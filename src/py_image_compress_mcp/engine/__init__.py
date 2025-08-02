"""图像压缩处理引擎模块。

包含批量处理和配置构建等核心处理逻辑。
"""

from .batch import BatchProcessor
from .config import ConfigBuilder


__all__ = [
    "BatchProcessor",
    "ConfigBuilder",
]
