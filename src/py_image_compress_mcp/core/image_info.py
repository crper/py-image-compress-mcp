"""增强的图片信息提取器。

利用 Pillow 的完整特性提取图片的详细元数据信息。
"""

# 可选的 defusedxml 导入，用于安全的 XMP 处理
import importlib.util
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps
from PIL.ExifTags import TAGS

from ..models.image_metadata import (
    BasicImageInfo,
    ComplexityMetrics,
    ExifData,
    HistogramData,
    ICCProfile,
    ImageCharacteristics,
    ImageMetadata,
)
from ..utils.logging_helpers import get_logger


# 可选的 defusedxml 检查，用于安全的 XMP 处理
HAS_DEFUSEDXML = importlib.util.find_spec("defusedxml") is not None


logger = get_logger()


@lru_cache(maxsize=128)
def _get_format_from_extension(extension: str) -> str | None:
    """从扩展名获取格式，使用缓存优化性能"""
    result = Image.registered_extensions().get(extension.lower())
    return str(result) if result is not None else None


class ImageInfoExtractor:
    """图片信息提取器

    默认启用所有分析功能，提供完整的图片信息用于智能压缩决策。
    """

    def __init__(self) -> None:
        """初始化提取器

        所有分析功能默认启用，包括：
        - 基础信息（尺寸、格式、透明度等）
        - EXIF数据分析
        - ICC色彩配置文件
        - 颜色直方图分析
        - 图像复杂度分析
        """
        pass  # 不需要配置参数，所有功能默认启用

    def extract(self, file_path: str | Path) -> ImageMetadata:
        """提取完整的图片元数据

        基于Pillow 11的增强功能：
        - 支持PNG、TIFF、JPEG的EXIF数据
        - 支持WebP、PNG、TIFF、JPEG的XMP数据
        - 改进的ICC配置文件处理
        - 更全面的元数据提取

        Args:
            file_path: 图片文件路径

        Returns:
            ImageMetadata: 完整的元数据对象，包含所有可用的分析信息
        """
        file_path = Path(file_path)

        with Image.open(file_path) as img:
            # 处理EXIF旋转
            img = ImageOps.exif_transpose(img)

            # 提取基础信息
            basic_info = self._extract_basic_info(img, file_path)

            # 提取增强的元数据信息
            exif_data = self._extract_exif_data(img)
            icc_profile = self._extract_icc_profile(img)
            xmp_data = self._extract_xmp_data(img)
            histogram = self._extract_histogram(img)
            complexity = self._calculate_complexity(img)

            return ImageMetadata(
                basic_info=basic_info,
                exif_data=exif_data,
                icc_profile=icc_profile,
                xmp_data=xmp_data,
                histogram=histogram,
                complexity=complexity,
            )

    def _detect_transparency(self, img: Image.Image) -> bool:
        """检测图片是否有透明度 - 使用简化的Pillow API检测"""
        # 检查颜色模式 - 这些模式天然支持透明度
        if img.mode in ("RGBA", "LA", "PA"):
            return True

        # 检查 Image.info 中的透明度信息 - 适用于PNG、GIF等格式
        if "transparency" in img.info:
            return True

        # 对于调色板模式，检查是否有透明色索引
        return bool(
            img.mode == "P" and hasattr(img, "info") and "transparency" in img.info
        )

    def _extract_basic_info(self, img: Image.Image, file_path: Path) -> BasicImageInfo:
        """提取基础图片信息"""
        file_size = file_path.stat().st_size
        width, height = img.size

        # 使用 Pillow 的格式检测，无需手动映射
        detected_format = img.format or "UNKNOWN"

        # 如果 Pillow 无法检测格式，尝试从扩展名推断
        if detected_format == "UNKNOWN":
            # 使用缓存的格式检测函数
            format_from_ext = _get_format_from_extension(file_path.suffix)
            if format_from_ext:
                detected_format = format_from_ext

        # 检测透明度 - 利用 Pillow 的内置信息
        has_transparency = self._detect_transparency(img)

        return BasicImageInfo(
            file_path=file_path,
            file_size=file_size,
            format=detected_format,
            mode=img.mode,
            width=width,
            height=height,
            has_transparency=has_transparency,
            frame_count=getattr(img, "n_frames", 1),
        )

    def _extract_exif_data(self, img: Image.Image) -> ExifData | None:
        """提取EXIF数据 - 使用现代化的Pillow API"""
        try:
            # 使用现代的 getexif() 方法
            exif_dict = img.getexif()
            if not exif_dict:
                return None

            # 创建标签名到值的映射，使用PIL.ExifTags.TAGS
            exif_data = {}
            for tag_id, value in exif_dict.items():
                tag_name = TAGS.get(tag_id, tag_id)
                exif_data[tag_name] = value

            # 安全地获取EXIF数据
            def safe_get(key: str, default: Any = None) -> Any:
                return exif_data.get(key, default)

            # 简化的EXIF数据提取，只获取基础信息
            return ExifData(
                camera_make=safe_get("Make"),
                camera_model=safe_get("Model"),
                lens_model=safe_get("LensModel"),
                datetime_original=self._parse_datetime(safe_get("DateTimeOriginal")),
                datetime_digitized=self._parse_datetime(safe_get("DateTimeDigitized")),
                focal_length=self._parse_focal_length(safe_get("FocalLength")),
                aperture=self._parse_aperture(safe_get("FNumber")),
                shutter_speed=self._parse_shutter_speed(safe_get("ExposureTime")),
                iso=safe_get("ISOSpeedRatings")
                or safe_get("ISO"),  # 兼容不同的ISO字段名
                flash=self._parse_flash(safe_get("Flash")),
                gps_latitude=None,  # 简化：暂时不处理GPS
                gps_longitude=None,
                gps_altitude=None,
                white_balance=self._parse_white_balance(safe_get("WhiteBalance")),
                exposure_mode=self._parse_exposure_mode(safe_get("ExposureMode")),
                metering_mode=self._parse_scene_type(
                    safe_get("SceneCaptureType")
                ),  # 修正字段名
            )

        except Exception as e:
            logger.debug(f"EXIF提取失败: {e}")
            return None

    def _extract_icc_profile(self, img: Image.Image) -> ICCProfile | None:
        """提取ICC配置文件信息"""
        try:
            icc_profile = img.info.get("icc_profile")
            if not icc_profile:
                return None

            # 这里可以使用专门的ICC解析库，如 colour-science
            # 目前提供基础实现
            return ICCProfile(
                profile_description="Unknown",
                color_space=self._guess_color_space(img.mode),
                profile_size=len(icc_profile),
                raw_profile=icc_profile,
            )

        except Exception as e:
            logger.debug(f"ICC配置文件提取失败: {e}")
            return None

    def _extract_histogram(self, img: Image.Image) -> HistogramData | None:
        """提取直方图数据 - 使用正确的Pillow API方法"""
        try:
            # 转换为RGB模式进行分析
            img_rgb = img.convert("RGB") if img.mode != "RGB" else img

            # 正确的方法：分离通道后分别计算直方图
            r_channel, g_channel, b_channel = img_rgb.split()
            red_hist = r_channel.histogram()
            green_hist = g_channel.histogram()
            blue_hist = b_channel.histogram()

            # 计算亮度直方图
            luminance_img = img_rgb.convert("L")
            luminance_hist = luminance_img.histogram()

            return HistogramData(
                red_histogram=red_hist,
                green_histogram=green_hist,
                blue_histogram=blue_hist,
                luminance_histogram=luminance_hist,
            )

        except Exception as e:
            logger.debug(f"直方图提取失败: {e}")
            return None

    def _calculate_complexity(self, img: Image.Image) -> ComplexityMetrics | None:
        """计算图片复杂度指标"""
        try:
            # 转换为RGB进行分析
            img_rgb = img.convert("RGB") if img.mode != "RGB" else img

            # 转换为numpy数组进行分析
            img_array = np.array(img_rgb)

            # 边缘密度 - 使用简单的梯度计算
            gray = np.mean(img_array, axis=2)
            grad_x = np.abs(np.diff(gray, axis=1))
            grad_y = np.abs(np.diff(gray, axis=0))
            edge_density = (np.mean(grad_x) + np.mean(grad_y)) / 255.0

            # 颜色多样性 - 计算唯一颜色数量
            reshaped = img_array.reshape(-1, 3)
            unique_colors = len(
                np.unique(
                    reshaped.view(np.dtype((np.void, reshaped.dtype.itemsize * 3)))
                )
            )
            total_pixels = img_array.shape[0] * img_array.shape[1]
            color_diversity = min(unique_colors / total_pixels, 1.0)

            # 纹理复杂度 - 使用标准差
            texture_complexity = np.std(gray) / 255.0

            # 压缩难度评分 - 综合指标
            compression_difficulty = (
                edge_density * 0.4 + color_diversity * 0.3 + texture_complexity * 0.3
            )

            return ComplexityMetrics(
                edge_density=float(edge_density),
                color_diversity=float(color_diversity),
                texture_complexity=float(texture_complexity),
                compression_difficulty=float(compression_difficulty),
            )

        except Exception as e:
            logger.debug(f"复杂度计算失败: {e}")
            return None

    # ========================================================================
    # 辅助解析方法
    # ========================================================================

    def _parse_gps_coordinates(
        self, gps_info: dict[str, Any]
    ) -> tuple[float | None, float | None]:
        """解析GPS坐标"""
        try:
            if "GPSLatitude" not in gps_info or "GPSLongitude" not in gps_info:
                return None, None

            lat = self._convert_gps_coordinate(
                gps_info["GPSLatitude"], gps_info.get("GPSLatitudeRef", "N")
            )
            lon = self._convert_gps_coordinate(
                gps_info["GPSLongitude"], gps_info.get("GPSLongitudeRef", "E")
            )

            return lat, lon

        except Exception:
            return None, None

    def _convert_gps_coordinate(
        self, coord: tuple[float, float, float], ref: str
    ) -> float:
        """转换GPS坐标格式"""
        degrees, minutes, seconds = coord
        decimal = float(degrees) + float(minutes) / 60 + float(seconds) / 3600
        if ref in ("S", "W"):
            decimal = -decimal
        return decimal

    def _parse_gps_altitude(self, gps_info: dict[str, Any]) -> float | None:
        """解析GPS海拔"""
        try:
            if "GPSAltitude" not in gps_info:
                return None
            altitude = float(gps_info["GPSAltitude"])
            if gps_info.get("GPSAltitudeRef", 0) == 1:
                altitude = -altitude
            return altitude
        except Exception:
            return None

    def _parse_datetime(self, dt_str: str | None) -> datetime | None:
        """解析EXIF日期时间"""
        if not dt_str:
            return None
        try:
            return datetime.strptime(dt_str, "%Y:%m:%d %H:%M:%S")
        except Exception:
            return None

    def _parse_focal_length(self, focal_length: Any) -> float | None:
        """解析焦距"""
        if focal_length is None:
            return None
        try:
            if isinstance(focal_length, tuple) and len(focal_length) == 2:
                return float(focal_length[0]) / float(focal_length[1])
            # 安全的类型转换
            if isinstance(focal_length, int | float | str):
                return float(focal_length)
            return None
        except Exception:
            return None

    def _parse_aperture(self, f_number: Any) -> float | None:
        """解析光圈值"""
        if f_number is None:
            return None
        try:
            if isinstance(f_number, tuple) and len(f_number) == 2:
                return float(f_number[0]) / float(f_number[1])
            # 安全的类型转换
            if isinstance(f_number, int | float | str):
                return float(f_number)
            return None
        except Exception:
            return None

    def _parse_shutter_speed(self, exposure_time: Any) -> str | None:
        """解析快门速度"""
        if exposure_time is None:
            return None
        try:
            if isinstance(exposure_time, tuple) and len(exposure_time) == 2:
                numerator, denominator = exposure_time
                if numerator == 1:
                    return f"1/{denominator}"
                return f"{numerator}/{denominator}"
            return str(exposure_time)
        except Exception:
            return None

    def _parse_flash(self, flash_value: Any) -> str | None:
        """解析闪光灯信息"""
        if flash_value is None:
            return None
        try:
            # Flash值的最低位表示是否使用闪光灯
            flash_fired = bool(int(flash_value) & 1)
            return "Fired" if flash_fired else "No Flash"
        except Exception:
            return None

    def _parse_white_balance(self, wb_value: Any) -> str | None:
        """解析白平衡"""
        if wb_value is None:
            return None
        wb_map = {0: "Auto", 1: "Manual"}
        return wb_map.get(wb_value, f"Unknown({wb_value})")

    def _parse_exposure_mode(self, exp_mode: Any) -> str | None:
        """解析曝光模式"""
        if exp_mode is None:
            return None
        exp_map = {0: "Auto", 1: "Manual", 2: "Auto bracket"}
        return exp_map.get(exp_mode, f"Unknown({exp_mode})")

    def _parse_scene_type(self, scene_type: Any) -> str | None:
        """解析场景类型"""
        if scene_type is None:
            return None
        scene_map = {
            0: "Standard",
            1: "Landscape",
            2: "Portrait",
            3: "Night scene",
            4: "Sports",
            5: "Close-up",
            6: "Fireworks",
        }
        return scene_map.get(scene_type, f"Unknown({scene_type})")

    def _guess_color_space(self, mode: str) -> str:
        """根据图片模式推测颜色空间"""
        mode_map = {
            "RGB": "RGB",
            "RGBA": "RGB",
            "CMYK": "CMYK",
            "L": "Grayscale",
            "LA": "Grayscale",
            "P": "Indexed",
        }
        return mode_map.get(mode, "Unknown")

    def _extract_xmp_data(self, img: Image.Image) -> dict[str, Any] | None:
        """提取XMP数据 - 基于Pillow 11的新功能

        支持WebP、PNG、TIFF、JPEG的XMP数据提取
        注意：需要Pillow 8.2.0+版本和defusedxml依赖
        """
        try:
            # 检查是否支持getxmp方法  # cspell:ignore getxmp
            if not hasattr(img, "getxmp"):
                return None

            # 检查是否有defusedxml依赖，避免警告
            if not HAS_DEFUSEDXML:
                # 没有defusedxml依赖，静默返回None
                logger.debug("XMP数据提取需要defusedxml依赖，跳过XMP提取")
                return None

            xmp_data = img.getxmp()
            if xmp_data:
                # XMP数据以字典形式返回，从"xmpmeta"键开始
                # 确保返回类型正确
                return dict(xmp_data) if isinstance(xmp_data, dict) else None
            return None
        except Exception as e:
            logger.debug(f"XMP数据提取失败: {e}")
            return None


# ========================================================================
# 统一的图片特征分析功能
# ========================================================================


def analyze_image_from_pil(img: Image.Image) -> ImageCharacteristics:
    """从 PIL Image 对象分析图片特征

    Args:
        img: PIL Image 对象

    Returns:
        ImageCharacteristics: 图片特征分析结果
    """
    try:
        # 转换为RGB进行分析
        img_rgb = img.convert("RGB") if img.mode != "RGB" else img

        # 使用直方图分析颜色分布
        histogram = img_rgb.histogram()

        # 计算非零颜色数量（更精确的颜色统计）
        non_zero_colors = sum(1 for count in histogram if count > 0)

        # 计算复杂度分数（统一算法）
        complexity_score = _calculate_unified_complexity_score(histogram)

        # 判断图片类型
        is_simple_graphic = non_zero_colors <= 48  # RGB 每通道16色
        is_photo_like = non_zero_colors > 3000

        return ImageCharacteristics(
            is_simple_graphic=is_simple_graphic,
            is_photo_like=is_photo_like,
            color_count=non_zero_colors,
            complexity_score=complexity_score,
            has_transparency=img.mode in ("RGBA", "LA") or "transparency" in img.info,
        )
    except Exception as e:
        logger.debug(f"PIL图片特征分析失败: {e}")
        return ImageCharacteristics(
            is_simple_graphic=False,
            is_photo_like=False,
            color_count=0,
            complexity_score=0.0,
            has_transparency=False,
        )


def analyze_image_from_metadata(metadata: ImageMetadata) -> ImageCharacteristics:
    """从图片元数据分析图片特征

    Args:
        metadata: 图片元数据

    Returns:
        ImageCharacteristics: 图片特征分析结果
    """
    complexity = metadata.complexity
    histogram = metadata.histogram

    # 基于复杂度元数据判断
    is_simple_graphic = False
    is_photo_like = False
    complexity_score = 0.0
    color_count = 0

    if complexity:
        # 基于复杂度判断
        is_simple_graphic = complexity.overall_complexity == "simple"
        is_photo_like = complexity.overall_complexity in ("moderate", "complex")

        # 基于颜色多样性判断
        if complexity.color_diversity < 0.1:
            is_simple_graphic = True
        elif complexity.color_diversity > 0.5:
            is_photo_like = True

        complexity_score = complexity.texture_complexity or 0.0

    # 基于亮度分布判断（照片通常有更均匀的亮度分布）
    if histogram:
        try:
            # 使用 getattr 来避免类型推断问题
            stats_dict = getattr(histogram, "brightness_stats", {})
            # 如果中间调比例较高，可能是照片
            if (
                stats_dict
                and isinstance(stats_dict, dict)
                and "mid_ratio" in stats_dict
                and stats_dict["mid_ratio"] > 0.3
            ):
                is_photo_like = True
        except Exception:
            pass  # 忽略亮度统计错误

    return ImageCharacteristics(
        is_simple_graphic=is_simple_graphic,
        is_photo_like=is_photo_like,
        color_count=color_count,
        complexity_score=complexity_score,
        has_transparency=metadata.basic_info.has_transparency,
    )


def _calculate_unified_complexity_score(histogram: list[int]) -> float:
    """统一的复杂度分数计算

    Args:
        histogram: RGB直方图数据

    Returns:
        float: 复杂度分数 (0.0-1.0)
    """
    try:
        # 计算直方图的标准差作为复杂度指标
        total_pixels = sum(histogram)
        if total_pixels == 0:
            return 0.0

        # 计算平均值
        mean = total_pixels / len(histogram)

        # 计算方差
        variance = sum((count - mean) ** 2 for count in histogram) / len(histogram)

        # 标准差归一化到 0-1 范围
        std_dev = (variance**0.5) / total_pixels

        return float(min(std_dev, 1.0))
    except Exception:
        return 0.0


# 便捷函数
def is_simple_graphic_pil(img: Image.Image) -> bool:
    """判断 PIL Image 是否为简单图形"""
    return analyze_image_from_pil(img).is_simple_graphic


def is_photo_like_pil(img: Image.Image) -> bool:
    """判断 PIL Image 是否为照片类图片"""
    return analyze_image_from_pil(img).is_photo_like


def is_simple_graphic_metadata(metadata: ImageMetadata) -> bool:
    """判断元数据对应的图片是否为简单图形"""
    return analyze_image_from_metadata(metadata).is_simple_graphic


def is_photo_like_metadata(metadata: ImageMetadata) -> bool:
    """判断元数据对应的图片是否为照片类图片"""
    return analyze_image_from_metadata(metadata).is_photo_like
