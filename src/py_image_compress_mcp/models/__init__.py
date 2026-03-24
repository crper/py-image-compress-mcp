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
    get_format_alias,
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
    "ProcessingResult",
    "QualityMode",
    "ResizeConfig",
    "StrategyType",
    "get_format_alias",
    # "ValidationError" 已移至 exceptions 模块
]
