"""压缩参数优化器。

提供基于图像特征的智能压缩参数优化。
"""

from typing import Any

from ..models.compression_config import CompressionConfig, QualityMode
from ..models.image_metadata import ImageMetadata
from ..utils.logging_helpers import get_logger
from .image_info import analyze_image_from_metadata


logger = get_logger()


class CompressionOptimizer:
    """压缩参数优化器，基于图像特征智能调整压缩参数"""

    def __init__(self) -> None:
        """初始化优化器"""
        self.format_optimizers = {
            "JPEG": self._optimize_jpeg_params,
            "PNG": self._optimize_png_params,
            "WEBP": self._optimize_webp_params,
            "AVIF": self._optimize_avif_params,
            "HEIF": self._optimize_heif_params,
        }

    def optimize_parameters(
        self,
        format_name: str,
        config: CompressionConfig,
        metadata: ImageMetadata,
        base_params: dict[str, Any],
    ) -> dict[str, Any]:
        """优化压缩参数

        Args:
            format_name: 目标格式
            config: 压缩配置
            metadata: 图像元数据
            base_params: 基础参数

        Returns:
            dict[str, Any]: 优化后的参数
        """
        if format_name not in self.format_optimizers:
            return base_params

        try:
            optimizer = self.format_optimizers[format_name]
            return optimizer(config, metadata, base_params.copy())
        except Exception as e:
            logger.warning(f"参数优化失败: {e}")
            return base_params

    def _optimize_jpeg_params(
        self,
        config: CompressionConfig,
        metadata: ImageMetadata,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """优化JPEG参数，基于Pillow最佳实践 - 保守策略避免负优化"""
        basic = metadata.basic_info
        characteristics = analyze_image_from_metadata(metadata)
        quality = params.get("quality", 85)

        # 处理无损模式
        if config.quality_mode == QualityMode.LOSSLESS and basic.format == "JPEG":
            return {"optimize": True}  # 重置参数，只保留optimize

        # 基础优化设置
        self._apply_basic_jpeg_optimization(params, basic, quality)

        # 基于图像特征优化
        self._apply_jpeg_feature_optimization(params, characteristics, basic, quality)

        # 基于文件大小优化
        self._apply_jpeg_size_optimization(params, basic)

        # 添加重启标记优化
        self._apply_jpeg_restart_markers(params, basic, quality)

        return params

    def _apply_basic_jpeg_optimization(
        self, params: dict[str, Any], basic: Any, quality: int | str
    ) -> None:
        """应用基础JPEG优化"""
        file_size_mb = basic.file_size / (1024 * 1024)

        if basic.format == "JPEG":
            # 有损模式下的JPEG：谨慎使用optimize
            if file_size_mb > 1.0 or (isinstance(quality, int) and quality < 80):
                params["optimize"] = True
        else:
            # 对于从其他格式转换的图片，可以安全使用optimize
            params["optimize"] = True

    def _apply_jpeg_feature_optimization(
        self,
        params: dict[str, Any],
        characteristics: Any,
        basic: Any,
        quality: int | str,
    ) -> None:
        """基于图像特征优化JPEG参数"""
        if characteristics.is_photo_like:
            self._optimize_photo_jpeg(params, basic, quality)
        elif characteristics.is_simple_graphic:
            self._optimize_graphic_jpeg(params)

    def _optimize_photo_jpeg(
        self, params: dict[str, Any], basic: Any, quality: int | str
    ) -> None:
        """优化照片类JPEG"""
        if basic.width * basic.height > 2000000:  # 大于2MP
            # 大图片：使用渐进式JPEG
            params["progressive"] = True
            self._set_photo_subsampling(params, quality)
        else:
            # 小图片：优先质量，不使用渐进式
            params["subsampling"] = "4:4:4"

        # 高质量照片保持RGB色彩空间
        if isinstance(quality, int) and quality >= 95:
            params["keep_rgb"] = True

    def _set_photo_subsampling(
        self, params: dict[str, Any], quality: int | str
    ) -> None:
        """设置照片子采样策略"""
        if isinstance(quality, int) and quality >= 90:
            params["subsampling"] = "4:4:4"  # 无子采样，最高质量
        elif isinstance(quality, int) and quality >= 75:
            params["subsampling"] = "4:2:2"  # 水平子采样
        elif isinstance(quality, int):
            params["subsampling"] = "4:2:0"  # 标准子采样

    def _optimize_graphic_jpeg(self, params: dict[str, Any]) -> None:
        """优化图形类JPEG"""
        params["optimize"] = True
        params["progressive"] = False  # 简单图形不需要渐进式
        params["subsampling"] = "4:4:4"  # 禁用子采样保持锐利边缘

    def _apply_jpeg_size_optimization(self, params: dict[str, Any], basic: Any) -> None:
        """基于文件大小优化"""
        file_size_mb = basic.file_size / (1024 * 1024)
        if file_size_mb > 5.0:
            # 大文件：启用所有优化
            params["optimize"] = True
            params["progressive"] = True

    def _apply_jpeg_restart_markers(
        self, params: dict[str, Any], basic: Any, quality: int | str
    ) -> None:
        """添加重启标记优化"""
        if (
            basic.width * basic.height > 4000000
            and isinstance(quality, int)
            and quality >= 80
        ):  # 4MP以上高质量图片
            params["restart_marker_blocks"] = 64  # 每64个MCU块添加重启标记

    def _optimize_png_params(
        self,
        config: CompressionConfig,  # noqa: ARG002
        metadata: ImageMetadata,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """优化PNG参数，基于Pillow最佳实践"""
        basic = metadata.basic_info
        characteristics = analyze_image_from_metadata(metadata)

        # 基于图像特征调整压缩级别
        if characteristics.is_simple_graphic:
            # 简单图形：使用最高压缩级别
            params["compress_level"] = 9
            params["optimize"] = True
            # 简单图形可能适合较少的位深度
            if not basic.has_transparency and basic.mode in ("RGB", "L"):
                params["bits"] = 8  # 确保足够的颜色深度
        elif characteristics.is_photo_like:
            # 照片类：平衡压缩速度和效果
            params["compress_level"] = 6
            params["optimize"] = True  # 照片也启用优化
        else:
            # 其他类型：标准压缩
            params["compress_level"] = 7
            params["optimize"] = True

        # 基于图像尺寸调整
        pixel_count = basic.width * basic.height
        if pixel_count > 4000000:  # 大于4MP
            # 大图片：降低压缩级别以提高速度，但仍保持优化
            params["compress_level"] = min(params["compress_level"], 6)
        elif pixel_count < 100000:  # 小于0.1MP的小图片
            # 小图片：可以使用最高压缩级别
            params["compress_level"] = 9

        # 透明度优化
        if basic.has_transparency:
            params["optimize"] = True
            # 对于有透明度的图像，确保使用适当的位深度
            if basic.mode == "RGBA":
                params["bits"] = 8  # RGBA需要8位

        # 基于文件大小进一步优化
        file_size_mb = basic.file_size / (1024 * 1024)
        if file_size_mb > 2.0:
            # 大文件：使用最高压缩级别
            params["compress_level"] = 9
            params["optimize"] = True

        return params

    def _optimize_webp_params(
        self,
        config: CompressionConfig,  # noqa: ARG002
        metadata: ImageMetadata,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """优化WebP参数，基于Pillow最佳实践"""
        if params.get("lossless"):
            return self._optimize_webp_lossless_params(metadata, params)
        return self._optimize_webp_lossy_params(metadata, params)

    def _optimize_webp_lossless_params(
        self, metadata: ImageMetadata, params: dict[str, Any]
    ) -> dict[str, Any]:
        """优化无损WebP参数"""
        basic = metadata.basic_info
        characteristics = analyze_image_from_metadata(metadata)

        params["exact"] = True
        params["method"] = 6  # 最佳压缩方法

        # 基于图像特征调整
        if characteristics.is_simple_graphic:
            params["quality"] = 100  # 无损模式下，quality控制压缩努力程度
        elif basic.width * basic.height > 2000000:
            params["method"] = 4
            params["quality"] = 80  # 平衡压缩时间
        else:
            params["quality"] = 90

        return params

    def _optimize_webp_lossy_params(
        self, metadata: ImageMetadata, params: dict[str, Any]
    ) -> dict[str, Any]:
        """优化有损WebP参数"""
        basic = metadata.basic_info
        characteristics = analyze_image_from_metadata(metadata)
        quality = params.get("quality", 80)

        # 基于图像特征调整
        if characteristics.is_photo_like:
            self._apply_webp_photo_settings(params, quality)
        elif characteristics.is_simple_graphic:
            self._apply_webp_graphic_settings(params)
        else:
            self._apply_webp_general_settings(params, quality)

        # 透明度和文件大小优化
        self._apply_webp_transparency_optimization(params, basic, quality)
        self._apply_webp_size_optimization(params, basic)

        return params

    def _apply_webp_photo_settings(self, params: dict[str, Any], quality: int) -> None:
        """应用照片类WebP设置"""
        params.update(
            {
                "method": 6,
                "segments": 4,
                "sns_strength": 50,
                "filter_strength": 60,
                "filter_sharpness": 0,
                "filter_type": 1,
            }
        )
        # 根据质量调整编码通道数
        if quality >= 90:
            params["pass"] = 10
        elif quality >= 70:
            params["pass"] = 6
        else:
            params["pass"] = 4

    def _apply_webp_graphic_settings(self, params: dict[str, Any]) -> None:
        """应用简单图形WebP设置"""
        params.update(
            {
                "method": 6,
                "segments": 1,
                "filter_type": 0,  # 简单滤波器
                "pass": 6,  # 适中的编码通道数
            }
        )

    def _apply_webp_general_settings(
        self, params: dict[str, Any], quality: int
    ) -> None:
        """应用通用WebP设置"""
        if quality >= 90:
            params["pass"] = 10
            params["alpha_quality"] = min(100, quality + 5)
        elif quality >= 70:
            params["pass"] = 6
            params["alpha_quality"] = quality
        else:
            params["pass"] = 4
            params["alpha_quality"] = max(50, quality - 10)

    def _apply_webp_transparency_optimization(
        self, params: dict[str, Any], basic: Any, quality: int
    ) -> None:
        """应用WebP透明度优化"""
        if basic.has_transparency:
            alpha_quality = params.get("alpha_quality", quality)
            params["alpha_quality"] = max(alpha_quality, 80)

    def _apply_webp_size_optimization(self, params: dict[str, Any], basic: Any) -> None:
        """应用WebP文件大小优化"""
        file_size_mb = basic.file_size / (1024 * 1024)
        if file_size_mb > 3.0:
            params["autofilter"] = True
            params["method"] = 6
        elif file_size_mb < 0.5:
            params["method"] = 6

    def estimate_compression_ratio(
        self, format_name: str, metadata: ImageMetadata, quality: int | None = None
    ) -> float:
        """估算压缩比

        Args:
            format_name: 目标格式
            metadata: 图像元数据
            quality: 质量设置

        Returns:
            float: 估算的压缩比（0-1之间）
        """
        try:
            basic = metadata.basic_info
            characteristics = analyze_image_from_metadata(metadata)

            # 基础压缩比估算
            base_ratio = {
                "JPEG": 0.1 if characteristics.is_photo_like else 0.2,
                "PNG": 0.3 if characteristics.is_simple_graphic else 0.6,
                "WEBP": 0.08 if characteristics.is_photo_like else 0.15,
            }.get(format_name, 0.5)

            # 基于质量调整
            if quality is not None:
                quality_factor = quality / 100.0
                if format_name == "JPEG":
                    base_ratio *= 0.5 + quality_factor * 0.5
                elif format_name == "WEBP" and quality < 100:
                    base_ratio *= 0.3 + quality_factor * 0.7

            # 基于图像特征调整
            if characteristics.is_simple_graphic:
                base_ratio *= 0.7  # 简单图形压缩更好
            elif characteristics.is_photo_like:
                base_ratio *= 1.2  # 照片压缩相对较差

            # 基于透明度调整
            if basic.has_transparency:
                base_ratio *= 1.3  # 透明图片通常更大

            return min(1.0, max(0.05, base_ratio))

        except Exception as e:
            logger.warning(f"压缩比估算失败: {e}")
            return 0.5  # 默认估算值

    def _optimize_avif_params(
        self,
        config: CompressionConfig,  # noqa: ARG002
        metadata: ImageMetadata,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """优化AVIF参数，基于Pillow 11的AVIF支持"""
        basic = metadata.basic_info
        characteristics = analyze_image_from_metadata(metadata)
        quality = params.get("quality", 80)

        # 基于图像特征调整速度参数
        if characteristics.is_photo_like:
            # 照片类图像：优先质量
            if basic.width * basic.height > 4000000:  # 大于4MP
                params["speed"] = 4  # 平衡速度和质量
            else:
                params["speed"] = 2  # 优先质量
        elif characteristics.is_simple_graphic:
            # 简单图形：可以使用较慢的设置获得更好压缩
            params["speed"] = 1  # 最佳质量
        else:
            # 其他类型：标准设置
            params["speed"] = 4

        # 高质量时的特殊处理
        if quality and quality >= 95:
            params["speed"] = 1  # 最佳质量设置

        return params

    def _optimize_heif_params(
        self,
        config: CompressionConfig,  # noqa: ARG002
        metadata: ImageMetadata,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """优化HEIF参数，基于Pillow 11的HEIF支持"""
        characteristics = analyze_image_from_metadata(metadata)
        quality = params.get("quality", 80)

        # HEIF参数相对简单，主要是质量控制
        # 基于图像特征进行微调
        if characteristics.is_photo_like and quality and quality < 90:
            # 照片类图像可以适当提高质量
            params["quality"] = min(100, quality + 5)
        elif characteristics.is_simple_graphic and quality and quality > 70:
            # 简单图形可以适当降低质量而不影响视觉效果
            params["quality"] = max(70, quality - 5)

        return params
