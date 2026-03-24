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

    @classmethod
    def get_supported_formats(cls) -> set[str]:
        """动态获取 Pillow 支持的所有格式"""
        return {fmt.upper() for fmt in Image.registered_extensions().values() if fmt}


def get_format_alias(format_str: str) -> str:
    """获取格式的标准名称"""
    format_upper = format_str.upper()
    return ImageFormats.ALIASES.get(format_upper, format_upper)
