"""现代化压缩引擎模块。

提供简洁高效的图像压缩处理，专为进程池并发优化。
"""

import shutil
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from ..models.compression_config import (
    CompressionConfig,
    CompressionDecision,
    QualityMode,
)
from ..models.compression_result import CompressionResult
from ..models.image_metadata import ImageMetadata
from ..utils.logging_helpers import get_logger
from .formats import FormatProcessor, get_save_parameters
from .image_info import ImageInfoExtractor
from .optimizer import CompressionOptimizer
from .strategy import CompressionStrategy


logger = get_logger()
FAST_INFO_EXTRACTOR = ImageInfoExtractor(
    include_exif=False,
    include_icc=False,
    include_xmp=False,
    include_histogram=False,
    include_complexity=True,
)
FORMAT_PROCESSOR = FormatProcessor()
STRATEGY = CompressionStrategy()
OPTIMIZER = CompressionOptimizer()
JPEG_REENCODE_SKIP_MIN_PIXELS = 2_000_000
JPEG_REENCODE_SKIP_MAX_BYTES_PER_PIXEL = 0.08
WEBP_REENCODE_SKIP_MAX_FILE_SIZE = 32 * 1024
WEBP_REENCODE_SKIP_MAX_PIXELS = 512 * 512
REENCODE_SKIP_MIN_QUALITY = 80
EXPLICIT_JPEG_SKIP_MAX_QUALITY = 80


def process_image(config: CompressionConfig) -> CompressionResult:
    """处理单个图像压缩。

    统一的图像处理入口，适用于单线程和多进程环境。

    Args:
        config: 压缩配置

    Returns:
        CompressionResult: 压缩结果
    """
    try:
        # 验证输入文件
        if not config.input_path.exists():
            from ..exceptions import ErrorHandler

            return ErrorHandler.handle_with_context(
                FileNotFoundError(f"输入文件不存在: {config.input_path}"),
                config.input_path,
                "文件验证",
                log_level="warning",
            )

        # 提取图片元数据
        metadata = FAST_INFO_EXTRACTOR.extract(config.input_path)

        # 智能策略决策（仅在用户未明确指定格式和质量时应用）
        if not config.target_format and config.quality_mode == QualityMode.LOSSLESS:
            decision = STRATEGY.select_optimal(metadata, config)
            if decision.skip_compression:
                return _create_skip_result(config, decision.reason)
            config = _apply_strategy_decision(config, decision)
        # 用户明确指定了参数，跳过智能策略，直接压缩

        target_format = _resolve_target_format(config, metadata)
        _validate_output_path(config.get_output_path(config.input_path))
        skip_reason = _get_preemptive_skip_reason(config, metadata, target_format)
        if skip_reason is not None:
            logger.info("跳过同格式重编码 %s: %s", config.input_path, skip_reason)
            return _create_skip_result(config, skip_reason)

        # 执行压缩
        return _compress_image(
            config,
            metadata,
            FORMAT_PROCESSOR,
            OPTIMIZER,
            target_format=target_format,
        )

    except Exception as e:
        # 统一的异常处理，确保总是返回 CompressionResult
        from ..exceptions import ErrorHandler

        return ErrorHandler.handle_compression_error(
            e, config.input_path, "图像压缩引擎"
        )


def _compress_image(
    config: CompressionConfig,
    metadata: ImageMetadata,
    format_processor: FormatProcessor,
    optimizer: CompressionOptimizer,
    *,
    target_format: str,
) -> CompressionResult:
    """执行图片压缩"""
    original_size = metadata.basic_info.file_size
    output_path = config.get_output_path(config.input_path)
    _validate_output_path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 处理图片并保存
    with Image.open(config.input_path) as img:
        processed_img, was_resized, original_dimensions = _process_image(
            img, config, format_processor, target_format
        )

        # 获取保存参数
        base_params, actual_quality = get_save_parameters(target_format, config)
        if base_params.get("skip_processing"):
            logger.info(f"跳过处理 {config.input_path}，避免JPEG无损模式的质量损失")
            return _create_skip_result(config, "JPEG无损模式跳过处理")

        save_params = optimizer.optimize_parameters(
            target_format, config, metadata, base_params
        )

        # PNG特殊处理日志
        _log_png_processing(target_format, config, original_size)

        temp_output_path = _create_temp_output_path(output_path)

        try:
            processed_img.save(temp_output_path, format=target_format, **save_params)
            compressed_size = temp_output_path.stat().st_size

            # 后处理：文件名优化和回退检查
            output_path, compressed_size = _post_process_result(
                config,
                temp_output_path,
                output_path,
                original_size,
                compressed_size,
                target_format,
            )
        finally:
            if temp_output_path.exists():
                temp_output_path.unlink(missing_ok=True)

        return CompressionResult(
            input_path=config.input_path,
            output_path=output_path,
            original_size=original_size,
            compressed_size=compressed_size,
            success=True,
            format_used=target_format,
            quality_used=actual_quality,
            was_resized=was_resized,
            original_dimensions=original_dimensions,
            final_dimensions=processed_img.size,
            error=None,
        )


def _resolve_target_format(config: CompressionConfig, metadata: ImageMetadata) -> str:
    """解析本次压缩实际使用的目标格式。"""
    target_format = config.target_format or metadata.basic_info.format
    if target_format == "UNKNOWN":
        return "JPEG"
    return target_format


def _get_preemptive_skip_reason(
    config: CompressionConfig,
    metadata: ImageMetadata,
    target_format: str,
) -> str | None:
    """在真正编码前拦截高概率负优化的同格式重编码。"""
    if config.quality_mode != QualityMode.CUSTOM or config.should_resize:
        return None

    source_format = metadata.basic_info.format
    if source_format != target_format:
        return None

    requested_quality = config.effective_quality
    if requested_quality is None or requested_quality < REENCODE_SKIP_MIN_QUALITY:
        return None

    if config.target_format is not None:
        if (
            target_format == "JPEG"
            and requested_quality <= EXPLICIT_JPEG_SKIP_MAX_QUALITY
            and _should_skip_jpeg_reencode(metadata)
        ):
            return "JPEG 已经是高压缩密度的大图，跳过显式同格式重编码"
        return None

    if target_format == "JPEG" and _should_skip_jpeg_reencode(metadata):
        return "JPEG 已经是高压缩密度的大图，跳过同格式重编码"

    if target_format == "WEBP" and _should_skip_webp_reencode(metadata):
        return "WebP 已经是简单小图，跳过同格式重编码"

    return None


def _should_skip_jpeg_reencode(metadata: ImageMetadata) -> bool:
    """判断 JPEG 同格式重编码是否大概率属于负优化。"""
    basic = metadata.basic_info
    total_pixels = max(1, basic.total_pixels)
    bytes_per_pixel = basic.file_size / total_pixels

    return bool(
        total_pixels >= JPEG_REENCODE_SKIP_MIN_PIXELS
        and bytes_per_pixel <= JPEG_REENCODE_SKIP_MAX_BYTES_PER_PIXEL
    )


def _should_skip_webp_reencode(metadata: ImageMetadata) -> bool:
    """判断简单小型 WebP 的同格式重编码是否值得跳过。"""
    basic = metadata.basic_info
    complexity = metadata.complexity

    if basic.file_size > WEBP_REENCODE_SKIP_MAX_FILE_SIZE:
        return False
    if basic.total_pixels > WEBP_REENCODE_SKIP_MAX_PIXELS:
        return False
    if complexity is None:
        return False

    return bool(complexity.color_diversity <= 0.12)


def _process_image(
    img: Image.Image,
    config: CompressionConfig,
    format_processor: FormatProcessor,
    target_format: str,
) -> tuple[Image.Image, bool, tuple[int, int]]:
    """处理图片：EXIF旋转、尺寸调整、格式转换"""
    # 处理EXIF旋转
    img = ImageOps.exif_transpose(img)
    original_dimensions = img.size

    # 调整尺寸（如果需要）
    was_resized = False
    if config.should_resize:
        img = _resize_image(img, config.resize_config)
        was_resized = img.size != original_dimensions

    # 格式转换和优化
    img = format_processor.prepare_for_format(img, target_format)

    return img, was_resized, original_dimensions


def _log_png_processing(
    target_format: str, config: CompressionConfig, original_size: int
) -> None:
    """记录PNG处理日志"""
    if target_format == "PNG" and config.effective_quality is not None:
        if original_size > 200 * 1024:
            logger.info(f"PNG文件较大({original_size} bytes)，尝试PNG优化")
        else:
            logger.info(f"PNG文件中小尺寸({original_size} bytes)，保持原格式")


def _post_process_result(
    config: CompressionConfig,
    temp_output_path: Path,
    output_path: Path,
    original_size: int,
    compressed_size: int,
    target_format: str,
) -> tuple[Path, int]:
    """后处理：文件名优化和回退检查"""
    # 检查无损压缩效果：如果压缩效果不明显，使用原文件名
    compression_ratio = (
        (original_size - compressed_size) / original_size if original_size > 0 else 0
    )
    should_use_original_name = (
        config.quality_mode == QualityMode.LOSSLESS
        and compression_ratio < 0.05
        and config.output_path is None  # 只有在用户未指定输出路径时才重命名
    )

    if should_use_original_name:
        output_path = config.get_output_path(
            config.input_path, target_format, skip_suffix=True
        )

    # 回退检查：如果压缩后文件变大，回退到原文件
    fallback_threshold = 1.005 if config.custom_quality is None else 1.02
    if compressed_size > original_size * fallback_threshold:
        logger.warning(
            f"压缩导致文件增大 {(compressed_size / original_size - 1) * 100:.1f}%，"
            f"强制回退到原文件（阈值: {(fallback_threshold - 1) * 100:.1f}%）"
        )
        if not _paths_refer_to_same_file(config.input_path, output_path):
            shutil.copy2(config.input_path, output_path)
        compressed_size = original_size
        return output_path, compressed_size

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_output_path.replace(output_path)

    return output_path, compressed_size


def _validate_output_path(output_path: Path) -> None:
    """确保输出路径可作为文件写入。"""
    if output_path.exists() and output_path.is_dir():
        raise IsADirectoryError(f"输出路径是目录，无法写入文件: {output_path}")


def _create_temp_output_path(output_path: Path) -> Path:
    """在目标目录中创建临时输出文件路径。"""
    with tempfile.NamedTemporaryFile(
        prefix=f".{output_path.stem}_",
        suffix=output_path.suffix,
        dir=output_path.parent,
        delete=False,
    ) as temp_file:
        return Path(temp_file.name)


def _resize_image(img: Image.Image, resize_config: Any) -> Image.Image:
    """调整图片尺寸"""
    if not resize_config:
        return img

    current_width, current_height = img.size
    max_width = resize_config.max_width or current_width
    max_height = resize_config.max_height or current_height

    # 检查是否需要调整
    if current_width <= max_width and current_height <= max_height:
        return img

    # 计算新尺寸
    if resize_config.maintain_aspect_ratio:
        # 保持宽高比
        ratio = min(max_width / current_width, max_height / current_height)
        new_width = int(current_width * ratio)
        new_height = int(current_height * ratio)
    else:
        # 不保持宽高比
        new_width = min(current_width, max_width)
        new_height = min(current_height, max_height)

    # 检查是否允许放大
    if not resize_config.upscale_allowed:
        new_width = min(new_width, current_width)
        new_height = min(new_height, current_height)

    # 执行调整
    return img.resize((new_width, new_height), Image.Resampling.LANCZOS)


def _apply_strategy_decision(
    config: CompressionConfig, decision: CompressionDecision
) -> CompressionConfig:
    """应用策略决策到配置"""
    # 创建配置副本
    new_config: CompressionConfig = config.model_copy()

    # 应用推荐的格式
    if decision.recommended_format:
        new_config.target_format = decision.recommended_format

    # 应用推荐的质量
    if decision.recommended_quality is not None:
        new_config.custom_quality = decision.recommended_quality
        new_config.quality_mode = QualityMode.CUSTOM

    return new_config


def _create_skip_result(config: CompressionConfig, reason: str) -> CompressionResult:
    """创建跳过压缩的结果"""
    # 直接复制原文件到输出位置
    output_path = config.get_output_path(config.input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    note = f"跳过压缩: {reason}"
    if not _paths_refer_to_same_file(config.input_path, output_path):
        shutil.copy2(config.input_path, output_path)

    file_size = config.input_path.stat().st_size

    return CompressionResult(
        input_path=config.input_path,
        output_path=output_path,
        original_size=file_size,
        compressed_size=file_size,
        success=True,
        format_used="SKIPPED",
        error=None,
        skipped=True,
        note=note,
        quality_used=None,
        was_resized=False,
        original_dimensions=None,
        final_dimensions=None,
    )


def _paths_refer_to_same_file(first_path: Path, second_path: Path) -> bool:
    """判断两个路径是否实际指向同一文件。"""
    try:
        return first_path.resolve() == second_path.resolve()
    except OSError:
        return first_path == second_path


# PNG量化相关函数已移除，简化PNG处理逻辑
