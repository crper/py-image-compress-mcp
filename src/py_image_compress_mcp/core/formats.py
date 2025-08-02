"""格式处理器模块。

图片格式处理和转换，优化不同格式的输出效果。
"""

import logging
from typing import Any

from PIL import Image

from ..models.compression_config import CompressionConfig
from .image_info import ImageCharacteristics, analyze_image_from_pil


logger = logging.getLogger(__name__)


class FormatProcessor:
    """格式处理器 - 充分利用 Pillow 11 的现代化特性"""

    def __init__(self) -> None:
        """初始化格式处理器"""
        # 动态获取支持的格式
        self.supported_formats = {
            fmt.upper() for fmt in Image.registered_extensions().values() if fmt
        }

        # 检测现代格式支持（Pillow 11 新特性）
        self.avif_supported = self._check_format_support("AVIF")
        self.heif_supported = self._check_format_support("HEIF")

        logger.debug(f"支持的格式: {sorted(self.supported_formats)}")
        if self.avif_supported:
            logger.debug("✅ AVIF 格式支持已启用")
        if self.heif_supported:
            logger.debug("✅ HEIF 格式支持已启用")

    def _check_format_support(self, format_name: str) -> bool:
        """检查特定格式是否支持"""
        try:
            # 首先检查格式是否在注册的扩展名中
            if format_name.upper() not in self.supported_formats:
                return False

            # 尝试创建一个小的测试图像来检查格式支持
            from io import BytesIO

            test_img = Image.new("RGB", (1, 1), color="red")
            buffer = BytesIO()
            test_img.save(buffer, format=format_name)
            buffer.seek(0)

            # 尝试重新打开以确保完整支持
            Image.open(buffer)
            return True
        except Exception as e:
            logger.debug(f"格式 {format_name} 不支持: {e}")
            return False

    def prepare_for_format(self, img: Image.Image, target_format: str) -> Image.Image:
        """为目标格式准备图片

        Args:
            img: PIL图片对象
            target_format: 目标格式

        Returns:
            Image.Image: 处理后的图片对象
        """
        if target_format not in self.supported_formats:
            logger.warning(f"不支持的格式: {target_format}, 使用JPEG")
            target_format = "JPEG"

        match target_format:
            case "JPEG":
                return self._prepare_for_jpeg(img)
            case "PNG":
                return self._prepare_for_png(img)
            case "WEBP":
                return self._prepare_for_webp(img)
            case "AVIF" if self.avif_supported:
                return self._prepare_for_avif(img)
            case "HEIF" if self.heif_supported:
                return self._prepare_for_heif(img)
            case _:
                return img

    def _prepare_for_jpeg(self, img: Image.Image) -> Image.Image:
        """为JPEG格式准备图片，使用更严谨的色彩空间处理"""
        # JPEG不支持透明度，需要转换为RGB
        if img.mode in ("RGBA", "LA", "P"):
            # 智能背景色选择：分析图像边缘来确定最佳背景色
            background_color = self._get_optimal_background_color(img)
            background = Image.new("RGB", img.size, background_color)

            if img.mode == "P":
                # 调色板模式：检查是否有透明色
                if "transparency" in img.info:
                    # 有透明色，转换为RGBA处理
                    img = img.convert("RGBA")
                else:
                    # 无透明色，直接转换为RGB
                    return img.convert("RGB")

            if img.mode in ("RGBA", "LA"):
                # 使用alpha通道进行合成
                if img.mode == "LA":
                    # 灰度+alpha转换为RGBA
                    img = img.convert("RGBA")

                # 使用更精确的alpha合成
                alpha = img.split()[-1]
                # 预乘alpha以获得更好的合成效果
                rgb_img = Image.new("RGB", img.size, background_color)
                rgb_img.paste(img, mask=alpha)
                return rgb_img

            background.paste(img)
            return background

        # 处理其他色彩模式
        if img.mode == "CMYK":
            # CMYK转RGB需要特殊处理
            return img.convert("RGB")

        if img.mode in ("L", "1"):
            # 灰度和二值图像转RGB
            return img.convert("RGB")

        if img.mode != "RGB":
            # 其他模式转换为RGB
            return img.convert("RGB")

        return img

    def _get_optimal_background_color(self, img: Image.Image) -> tuple[int, int, int]:
        """智能选择最佳背景色，基于图像边缘分析 - 优化版本"""
        try:
            # 如果图像有透明通道，分析边缘像素
            if img.mode not in ("RGBA", "LA"):
                return (255, 255, 255)  # 默认白色背景

            edge_pixels = self._sample_edge_pixels(img)

            # 如果有足够的边缘像素，计算平均色
            if len(edge_pixels) >= 3:  # 降低阈值，更容易获得背景色
                return self._calculate_average_color(edge_pixels)

            # 默认使用白色背景
            return (255, 255, 255)

        except Exception:
            # 出错时使用白色背景
            return (255, 255, 255)

    def _sample_edge_pixels(self, img: Image.Image) -> list[tuple[int, int, int]]:
        """采样图像边缘像素"""
        width, height = img.size
        edge_pixels: list[tuple[int, int, int]] = []

        # 优化的边缘采样：减少采样点数，提高性能
        sample_step = max(1, min(width, height) // 10)  # 自适应采样步长

        # 采样边缘像素（上下左右边缘）
        for x in range(0, width, sample_step):
            # 上边缘和下边缘
            for y in [0, height - 1]:
                pixel = img.getpixel((x, y))
                if (
                    isinstance(pixel, tuple | list)
                    and len(pixel) >= 4
                    and pixel[-1] > 128
                ):
                    # 确保类型安全的转换
                    rgb_pixel = (int(pixel[0]), int(pixel[1]), int(pixel[2]))
                    edge_pixels.append(rgb_pixel)

        for y in range(0, height, sample_step):
            # 左边缘和右边缘
            for x in [0, width - 1]:
                pixel = img.getpixel((x, y))
                if (
                    isinstance(pixel, tuple | list)
                    and len(pixel) >= 4
                    and pixel[-1] > 128
                ):
                    # 确保类型安全的转换
                    rgb_pixel = (int(pixel[0]), int(pixel[1]), int(pixel[2]))
                    edge_pixels.append(rgb_pixel)

        return edge_pixels

    def _calculate_average_color(
        self, edge_pixels: list[tuple[int, int, int]]
    ) -> tuple[int, int, int]:
        """计算边缘像素的平均颜色"""
        avg_r = sum(p[0] for p in edge_pixels) // len(edge_pixels)
        avg_g = sum(p[1] for p in edge_pixels) // len(edge_pixels)
        avg_b = sum(p[2] for p in edge_pixels) // len(edge_pixels)
        return (avg_r, avg_g, avg_b)

    def _prepare_for_png(self, img: Image.Image) -> Image.Image:
        """为PNG格式准备图片，优化色彩模式以获得更好的压缩效果"""
        # PNG支持多种色彩模式，选择最优的模式
        if img.mode == "P":
            # 调色板模式，检查是否有透明度
            if "transparency" in img.info:
                return img.convert("RGBA")
            return img.convert("RGB")

        # 对于CMYK模式，转换为RGB
        if img.mode == "CMYK":
            return img.convert("RGB")

        # 对于1位模式，保持原样（PNG支持且压缩效果好）
        if img.mode == "1":
            return img

        # 灰度图像优化：如果是伪灰度的RGB图像，转换为真正的灰度
        if img.mode == "RGB" and self._is_grayscale_image(img):
            return img.convert("L")

        # 其他模式保持不变，PNG都支持
        return img

    def _is_grayscale_image(self, img: Image.Image) -> bool:
        """检测RGB图像是否实际上是灰度图像"""
        try:
            # 采样检测：检查图像的一些像素点
            width, height = img.size
            sample_size = min(100, width * height // 100)  # 采样1%的像素，最多100个

            for _ in range(sample_size):
                x = (width * _) // sample_size
                y = (height * _) // sample_size
                pixel = img.getpixel((x, y))

                # 处理不同的像素格式
                if isinstance(pixel, int | float):
                    # 单通道灰度图，已经是灰度
                    continue
                if isinstance(pixel, tuple | list) and len(pixel) >= 3:
                    r, g, b = pixel[:3]
                    # 如果R、G、B值不相等，则不是灰度图像
                    if not (r == g == b):
                        return False
                else:
                    # 未知格式，假设不是灰度
                    return False

            return True
        except Exception:
            return False

    def _prepare_for_webp(self, img: Image.Image) -> Image.Image:
        """为WebP格式准备图片"""
        # WebP支持RGB和RGBA
        if img.mode == "P":
            # 调色板模式，检查是否有透明度
            if "transparency" in img.info:
                return img.convert("RGBA")
            return img.convert("RGB")
        if img.mode == "LA":
            # 灰度+alpha转换为RGBA
            return img.convert("RGBA")
        if img.mode == "L":
            # 灰度转换为RGB
            return img.convert("RGB")

        # RGB和RGBA保持不变
        return img

    def _prepare_for_avif(self, img: Image.Image) -> Image.Image:
        """为AVIF格式准备图片

        AVIF是现代高效格式，支持RGB、RGBA，压缩效果优于WebP。
        """
        if img.mode == "P":
            # 调色板模式，检查是否有透明度
            if "transparency" in img.info:
                return img.convert("RGBA")
            return img.convert("RGB")
        if img.mode == "LA":
            # 灰度+alpha转换为RGBA
            return img.convert("RGBA")
        if img.mode == "L":
            # 灰度转换为RGB
            return img.convert("RGB")

        # RGB和RGBA保持不变
        return img

    def _prepare_for_heif(self, img: Image.Image) -> Image.Image:
        """为HEIF格式准备图片

        HEIF是Apple推广的现代格式，压缩效果好。
        """
        if img.mode == "P":
            # 调色板模式，检查是否有透明度
            if "transparency" in img.info:
                return img.convert("RGBA")
            return img.convert("RGB")
        if img.mode == "LA":
            # 灰度+alpha转换为RGBA
            return img.convert("RGBA")
        if img.mode == "L":
            # 灰度转换为RGB
            return img.convert("RGB")

        # RGB和RGBA保持不变
        return img

    def get_optimal_format(self, img: Image.Image, prefer_quality: bool = True) -> str:
        """根据图片特征推荐最优格式（兼容性方法）

        Args:
            img: PIL图片对象
            prefer_quality: 是否优先考虑质量

        Returns:
            str: 推荐的格式
        """
        # 分析图片特征
        characteristics = analyze_image_from_pil(img)

        # 检查透明度
        has_transparency = img.mode in ("RGBA", "LA") or "transparency" in img.info

        # 使用统一的格式推荐逻辑
        return self.get_optimal_format_from_characteristics(
            characteristics=characteristics,
            has_transparency=has_transparency,
            prefer_quality=prefer_quality,
        )

    def get_optimal_format_from_characteristics(
        self,
        characteristics: ImageCharacteristics,
        has_transparency: bool = False,
        user_preference: str | None = None,
        prefer_quality: bool = True,
    ) -> str:
        """根据图片特征建议最优格式（统一接口）

        Args:
            characteristics: 图片特征分析结果
            has_transparency: 是否有透明度
            user_preference: 用户偏好格式
            prefer_quality: 是否优先考虑质量

        Returns:
            str: 推荐的格式
        """
        if user_preference:
            return user_preference.upper()

        # 有透明度的图片
        if has_transparency:
            return self._select_format_for_transparency(prefer_quality)

        # 简单图形优先PNG
        if characteristics.is_simple_graphic:
            return self._select_format_for_graphics()

        # 复杂图片（照片类）优先现代格式
        if characteristics.is_photo_like:
            return self._select_format_for_photos(prefer_quality)

        # 默认选择最佳现代格式
        return self._select_default_modern_format()

    def _select_format_for_transparency(self, prefer_quality: bool) -> str:
        """为有透明度的图片选择最优格式"""
        if prefer_quality:
            return "PNG"
        if self.avif_supported:
            return "AVIF"  # AVIF 对透明度支持更好
        return "WEBP"

    def _select_format_for_graphics(self) -> str:
        """为简单图形选择最优格式"""
        return "PNG"  # 简单图形PNG效果最佳

    def _select_format_for_photos(self, prefer_quality: bool) -> str:
        """为照片类图片选择最优格式"""
        if prefer_quality and self.avif_supported:
            return "AVIF"  # AVIF 压缩效果最佳
        if self.heif_supported:
            return "HEIF"  # HEIF 也是不错的选择
        return "JPEG"

    def _select_default_modern_format(self) -> str:
        """选择默认的现代格式"""
        if self.avif_supported:
            return "AVIF"
        if self.heif_supported:
            return "HEIF"
        return "WEBP"


def get_save_parameters(
    format_name: str, config: CompressionConfig
) -> tuple[dict[str, Any], int | None]:
    """获取保存参数，简化处理逻辑

    Returns:
        tuple: (保存参数字典, 实际使用的质量值)
    """
    params: dict[str, Any] = {}  # 不包含format，由调用方处理
    quality = config.effective_quality
    actual_quality = quality  # 默认实际质量等于配置质量

    match format_name:
        case "JPEG":
            jpeg_params, actual_quality = get_jpeg_params(quality, config)
            params.update(jpeg_params)
        case "PNG":
            params.update(get_png_params(quality, config))
            # PNG的"质量"通过颜色量化实现，保持原始质量值
        case "WEBP":
            params.update(get_webp_params(quality, config))
        case "AVIF":
            params.update(get_avif_params(quality, config))
        case "HEIF":
            params.update(get_heif_params(quality, config))

    return params, actual_quality


def get_jpeg_params(
    quality: int | None, config: CompressionConfig
) -> tuple[dict[str, Any], int | None]:
    """获取JPEG压缩参数

    基于Pillow 11文档的最佳实践：
    - quality: 0-95 推荐范围，100会禁用部分JPEG压缩算法
    - optimize: 额外处理以找到最优编码设置
    - progressive: 渐进式JPEG，适合网络传输
    - subsampling: 色度子采样，影响质量和文件大小
    - quality='keep': 保持原始JPEG参数（真正的无损优化）
    """
    # 无损模式：JPEG本身是有损格式，需要智能处理
    if quality is None:
        # 检查是否为JPEG输入文件
        if config.input_path.suffix.lower() in {".jpg", ".jpeg"}:
            # 对于JPEG输入，返回特殊标记表示应该跳过处理
            logger.info("JPEG输入文件，无损模式下跳过处理以避免质量损失")
            return {"skip_processing": True}, None
        # 非JPEG输入转JPEG：检查是否为现代高效格式
        input_ext = config.input_path.suffix.lower()
        if input_ext in {".webp", ".avif", ".heif"}:
            # 现代格式转JPEG通常会变大，建议跳过或使用低质量
            logger.warning(f"将高效格式{input_ext}转换为JPEG可能导致文件变大")
            # 使用较低质量以控制文件大小
            jpeg_quality = 75
        else:
            # 传统格式（PNG等）转JPEG，使用适中质量
            jpeg_quality = 85
    else:
        # 直接使用用户指定的质量值，但限制在合理范围内
        jpeg_quality = max(1, min(100, quality))

        # 质量100的特殊处理（根据Pillow文档，100会禁用部分算法）
        if jpeg_quality == 100:
            logger.warning(
                "JPEG质量100会禁用部分压缩算法，可能导致文件过大。建议使用95-98"
            )
            # 强制降低到98以避免文件过大
            jpeg_quality = 98
            logger.info("自动调整质量从100到98以优化文件大小")

    # 基础参数 - 无损模式避免 progressive 以防文件变大
    params = {
        "quality": jpeg_quality,
        "optimize": config.optimize,
        "progressive": config.progressive if quality is not None else False,
    }

    # 色度子采样设置（基于Pillow 11文档）
    # 智能子采样策略：平衡质量和文件大小
    if quality is None and config.input_path.suffix.lower() in {".jpg", ".jpeg"}:
        # JPEG输入的无损模式：不设置subsampling，让Pillow保持最佳设置
        pass  # 不设置subsampling参数
    elif jpeg_quality >= 95:
        # 极高质量：使用适度子采样避免文件过大
        params["subsampling"] = 1  # "4:2:2" - 水平子采样，质量高但文件不会过大
    elif jpeg_quality >= 85:
        params["subsampling"] = 1  # "4:2:2" - 水平子采样
    else:
        params["subsampling"] = 2  # "4:2:0" - 标准子采样，最佳压缩

    # 元数据控制，简化设计
    if config.strip_metadata:
        # 移除所有元数据
        params["exif"] = b""  # type: ignore[assignment]
        params["icc_profile"] = None  # type: ignore[assignment]

    return params, jpeg_quality


def get_png_params(quality: int | None, config: CompressionConfig) -> dict[str, Any]:
    """获取PNG压缩参数

    PNG支持无损和有损压缩：
    - 无损模式：使用最佳压缩级别，不进行颜色量化
    - 有损模式：通过颜色量化实现，在compression_engine中处理
    基于Pillow文档建议：
    - optimize=True时，compress_level会被设为9（最佳压缩）
    """
    if quality is None:
        # 无损模式：使用最佳压缩级别
        compress_level = 9
        logger.debug("PNG无损压缩，使用最佳压缩级别")
    else:
        # 有损模式：仍然使用较高的压缩级别，颜色量化在引擎中处理
        compress_level = 9  # PNG的压缩级别与颜色量化是独立的
        logger.debug(f"PNG有损压缩，质量={quality}，将进行颜色量化")

    return {
        "optimize": config.optimize,
        "compress_level": compress_level,
        "bits": 8,  # 默认 8 位深度
    }


def get_webp_params(quality: int | None, config: CompressionConfig) -> dict[str, Any]:
    """获取WebP压缩参数

    基于Pillow文档建议：
    - 无损模式：lossless=True, quality控制压缩努力程度(0=快速,100=最佳)
    - 有损模式：quality控制图像质量(0=最小,100=最大)
    - method参数：0=快速，6=最慢但最佳压缩
    - alpha_quality：控制透明通道质量，100为无损
    """
    _ = config  # 标记参数已使用，避免警告

    if quality is None:
        # 无损 WebP - 使用保守参数避免文件变大
        # WebP无损对简单图形和小文件效果较差，使用低effort
        return {
            "lossless": True,
            "quality": 30,  # 降低effort，避免过度优化导致文件变大
            "method": 2,  # 使用较快的方法，避免过度压缩
            "exact": True,  # 精确无损，保持透明RGB值
        }

    # 有损 WebP
    webp_quality = max(1, min(100, quality))
    params = {
        "quality": webp_quality,
        "method": 6,  # 最佳压缩方法（较慢但效果好）
    }

    # 根据Pillow文档，alpha_quality控制透明通道压缩
    # 高质量时保持透明通道无损或接近无损
    if webp_quality >= 85:
        params["alpha_quality"] = 100  # 透明通道无损
    elif webp_quality >= 70:
        params["alpha_quality"] = min(100, webp_quality + 10)
    else:
        params["alpha_quality"] = webp_quality

    return params


def get_avif_params(quality: int | None, config: CompressionConfig) -> dict[str, Any]:
    """获取AVIF压缩参数

    AVIF是现代高效格式，基于AV1编码，压缩效果优于WebP。
    """
    _ = config  # 标记参数已使用，避免警告

    if quality is None:
        # 无损 AVIF
        return {
            "lossless": True,
            "quality": 100,
            "speed": 4,  # 平衡速度和压缩效果 (0=最慢最佳, 10=最快)
        }

    # 有损 AVIF
    avif_quality = max(1, min(100, quality))
    params = {
        "quality": avif_quality,
    }

    # 根据质量调整速度参数
    if avif_quality >= 90:
        params["speed"] = 2  # 高质量，较慢速度
    elif avif_quality >= 70:
        params["speed"] = 4  # 平衡速度和质量
    else:
        params["speed"] = 6  # 优先速度

    # 添加其他官方支持的参数
    if avif_quality >= 95:
        # 高质量时使用更好的子采样
        params["subsampling"] = "4:4:4"  # type: ignore[assignment]
    elif avif_quality >= 80:
        params["subsampling"] = "4:2:2"  # type: ignore[assignment]
    else:
        params["subsampling"] = "4:2:0"  # type: ignore[assignment]

    return params


def get_heif_params(quality: int | None, config: CompressionConfig) -> dict[str, Any]:
    """获取HEIF压缩参数

    HEIF是Apple推广的现代格式，基于HEVC编码。
    注意：需要 pillow-heif 插件支持，标准 Pillow 不包含 HEIF 支持。
    """
    _ = config  # 标记参数已使用，避免警告

    if quality is None:
        # 高质量 HEIF（接近无损）
        return {
            "quality": 100,
        }

    # 有损 HEIF
    heif_quality = max(1, min(100, quality))
    return {
        "quality": heif_quality,
    }
