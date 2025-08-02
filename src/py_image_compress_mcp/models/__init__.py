"""数据模型包。

定义图片处理相关的数据结构和模型。
"""

from .compression_config import (
    CompressionConfig,
    CompressionDecision,
    CompressionValidators,
    QualityMode,
    ResizeConfig,
    StrategyType,
    # ValidationError 已移至 exceptions 模块
)
from .compression_result import (
    BatchResult,
    CompressionResult,
    ImageInfoResponse,
    MultiFormatResult,
    ProcessingResult,
)
from .constants import (
    ImageFormats,
    ProcessingDefaults,
    QualityDefaults,
    ValidationLimits,
    get_extension,
    get_format_alias,
    get_mime_type,
    is_lossless_format,
    supports_transparency,
)
from .image_metadata import (
    BasicImageInfo,
    ComplexityMetrics,
    ExifData,
    HistogramData,
    ICCProfile,
    ImageCharacteristics,
    ImageMetadata,
)


__all__ = [
    # 核心模型
    "BasicImageInfo",
    "BatchResult",
    "ComplexityMetrics",
    "CompressionConfig",
    "CompressionDecision",
    "CompressionResult",
    # 验证器
    "CompressionValidators",
    "ExifData",
    "HistogramData",
    "ICCProfile",
    "ImageCharacteristics",
    # 常量和工具
    "ImageFormats",
    # 类型定义
    "ImageInfoResponse",
    "ImageMetadata",
    "MultiFormatResult",
    "ProcessingDefaults",
    "ProcessingResult",
    "QualityDefaults",
    "QualityMode",
    "ResizeConfig",
    "StrategyType",
    "ValidationLimits",
    "get_extension",
    "get_format_alias",
    "get_mime_type",
    "is_lossless_format",
    "supports_transparency",
    # "ValidationError" 已移至 exceptions 模块
]
