"""现代化 Python 图像压缩库。

基于 Pillow 11 现代 API 的高效图像压缩解决方案。
"""

__version__ = "0.3.0"
__author__ = "crper"
__description__ = "现代化图像压缩库，基于 Pillow 11"

# 核心功能导出
from .compressor import ImageCompressor, compress_universal
from .models.compression_result import BatchResult, CompressionResult, MultiFormatResult


__all__ = [
    "BatchResult",
    "CompressionResult",
    "ImageCompressor",
    "MultiFormatResult",
    "compress_universal",
    "get_version",
]


def get_version() -> str:
    """获取版本号。"""
    return __version__
