"""图像元数据模型。

定义图像文件的元数据结构，包括基础信息、EXIF数据、ICC配置文件等。
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, computed_field


class BasicImageInfo(BaseModel):
    """基础图片信息"""

    file_path: Path
    file_size: int = Field(description="文件大小（字节）")
    format: str = Field(description="图片格式")
    mode: str = Field(description="颜色模式")
    width: int = Field(description="图片宽度")
    height: int = Field(description="图片高度")
    has_transparency: bool = Field(default=False, description="是否有透明通道")
    frame_count: int = Field(default=1, description="帧数")

    @computed_field
    def is_animated(self) -> bool:
        """是否为动画图片"""
        return self.frame_count > 1

    @computed_field
    def aspect_ratio(self) -> float:
        """宽高比"""
        return self.width / self.height if self.height > 0 else 0.0

    @computed_field
    def total_pixels(self) -> int:
        """总像素数"""
        return self.width * self.height

    def get_total_pixels_human(self) -> str:
        """人性化显示总像素数"""
        from humanize import intword

        return intword(self.total_pixels)

    def get_file_size_human(self) -> str:
        """人性化显示文件大小"""
        from humanize import naturalsize

        return naturalsize(self.file_size, binary=True)

    @computed_field
    def orientation(self) -> str:
        """图片方向"""
        if self.width > self.height:
            return "landscape"
        if self.height > self.width:
            return "portrait"
        return "square"


class ExifData(BaseModel):
    """EXIF数据"""

    camera_make: str | None = None
    camera_model: str | None = None
    lens_model: str | None = None
    datetime_original: datetime | None = None
    datetime_digitized: datetime | None = None

    # 拍摄参数
    focal_length: float | None = None
    aperture: float | None = None
    shutter_speed: str | None = None
    iso: int | None = None
    flash: str | None = None

    # 图像设置
    white_balance: str | None = None
    exposure_mode: str | None = None
    metering_mode: str | None = None

    # GPS信息
    gps_latitude: float | None = None
    gps_longitude: float | None = None
    gps_altitude: float | None = None

    # 软件信息
    software: str | None = None
    artist: str | None = None
    copyright: str | None = None

    @computed_field
    def has_gps(self) -> bool:
        """是否包含GPS信息"""
        return self.gps_latitude is not None and self.gps_longitude is not None

    def get_datetime_original_human(self) -> str | None:
        """人性化显示拍摄时间"""
        if not self.datetime_original:
            return None
        from humanize import naturaltime

        return naturaltime(self.datetime_original)

    def get_datetime_digitized_human(self) -> str | None:
        """人性化显示数字化时间"""
        if not self.datetime_digitized:
            return None
        from humanize import naturaltime

        return naturaltime(self.datetime_digitized)


class ICCProfile(BaseModel):
    """ICC颜色配置文件信息"""

    profile_description: str | None = None
    color_space: str | None = None
    device_class: str | None = None
    rendering_intent: str | None = None
    profile_size: int | None = None
    creation_date: datetime | None = None

    # 原始配置文件数据（用于保留）
    raw_profile: bytes | None = None

    # 白点和色域信息
    white_point: tuple[float, float] | None = None
    red_colorant: tuple[float, float, float] | None = None
    green_colorant: tuple[float, float, float] | None = None
    blue_colorant: tuple[float, float, float] | None = None

    @computed_field
    def has_profile(self) -> bool:
        """是否有ICC配置文件"""
        return self.raw_profile is not None

    def get_creation_date_human(self) -> str | None:
        """人性化显示ICC配置文件创建时间"""
        if not self.creation_date:
            return None
        from humanize import naturaltime

        return naturaltime(self.creation_date)


class HistogramData(BaseModel):
    """直方图数据"""

    red_histogram: list[int] = Field(default_factory=list)
    green_histogram: list[int] = Field(default_factory=list)
    blue_histogram: list[int] = Field(default_factory=list)
    luminance_histogram: list[int] = Field(default_factory=list)

    @computed_field
    def brightness_stats(self) -> dict[str, float]:
        """亮度统计"""
        if not self.luminance_histogram:
            return {}

        total_pixels = sum(self.luminance_histogram)
        if total_pixels == 0:
            return {}

        # 计算平均亮度
        weighted_sum = sum(
            i * count for i, count in enumerate(self.luminance_histogram)
        )
        mean_brightness = weighted_sum / total_pixels / 255.0

        # 计算亮度分布
        dark_pixels = sum(self.luminance_histogram[:85])  # 0-33%
        mid_pixels = sum(self.luminance_histogram[85:170])  # 33-66%
        bright_pixels = sum(self.luminance_histogram[170:])  # 66-100%

        return {
            "mean_brightness": mean_brightness,
            "dark_ratio": dark_pixels / total_pixels,
            "mid_ratio": mid_pixels / total_pixels,
            "bright_ratio": bright_pixels / total_pixels,
        }


class ComplexityMetrics(BaseModel):
    """图片复杂度指标"""

    edge_density: float = Field(description="边缘密度")
    color_diversity: float = Field(description="颜色多样性")
    texture_complexity: float = Field(description="纹理复杂度")
    compression_difficulty: float = Field(description="压缩难度评分")

    @computed_field
    def overall_complexity(self) -> str:
        """整体复杂度评级"""
        avg_complexity = (
            self.edge_density + self.color_diversity + self.texture_complexity
        ) / 3

        if avg_complexity >= 0.8:
            return "very_high"
        if avg_complexity >= 0.6:
            return "high"
        if avg_complexity >= 0.4:
            return "medium"
        if avg_complexity >= 0.2:
            return "low"
        return "very_low"


class ImageMetadata(BaseModel):
    """完整的图片元数据"""

    basic_info: BasicImageInfo
    exif_data: ExifData | None = None
    icc_profile: ICCProfile | None = None
    histogram: HistogramData | None = None
    complexity: ComplexityMetrics | None = None
    xmp_data: "dict[str, Any] | None" = Field(
        None, description="XMP元数据（Pillow 11+支持）"
    )

    def get_file_size_human(self) -> str:
        """人类可读的文件大小"""
        return self.basic_info.get_file_size_human()


class ImageCharacteristics(BaseModel):
    """图片特征分析结果

    统一的图片特征分析结果，用于智能压缩决策。
    使用 Pydantic 模型提供数据验证和类型安全。
    """

    is_simple_graphic: bool = Field(description="是否为简单图形")
    is_photo_like: bool = Field(description="是否为照片类图片")
    color_count: int = Field(ge=0, description="颜色数量")
    complexity_score: float = Field(ge=0.0, le=1.0, description="复杂度分数")
    has_transparency: bool = Field(default=False, description="是否有透明通道")

    @computed_field
    def image_type(self) -> str:
        """图像类型分类"""
        if self.is_simple_graphic:
            return "simple_graphic"
        if self.is_photo_like:
            return "photo"
        return "mixed"

    def get_recommended_formats(self) -> list[str]:
        """推荐的输出格式"""
        formats = []

        # 基于透明度
        if self.basic_info.has_transparency:
            formats.extend(["PNG", "WEBP"])
        else:
            formats.extend(["JPEG", "WEBP"])

        # 基于复杂度
        if self.complexity and self.complexity.overall_complexity in (
            "very_low",
            "low",
        ):
            # 简单图形优先PNG
            formats = ["PNG", "WEBP"] + [f for f in formats if f not in ["PNG", "WEBP"]]

        return list(dict.fromkeys(formats))  # 去重并保持顺序
