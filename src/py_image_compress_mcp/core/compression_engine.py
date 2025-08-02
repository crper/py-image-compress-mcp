"""现代化压缩引擎模块。

提供简洁高效的图像压缩处理，专为进程池并发优化。
"""

import shutil
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

        # 创建处理组件
        info_extractor = ImageInfoExtractor()
        format_processor = FormatProcessor()
        strategy = CompressionStrategy()
        optimizer = CompressionOptimizer()

        # 提取图片元数据
        metadata = info_extractor.extract(config.input_path)

        # 智能策略决策（仅在用户未明确指定格式和质量时应用）
        if not config.target_format and config.quality_mode == QualityMode.LOSSLESS:
            decision = strategy.select_optimal(metadata, config)
            if decision.skip_compression:
                return _create_skip_result(config, decision.reason)
            config = _apply_strategy_decision(config, decision)
        # 用户明确指定了参数，跳过智能策略，直接压缩

        # 执行压缩
        return _compress_image(config, metadata, format_processor, optimizer)

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
) -> CompressionResult:
    """执行图片压缩"""
    original_size = metadata.basic_info.file_size
    output_path = config.get_output_path(config.input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 确定目标格式
    target_format = config.target_format or metadata.basic_info.format
    if target_format == "UNKNOWN":
        target_format = "JPEG"

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

        # 保存图片
        processed_img.save(output_path, **save_params)
        compressed_size = output_path.stat().st_size

        # 后处理：文件名优化和回退检查
        output_path, compressed_size = _post_process_result(
            config, output_path, original_size, compressed_size, target_format
        )

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
    output_path: Any,
    original_size: int,
    compressed_size: int,
    target_format: str,
) -> tuple[Any, int]:
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
        new_output_path = config.get_output_path(
            config.input_path, target_format, skip_suffix=True
        )
        if new_output_path != output_path and new_output_path != config.input_path:
            try:
                output_path.rename(new_output_path)
                output_path = new_output_path
            except OSError as e:
                logger.warning(f"重命名文件失败: {e}，保持原文件名")

    # 回退检查：如果压缩后文件变大，回退到原文件
    fallback_threshold = 1.005 if config.custom_quality is None else 1.02
    if compressed_size > original_size * fallback_threshold:
        logger.warning(
            f"压缩导致文件增大 {(compressed_size / original_size - 1) * 100:.1f}%，"
            f"强制回退到原文件（阈值: {(fallback_threshold - 1) * 100:.1f}%）"
        )
        try:
            output_path.unlink()
            shutil.copy2(config.input_path, output_path)
            compressed_size = original_size
        except OSError as e:
            logger.error(f"回退操作失败: {e}")

    return output_path, compressed_size


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

    shutil.copy2(config.input_path, output_path)

    file_size = config.input_path.stat().st_size

    return CompressionResult(
        input_path=config.input_path,
        output_path=output_path,
        original_size=file_size,
        compressed_size=file_size,
        success=True,
        format_used="SKIPPED",
        error=f"跳过压缩: {reason}",
        quality_used=None,
        was_resized=False,
        original_dimensions=None,
        final_dimensions=None,
    )


# PNG量化相关函数已移除，简化PNG处理逻辑
