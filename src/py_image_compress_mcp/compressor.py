"""现代化图像压缩器接口。

基于核心压缩引擎的简洁用户接口，提供智能压缩和详细分析功能。
充分利用 Python 3.10+ 和 Pillow 11+ 的现代化特性。
"""

from pathlib import Path
from typing import Any

from .config import get_default_max_workers
from .core.compression_engine import process_image
from .engine.batch import BatchProcessor
from .engine.config import ConfigBuilder
from .exceptions import (
    ErrorHandler,
    ValidationError,  # 统一使用 exceptions 模块的 ValidationError
)
from .models import (
    BatchResult,
    CompressionResult,
    MultiFormatResult,
    ProcessingResult,
)
from .utils.logging_helpers import get_logger


logger = get_logger()
DEFAULT_EXCLUDE_DIRS = ["output", ".venv", "node_modules", ".git", "__pycache__"]
DEFAULT_MULTI_OUTPUT_DIR = "output"


def _to_processing_result(
    result: BatchResult | CompressionResult | MultiFormatResult,
) -> ProcessingResult:
    """把领域结果统一包装成带顶层错误语义的处理结果。"""
    return {
        "success": result.success,
        "result": result,
        "error": None if result.success else result.error,
    }


class ImageCompressor:
    """现代化图像压缩器。

    提供简洁的图像压缩接口，支持单文件和批量处理。
    充分利用现代化 API 特性和健壮的错误处理。
    """

    def __init__(
        self,
        max_workers: int | None = None,
        force_executor_type: str | None = None,
    ):
        """初始化压缩器。

        Args:
            max_workers: 批量处理时的最大并发数
            force_executor_type: 强制指定执行器类型 ('thread'/'process'/None为自动选择)
        """
        # 参数验证
        resolved_max_workers = (
            get_default_max_workers() if max_workers is None else max_workers
        )

        if resolved_max_workers <= 0:
            raise ValidationError("max_workers 必须大于 0")

        if force_executor_type is not None and force_executor_type not in {
            "thread",
            "process",
        }:
            raise ValidationError(
                "force_executor_type 必须是 'thread', 'process' 或 None"
            )

        self.max_workers = resolved_max_workers
        self.force_executor_type = force_executor_type
        self.config_builder = ConfigBuilder()
        self.batch_processor = BatchProcessor(
            max_workers=resolved_max_workers,
            force_executor_type=force_executor_type,
            config_builder=self.config_builder,
        )

        logger.debug("初始化图像压缩器")

    def compress_image(
        self,
        input_path: str | Path,
        output_path: str | Path | None = None,
        output_dir: str | Path | None = None,
        quality: int | None = None,
        format: str | None = None,
        max_width: int | None = None,
        max_height: int | None = None,
        **kwargs: Any,
    ) -> CompressionResult:
        """压缩单个图像文件。

        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径（可选）
            output_dir: 输出目录（可选）
            quality: 压缩质量 1-100，None为智能选择
            format: 输出格式 JPEG/PNG/WEBP，None为智能选择
            max_width: 最大宽度
            max_height: 最大高度
            **kwargs: 其他配置参数

        Returns:
            CompressionResult: 压缩结果

        Examples:
            >>> compressor = ImageCompressor()
            >>> result = compressor.compress_image("photo.jpg", quality=80)
            >>> print(f"压缩比: {result.get_compression_ratio():.1f}%")
        """
        input_path = Path(input_path)

        try:
            # 使用 ConfigBuilder 的验证和构建功能
            config = self.config_builder.build(
                input_path=input_path,
                output_path=output_path,
                output_dir=output_dir,
                quality=quality,
                format=format,
                max_width=max_width,
                max_height=max_height,
                validate_file_exists=True,
                validate_is_file=True,
                **kwargs,
            )

            return process_image(config)

        except Exception as e:
            return ErrorHandler.handle_compression_error(e, input_path, "图像压缩")

    def compress_multi_format(
        self,
        input_path: str | Path,
        output_dir: str | Path,
        formats: list[str],
        quality: int | None = None,
        max_width: int | None = None,
        max_height: int | None = None,
    ) -> MultiFormatResult:
        """多格式压缩。

        将一张图像同时输出为多种格式，便于比较和选择。
        使用现代化的格式验证和错误处理。

        Args:
            input_path: 输入图像路径
            output_dir: 输出目录
            formats: 输出格式列表，如 ["JPEG", "PNG", "WEBP"]
            quality: 压缩质量
            max_width: 最大宽度
            max_height: 最大高度

        Returns:
            MultiFormatResult: 多格式压缩结果
        """
        input_path = Path(input_path)
        output_dir = Path(output_dir)

        try:
            # 创建输出目录
            output_dir.mkdir(parents=True, exist_ok=True)

            # 验证并标准化格式列表
            validated_formats = self.config_builder.validate_and_normalize_formats(
                formats, input_path
            )

            # 为每种格式压缩
            results = self._process_formats(
                input_path,
                output_dir,
                validated_formats,
                quality,
                max_width,
                max_height,
            )

            success = any(r.success for r in results)
            error = None if success else "所有格式压缩都失败"

            return MultiFormatResult(
                input_path=input_path,
                results=results,
                success=success,
                error=error,
            )

        except Exception as e:
            logger.error(f"多格式压缩失败: {e}")
            return MultiFormatResult(
                input_path=input_path,
                results=[],
                success=False,
                error=str(e),
            )

    def _process_formats(
        self,
        input_path: Path,
        output_dir: Path,
        formats: list[str],
        quality: int | None,
        max_width: int | None,
        max_height: int | None,
    ) -> list[CompressionResult]:
        """处理多种格式的压缩"""
        results = []

        for fmt in formats:
            try:
                config = self.config_builder.build(
                    input_path=input_path,
                    output_dir=output_dir,
                    quality=quality,
                    format=fmt,
                    max_width=max_width,
                    max_height=max_height,
                )
                result = process_image(config)
                results.append(result)

            except Exception as e:
                error_result = ErrorHandler.handle_compression_error(
                    e, input_path, f"格式{fmt}压缩"
                )
                results.append(error_result)

        return results

    def _process_directory_unified(
        self,
        input_path: Path,
        output: str | Path | None,
        formats: list[str] | str | None,
        quality: int | None = None,
        max_width: int | None = None,
        max_height: int | None = None,
        recursive: bool = True,
    ) -> ProcessingResult:
        """统一的目录处理方法，支持单格式和多格式"""
        try:
            format_list = self._normalize_universal_formats(formats)

            # 单格式处理（包括智能选择）
            if len(format_list) == 1:
                result = self._process_directory_for_format(
                    input_path=input_path,
                    output=output,
                    format_name=format_list[0],
                    quality=quality,
                    max_width=max_width,
                    max_height=max_height,
                    recursive=recursive,
                )
                return _to_processing_result(result)

            # 多格式处理 - 过滤掉 None 值
            non_none_formats = [f for f in format_list if f is not None]
            validated_formats = self.config_builder.validate_and_normalize_formats(
                non_none_formats, input_path
            )

            all_results = []
            overall_success = True

            for fmt in validated_formats:
                try:
                    result = self._process_directory_for_format(
                        input_path=input_path,
                        output=output,
                        format_name=fmt,
                        quality=quality,
                        max_width=max_width,
                        max_height=max_height,
                        recursive=recursive,
                    )
                    all_results.extend(result.results)
                    if not result.success:
                        overall_success = False
                except Exception as e:
                    logger.error(f"格式{fmt}批量处理失败: {e}")
                    overall_success = False

            # 创建合并的批量结果
            merged_result = BatchResult(
                input_dir=input_path,
                output_dir=Path(output) if output else input_path,
                results=all_results,
                success=overall_success,
                error=None if overall_success else "部分格式处理失败",
            )
            return {
                "success": merged_result.success,
                "result": merged_result,
                "error": None if merged_result.success else merged_result.error,
            }

        except Exception as e:
            logger.error(f"目录处理失败: {e}")
            error_result = ErrorHandler.create_error_batch_result(
                input_dir=input_path,
                output_dir=Path(output) if output else None,
                error_message=str(e),
            )
            return {"success": False, "result": error_result, "error": str(e)}

    def _process_directory_for_format(
        self,
        *,
        input_path: Path,
        output: str | Path | None,
        format_name: str | None,
        quality: int | None,
        max_width: int | None,
        max_height: int | None,
        recursive: bool,
    ) -> BatchResult:
        """按指定格式处理目录。"""
        return self.batch_processor.process_directory(
            input_dir=input_path,
            output_dir=output,
            quality=quality,
            format=format_name,
            max_width=max_width,
            max_height=max_height,
            recursive=recursive,
            exclude_dirs=DEFAULT_EXCLUDE_DIRS.copy(),
        )

    def _normalize_universal_formats(
        self, formats: list[str] | str | None
    ) -> list[str | None]:
        """标准化通用压缩格式参数。"""
        if isinstance(formats, str):
            return [formats]
        if isinstance(formats, list):
            return list(formats)
        return [None]

    def compress_universal(
        self,
        input_path: str | Path,
        output: str | Path | None = None,
        formats: list[str] | str | None = None,
        quality: int | None = None,
        max_width: int | None = None,
        max_height: int | None = None,
        recursive: bool = True,
    ) -> ProcessingResult:
        """通用压缩工具，自动处理文件或文件夹。

        使用现代化的路径处理和 match-case 语句进行智能分发。

        Args:
            input_path: 输入路径（文件或文件夹）
            output: 输出路径（文件时为文件路径，文件夹时为输出目录）
            formats: 输出格式，支持单个格式字符串或格式列表
            quality: 压缩质量 1-100，None为智能选择
            max_width: 最大宽度（像素）
            max_height: 最大高度（像素）
            recursive: 文件夹时是否递归处理子目录

        Returns:
            ProcessingResult: 统一的压缩结果格式
        """
        input_path = Path(input_path)

        try:
            # 使用 match-case 根据输入路径类型进行处理
            match input_path:
                case path if path.is_file():
                    # 处理单个文件
                    result = self._process_single_file_universal(
                        path, output, formats, quality, max_width, max_height
                    )
                    return _to_processing_result(result)

                case path if path.is_dir():
                    # 处理目录
                    return self._process_directory_unified(
                        path,
                        output,
                        formats,
                        quality,
                        max_width,
                        max_height,
                        recursive,
                    )

                case path if not path.exists():
                    # 路径不存在
                    error_result = ErrorHandler.handle_compression_error(
                        FileNotFoundError(f"输入路径不存在: {path}"), path, "路径验证"
                    )
                    return {
                        "success": False,
                        "result": error_result,
                        "error": "输入路径不存在",
                    }

                case _:
                    # 其他情况（如特殊文件类型）
                    error_result = ErrorHandler.handle_compression_error(
                        ValidationError(f"不支持的路径类型: {input_path}"),
                        input_path,
                        "路径类型检查",
                    )
                    return {
                        "success": False,
                        "result": error_result,
                        "error": "不支持的路径类型",
                    }

        except Exception as e:
            error_result = ErrorHandler.handle_compression_error(
                e, input_path, "通用压缩处理"
            )
            return {"success": False, "result": error_result, "error": str(e)}

    def _process_single_file_universal(
        self,
        input_path: Path,
        output: str | Path | None,
        formats: list[str] | str | None,
        quality: int | None,
        max_width: int | None,
        max_height: int | None,
    ) -> CompressionResult | MultiFormatResult:
        """处理单个文件的通用压缩"""
        if not isinstance(formats, list) or len(formats) <= 1:
            single_format = (
                formats[0] if isinstance(formats, list) and formats else formats
            )
            if isinstance(single_format, list):
                raise ValidationError("单文件压缩的输出格式必须是字符串或空值")
            return self.compress_image(
                input_path=input_path,
                output_path=output,
                format=single_format,
                quality=quality,
                max_width=max_width,
                max_height=max_height,
            )

        output_dir = (
            Path(output)
            if output is not None
            else input_path.parent / DEFAULT_MULTI_OUTPUT_DIR
        )
        return self.compress_multi_format(
            input_path=input_path,
            output_dir=output_dir,
            formats=formats,
            quality=quality,
            max_width=max_width,
            max_height=max_height,
        )
