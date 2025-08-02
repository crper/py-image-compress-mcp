"""核心模块包。

现代化图像压缩核心功能模块，包含统一的图片分析功能。
"""

# 核心功能模块导入
# 从模型模块导入
from ..models.image_metadata import ImageMetadata
from .compression_engine import process_image
from .formats import FormatProcessor
from .image_info import (
    ImageCharacteristics,
    ImageInfoExtractor,
    analyze_image_from_metadata,
    analyze_image_from_pil,
    is_photo_like_metadata,
    is_photo_like_pil,
    is_simple_graphic_metadata,
    is_simple_graphic_pil,
)
from .strategy import CompressionStrategy, StrategyType


__all__ = [
    "CompressionStrategy",
    "FormatProcessor",
    "ImageCharacteristics",
    "ImageInfoExtractor",
    "ImageMetadata",
    "StrategyType",
    "analyze_image_from_metadata",
    "analyze_image_from_pil",
    "is_photo_like_metadata",
    "is_photo_like_pil",
    "is_simple_graphic_metadata",
    "is_simple_graphic_pil",
    "process_image",
]
