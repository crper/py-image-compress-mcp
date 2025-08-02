"""压缩配置模型。

定义图片压缩的配置参数和选项。
"""

from enum import Enum
from pathlib import Path

from PIL import Image
from pydantic import BaseModel, Field, field_validator, model_validator


class QualityMode(str, Enum):
    """质量模式枚举，简化设计"""

    LOSSLESS = "lossless"  # 无损压缩
    CUSTOM = "custom"  # 自定义质量（1-100）


class ResizeConfig(BaseModel):
    """尺寸调整配置"""

    max_width: int | None = Field(None, gt=0, description="最大宽度")
    max_height: int | None = Field(None, gt=0, description="最大高度")
    maintain_aspect_ratio: bool = Field(True, description="保持宽高比")
    upscale_allowed: bool = Field(False, description="是否允许放大")

    # 移除冗余的 field_validator，pydantic 的 gt=0 约束已经足够


class CompressionConfig(BaseModel):
    """压缩配置，简化设计"""

    # 输入输出
    input_path: Path = Field(description="输入文件路径")
    output_path: Path | None = Field(None, description="输出文件路径")
    output_dir: Path | None = Field(None, description="输出目录")

    # 质量设置
    quality_mode: QualityMode = Field(QualityMode.LOSSLESS, description="质量模式")
    custom_quality: int | None = Field(None, ge=1, le=100, description="自定义质量值")

    # 格式设置
    target_format: str | None = Field(None, description="目标格式")
    preserve_format: bool = Field(True, description="保持原格式")

    # 尺寸设置
    resize_config: ResizeConfig | None = Field(None, description="尺寸调整配置")

    # 优化选项
    optimize: bool = Field(True, description="启用优化")
    progressive: bool = Field(True, description="渐进式JPEG")
    strip_metadata: bool = Field(False, description="移除元数据")
    keep_orientation: bool = Field(True, description="保持图片方向信息")

    # 压缩策略选项
    fallback_to_original: bool = Field(False, description="压缩效果差时回退到原文件")

    @model_validator(mode="after")
    def validate_custom_quality(self) -> "CompressionConfig":
        if self.quality_mode == QualityMode.CUSTOM and self.custom_quality is None:
            raise ValueError("自定义模式必须指定质量值")
        return self

    @field_validator("target_format")
    @classmethod
    def validate_target_format(cls, v: str | None) -> str | None:
        if v is not None:
            # 使用 Pillow 动态检查格式支持
            supported_formats = {
                fmt.upper() for fmt in Image.registered_extensions().values() if fmt
            }
            if v.upper() not in supported_formats:
                raise ValueError(
                    f"不支持的格式: {v}，支持的格式: {sorted(supported_formats)}"
                )
        return v.upper() if v else v

    @property
    def effective_quality(self) -> int | None:
        """获取有效的质量值"""
        match self.quality_mode:
            case QualityMode.LOSSLESS:
                return None
            case QualityMode.CUSTOM:
                return self.custom_quality

    @property
    def should_resize(self) -> bool:
        """是否需要调整尺寸"""
        return self.resize_config is not None and (
            self.resize_config.max_width is not None
            or self.resize_config.max_height is not None
        )

    def get_output_path(
        self,
        original_path: Path,
        format_override: str | None = None,
        skip_suffix: bool = False,
    ) -> Path:
        """生成输出路径

        Args:
            original_path: 原始文件路径
            format_override: 格式覆盖
            skip_suffix: 是否跳过质量后缀（用于无损压缩无效果时）

        Returns:
            Path: 生成的输出路径
        """
        # 优先使用用户指定的输出路径
        if self.output_path:
            return self.output_path

        return self._generate_auto_path(original_path, format_override, skip_suffix)

    def _generate_auto_path(
        self,
        original_path: Path,
        format_override: str | None = None,
        skip_suffix: bool = False,
    ) -> Path:
        """生成自动命名的输出路径"""
        # 确定输出目录
        output_dir = self.output_dir or original_path.parent

        # 确定文件名和扩展名
        base_name = original_path.stem

        # 添加质量后缀（除非明确跳过或用户指定了输出路径）
        if not skip_suffix:
            suffix = self._get_quality_suffix()
            if suffix:
                base_name += suffix

        # 确定扩展名
        ext = self._determine_extension(original_path, format_override)

        return output_dir / f"{base_name}{ext}"

    def _get_quality_suffix(self) -> str:
        """获取质量后缀"""
        if self.quality_mode != QualityMode.LOSSLESS:
            # 有损压缩：使用 _compress_[quality] 格式
            return (
                f"_compress_{self.effective_quality}"
                if self.effective_quality
                else "_compress"
            )
        # 无损压缩：使用 _compress 格式
        return "_compress"

    def _determine_extension(
        self, original_path: Path, format_override: str | None = None
    ) -> str:
        """确定文件扩展名"""
        if format_override:
            return self._get_format_extension(format_override)
        if self.target_format:
            return self._get_format_extension(self.target_format)
        if self.preserve_format:
            return original_path.suffix
        return original_path.suffix

    def _get_format_extension(self, format_name: str) -> str:
        """获取格式对应的扩展名"""
        format_upper = format_name.upper()

        # 优先使用常见的扩展名映射，确保用户友好的扩展名
        preferred_extensions = {
            "JPEG": ".jpg",
            "PNG": ".png",
            "WEBP": ".webp",
            "GIF": ".gif",
            "BMP": ".bmp",
            "TIFF": ".tiff",
            "ICO": ".ico",
        }

        # 如果是常见格式，直接返回首选扩展名
        if format_upper in preferred_extensions:
            return preferred_extensions[format_upper]

        # 对于其他格式，从 Pillow 动态获取扩展名
        for ext, fmt in Image.registered_extensions().items():
            if fmt and fmt.upper() == format_upper:
                return ext.lower()

        # 最后的后备选择
        return ".jpg"


class StrategyType(str, Enum):
    """策略类型枚举"""

    LOSSLESS = "lossless"
    LOSSY = "lossy"
    ADAPTIVE = "adaptive"
    SKIP = "skip"


class CompressionDecision(BaseModel):
    """压缩决策结果，简化设计"""

    strategy_type: StrategyType = Field(description="策略类型")
    recommended_quality: int | None = Field(
        None, ge=1, le=100, description="推荐质量值"
    )
    recommended_format: str | None = Field(None, description="推荐格式")
    reason: str = Field(default="", description="决策原因")
    skip_compression: bool = Field(default=False, description="是否跳过压缩")

    @field_validator("recommended_format")
    @classmethod
    def validate_recommended_format(cls, v: str | None) -> str | None:
        if v is not None:
            # 使用 Pillow 动态检查格式支持
            supported_formats = {
                fmt.upper() for fmt in Image.registered_extensions().values() if fmt
            }
            if v.upper() not in supported_formats:
                raise ValueError(
                    f"不支持的推荐格式: {v}，支持的格式: {sorted(supported_formats)}"
                )
        return v.upper() if v else v


# ============================================================================
# 验证器类 - 集中的参数验证逻辑
# ============================================================================


class CompressionValidators:
    """压缩相关的验证器集合"""

    @staticmethod
    def validate_format(format_str: str) -> str:
        """验证并标准化格式名称

        Args:
            format_str: 格式字符串

        Returns:
            str: 标准化的格式名称

        Raises:
            ValidationError: 格式不支持时
        """
        # 导入 ValidationError（避免循环导入）
        from ..exceptions import ValidationError

        if not format_str:
            raise ValidationError("格式不能为空")

        # 导入常量（避免循环导入）
        from .constants import ImageFormats, get_format_alias

        # 标准化格式名称
        standard_format = get_format_alias(format_str)

        # 检查是否为支持的格式
        supported_formats = ImageFormats.get_supported_formats()

        if standard_format not in supported_formats:
            available = sorted(supported_formats)
            raise ValidationError(
                f"不支持的格式: {format_str}。可用格式: {', '.join(available)}"
            )

        return standard_format

    @staticmethod
    def validate_quality(quality: int | None) -> int | None:
        """验证质量参数

        Args:
            quality: 质量值

        Returns:
            int | None: 验证后的质量值

        Raises:
            ValidationError: 质量值无效时
        """
        from ..exceptions import ValidationError

        if quality is None:
            return None

        if not isinstance(quality, int) or not (1 <= quality <= 100):
            raise ValidationError(f"质量值必须在 1-100 之间的整数，得到: {quality}")

        return quality

    @staticmethod
    def validate_dimensions(
        width: int | None, height: int | None
    ) -> tuple[int | None, int | None]:
        """验证尺寸参数

        Args:
            width: 宽度
            height: 高度

        Returns:
            tuple: 验证后的宽度和高度

        Raises:
            ValidationError: 尺寸无效时
        """
        from ..exceptions import ValidationError

        if width is not None:
            if not isinstance(width, int) or width <= 0:
                raise ValidationError(f"宽度必须是正整数，得到: {width}")
            if width > 50000:  # 合理的限制
                raise ValidationError(f"宽度超过限制 50000，得到: {width}")

        if height is not None:
            if not isinstance(height, int) or height <= 0:
                raise ValidationError(f"高度必须是正整数，得到: {height}")
            if height > 50000:  # 合理的限制
                raise ValidationError(f"高度超过限制 50000，得到: {height}")

        return width, height
