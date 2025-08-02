"""图像处理相关常量定义。

基于 Pillow 动态能力的图像格式管理，避免硬编码重复。
"""

from typing import Final

from PIL import Image


class ImageFormats:
    """基于 Pillow 的动态图像格式管理"""

    # 只定义必要的别名映射（用户友好的别名）
    ALIASES: Final[dict[str, str]] = {
        "JPG": "JPEG",  # 最常见的别名
    }

    # 只定义 Pillow 未提供的特殊 MIME 类型
    SPECIAL_MIME_TYPES: Final[dict[str, str]] = {
        "ICO": "image/x-icon",
        "PPM": "image/x-portable-pixmap",
        "PGM": "image/x-portable-graymap",
        "PBM": "image/x-portable-bitmap",
    }

    # 只定义首选扩展名（当 Pillow 有多个选择时）
    PREFERRED_EXTENSIONS: Final[dict[str, str]] = {
        "JPEG": ".jpg",  # 而不是 .jpeg
        "TIFF": ".tiff",  # 而不是 .tif
    }

    # 业务相关的格式分类
    COMMON_FORMATS: Final[list[str]] = ["JPEG", "PNG", "WEBP"]
    TRANSPARENCY_FORMATS: Final[set[str]] = {"PNG", "WEBP", "GIF", "TIFF"}
    LOSSLESS_FORMATS: Final[set[str]] = {"PNG", "GIF", "BMP", "TIFF"}

    @classmethod
    def get_supported_formats(cls) -> set[str]:
        """动态获取 Pillow 支持的所有格式"""
        return {fmt.upper() for fmt in Image.registered_extensions().values() if fmt}

    @classmethod
    def get_supported_extensions(cls) -> set[str]:
        """动态获取 Pillow 支持的所有扩展名"""
        return set(Image.registered_extensions().keys())

    @classmethod
    def get_mime_type(cls, format_name: str) -> str:
        """动态获取 MIME 类型，优先使用 Pillow 信息"""
        format_upper = format_name.upper()

        # 先检查特殊映射
        if format_upper in cls.SPECIAL_MIME_TYPES:
            return cls.SPECIAL_MIME_TYPES[format_upper]

        # 使用标准映射
        return f"image/{format_upper.lower()}"

    @classmethod
    def get_extension(cls, format_name: str) -> str:
        """动态获取扩展名，优先使用首选扩展名"""
        format_upper = format_name.upper()

        # 先检查首选扩展名
        if format_upper in cls.PREFERRED_EXTENSIONS:
            return cls.PREFERRED_EXTENSIONS[format_upper]

        # 从 Pillow 动态获取
        for ext, fmt in Image.registered_extensions().items():
            if fmt and fmt.upper() == format_upper:
                return ext.lower()

        # 后备选择
        return f".{format_upper.lower()}"


class QualityDefaults:
    """质量相关默认值，简化设计"""

    # 质量模式对应的数值
    MODE_VALUES: Final[dict[str, int | None]] = {
        "lossless": None,
        "custom": None,  # 自定义质量由用户指定
    }

    # 默认质量值
    DEFAULT: Final[int] = 85

    # 质量范围
    MIN_QUALITY: Final[int] = 1
    MAX_QUALITY: Final[int] = 100

    # 格式推荐质量
    FORMAT_RECOMMENDED: Final[dict[str, int]] = {
        "JPEG": 85,
        "WEBP": 80,
        "PNG": 95,  # PNG量化时的推荐质量
    }


class ProcessingDefaults:
    """处理相关默认值"""

    # 默认排除目录
    EXCLUDE_DIRS: Final[list[str]] = [
        "__pycache__",
        ".git",
        ".svn",
        "node_modules",
        ".DS_Store",
        "Thumbs.db",
    ]

    # 默认最大工作线程数
    MAX_WORKERS: Final[int] = 4

    # 默认输出文件名模式
    OUTPUT_PATTERN: Final[str] = "{stem}_compressed_{quality}{ext}"

    # 批量处理时的默认递归设置
    DEFAULT_RECURSIVE: Final[bool] = True


class ValidationLimits:
    """验证相关限制"""

    # 文件大小限制 (字节)
    MAX_FILE_SIZE: Final[int] = 100 * 1024 * 1024  # 100MB

    # 图像尺寸限制
    MAX_DIMENSION: Final[int] = 50000  # 50000像素

    # 最大批量处理文件数
    MAX_BATCH_FILES: Final[int] = 1000

    # 路径长度限制
    MAX_PATH_LENGTH: Final[int] = 260  # Windows限制


# 便捷访问函数
def get_format_alias(format_str: str) -> str:
    """获取格式的标准名称"""
    format_upper = format_str.upper()
    return ImageFormats.ALIASES.get(format_upper, format_upper)


def get_mime_type(format_str: str) -> str:
    """获取格式的MIME类型"""
    standard_format = get_format_alias(format_str)
    return ImageFormats.get_mime_type(standard_format)


def get_extension(format_str: str) -> str:
    """获取格式的首选扩展名"""
    standard_format = get_format_alias(format_str)
    return ImageFormats.get_extension(standard_format)


def supports_transparency(format_str: str) -> bool:
    """检查格式是否支持透明度"""
    standard_format = get_format_alias(format_str)
    return standard_format in ImageFormats.TRANSPARENCY_FORMATS


def is_lossless_format(format_str: str) -> bool:
    """检查是否为无损格式"""
    standard_format = get_format_alias(format_str)
    return standard_format in ImageFormats.LOSSLESS_FORMATS
