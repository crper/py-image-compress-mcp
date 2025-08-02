"""配置构建器模块。

统一的压缩配置构建逻辑，集成参数验证功能。
"""

import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from ..exceptions import ValidationError as CustomValidationError
from ..models import CompressionValidators
from ..models.compression_config import (
    CompressionConfig,
    QualityMode,
    ResizeConfig,
)


logger = logging.getLogger(__name__)


class ConfigBuilder:
    """压缩配置构建器

    提供统一的配置构建接口和参数验证。
    集成了所有验证逻辑，避免重复代码。
    """

    def __init__(self):
        """初始化配置构建器"""
        pass

    def build(
        self,
        input_path: str | Path,
        output_path: str | Path | None = None,
        output_dir: str | Path | None = None,
        quality: int | None = None,
        format: str | None = None,
        max_width: int | None = None,
        max_height: int | None = None,
        **kwargs: Any,
    ) -> CompressionConfig:
        """构建压缩配置（不验证，用于向后兼容）

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
            CompressionConfig: 构建的配置对象

        Raises:
            CustomValidationError: 参数验证失败
        """
        try:
            # 标准化路径参数
            input_path = Path(input_path)
            output_path = Path(output_path) if output_path else None
            output_dir = Path(output_dir) if output_dir else None

            # 直接构建配置
            return self._create_config(
                input_path=input_path,
                output_path=output_path,
                output_dir=output_dir,
                quality=quality,
                format=format,
                max_width=max_width,
                max_height=max_height,
                **kwargs,
            )

        except PydanticValidationError as e:
            error_msg = self._format_validation_error(e)
            raise CustomValidationError(
                error_msg,
                Path(input_path) if isinstance(input_path, str) else input_path,
            ) from e
        except Exception as e:
            raise CustomValidationError(
                f"配置构建失败: {e!s}",
                Path(input_path) if isinstance(input_path, str) else input_path,
            ) from e

    def validate_and_build(
        self,
        input_path: str | Path,
        output_path: str | Path | None = None,
        output_dir: str | Path | None = None,
        quality: int | None = None,
        format: str | None = None,
        max_width: int | None = None,
        max_height: int | None = None,
        validate_file_exists: bool = True,
        validate_is_file: bool = False,
        formats_list: list[str] | None = None,
        **kwargs: Any,
    ) -> CompressionConfig:
        """验证参数并构建压缩配置

        集成了所有验证逻辑，避免重复代码。

        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径（可选）
            output_dir: 输出目录（可选）
            quality: 压缩质量 1-100，None为智能选择
            format: 输出格式 JPEG/PNG/WEBP，None为智能选择
            max_width: 最大宽度
            max_height: 最大高度
            validate_file_exists: 是否验证文件存在
            validate_is_file: 是否验证输入是文件（而非目录）
            formats_list: 多格式验证时的格式列表
            **kwargs: 其他配置参数

        Returns:
            CompressionConfig: 构建的配置对象

        Raises:
            CustomValidationError: 参数验证失败
        """
        try:
            # 标准化路径参数
            input_path = Path(input_path)
            output_path = Path(output_path) if output_path else None
            output_dir = Path(output_dir) if output_dir else None

            # 执行验证
            self._validate_common_params(
                input_path, quality, format, max_width, max_height, validate_file_exists
            )

            if validate_is_file and not input_path.is_file():
                raise CustomValidationError(
                    f"输入路径不是文件: {input_path}", input_path
                )

            if formats_list is not None:
                self._validate_multi_format_params(input_path, output_dir, formats_list)

            # 构建配置
            return self._create_config(
                input_path=input_path,
                output_path=output_path,
                output_dir=output_dir,
                quality=quality,
                format=format,
                max_width=max_width,
                max_height=max_height,
                **kwargs,
            )

        except PydanticValidationError as e:
            error_msg = self._format_validation_error(e)
            raise CustomValidationError(
                error_msg,
                Path(input_path) if isinstance(input_path, str) else input_path,
            ) from e
        except CustomValidationError:
            raise  # 重新抛出自定义验证错误
        except Exception as e:
            raise CustomValidationError(
                f"配置构建失败: {e!s}",
                Path(input_path) if isinstance(input_path, str) else input_path,
            ) from e

    def _validate_common_params(
        self,
        input_path: Path,
        quality: int | None,
        format: str | None,
        max_width: int | None,
        max_height: int | None,
        validate_file_exists: bool = True,
    ) -> None:
        """通用参数验证方法，从 compressor.py 移入"""
        # 验证输入文件存在性
        if validate_file_exists and not input_path.exists():
            raise FileNotFoundError(f"输入文件不存在: {input_path}")

        # 验证质量参数
        if quality is not None and not (1 <= quality <= 100):
            raise CustomValidationError(
                f"质量参数必须在 1-100 之间，当前值: {quality}", input_path
            )

        # 验证格式参数
        if format is not None:
            try:
                CompressionValidators.validate_format(format)
            except Exception as e:
                raise CustomValidationError(str(e), input_path) from e

        # 验证尺寸参数
        if max_width is not None and max_width <= 0:
            raise CustomValidationError(
                f"最大宽度必须大于 0，当前值: {max_width}", input_path
            )

        if max_height is not None and max_height <= 0:
            raise CustomValidationError(
                f"最大高度必须大于 0，当前值: {max_height}", input_path
            )

    def _validate_multi_format_params(
        self,
        input_path: Path,
        output_dir: Path | None,
        formats: list[str],
    ) -> None:
        """验证多格式压缩参数，从 compressor.py 移入"""
        # 多格式特定验证
        if not formats:
            raise CustomValidationError("格式列表不能为空", input_path)

        # 验证输出目录的父目录是否存在
        if output_dir and output_dir.parent and not output_dir.parent.exists():
            raise CustomValidationError(
                f"输出目录的父目录不存在: {output_dir.parent}", input_path
            )

    def validate_and_normalize_formats(
        self, formats: list[str], input_path: Path
    ) -> list[str]:
        """验证并标准化格式列表，从 compressor.py 移入"""
        validated_formats = []

        for fmt in formats:
            if not fmt or not fmt.strip():
                continue

            try:
                normalized_format = CompressionValidators.validate_format(fmt)
                if normalized_format not in validated_formats:
                    validated_formats.append(normalized_format)
            except Exception as e:
                logger.warning(f"跳过不支持的格式 {fmt}: {e}")
                continue

        if not validated_formats:
            raise CustomValidationError("没有有效的输出格式", input_path)

        return validated_formats

    def _create_config(
        self,
        input_path: Path,
        output_path: Path | None = None,
        output_dir: Path | None = None,
        quality: int | None = None,
        format: str | None = None,
        max_width: int | None = None,
        max_height: int | None = None,
        **kwargs: Any,
    ) -> CompressionConfig:
        """创建配置对象"""
        # 确定质量模式
        if quality is None:
            quality_mode = QualityMode.LOSSLESS
            custom_quality = None
        else:
            quality_mode = QualityMode.CUSTOM
            custom_quality = quality

        # 构建尺寸配置
        resize_config = None
        if max_width is not None or max_height is not None:
            resize_config = ResizeConfig(
                max_width=max_width,
                max_height=max_height,
                maintain_aspect_ratio=kwargs.get("maintain_aspect_ratio", True),
                upscale_allowed=kwargs.get("upscale_allowed", False),
            )

        # 智能设置回退机制：
        # 1. 无损模式默认启用
        # 2. 现代格式转传统格式时启用（防止文件变大）
        # 3. 其他情况根据用户设置
        input_ext = input_path.suffix.lower()
        is_modern_to_legacy = input_ext in {".webp", ".avif", ".heif"} and format in {
            "JPEG",
            "PNG",
        }

        default_fallback = (
            True
            if quality_mode == QualityMode.LOSSLESS or is_modern_to_legacy
            else kwargs.get("fallback_to_original", False)
        )

        # 构建主配置
        return CompressionConfig(
            input_path=input_path,
            output_path=output_path,
            output_dir=output_dir,
            quality_mode=quality_mode,
            custom_quality=custom_quality,
            target_format=format,
            resize_config=resize_config,
            # 从kwargs获取其他参数，使用默认值
            preserve_format=kwargs.get("preserve_format", True),
            optimize=kwargs.get("optimize", True),
            progressive=kwargs.get("progressive", True),
            strip_metadata=kwargs.get("strip_metadata", False),
            keep_orientation=kwargs.get("keep_orientation", True),
            fallback_to_original=kwargs.get("fallback_to_original", default_fallback),
        )

    def _format_validation_error(self, error: PydanticValidationError) -> str:
        """格式化验证错误"""
        messages = []
        for err in error.errors():
            field = ".".join(str(loc) for loc in err["loc"])
            msg = err["msg"]
            if field:
                messages.append(f"{field}: {msg}")
            else:
                messages.append(msg)
        return "; ".join(messages)


# 全局配置构建器实例
_default_builder = ConfigBuilder()


def build_config(**kwargs: Any) -> CompressionConfig:
    """便捷的配置构建函数

    使用全局配置构建器实例构建配置。

    Args:
        **kwargs: 配置参数

    Returns:
        CompressionConfig: 构建的配置对象
    """
    return _default_builder.build(**kwargs)
