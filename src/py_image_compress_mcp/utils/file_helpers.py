"""工具函数模块。

提供图像处理相关的实用工具函数。
"""

from collections.abc import Iterator
from pathlib import Path

from PIL import Image

from ..models.constants import get_mime_type
from .logging_helpers import get_logger
from .message_formatter import MessageFormatter


logger = get_logger()


def find_image_files(
    directory: str | Path,
    recursive: bool = True,
    exclude_dirs: list[str] | None = None,
) -> Iterator[Path]:
    """查找目录中的图像文件。

    Args:
        directory: 搜索目录
        recursive: 是否递归搜索子目录
        exclude_dirs: 要排除的目录名列表

    Yields:
        Path: 图像文件路径
    """
    directory = Path(directory)
    exclude_dirs = exclude_dirs or []

    if not directory.exists():
        logger.warning(MessageFormatter.directory_not_found(directory))
        return

    if not directory.is_dir():
        logger.warning(MessageFormatter.path_not_directory(directory))
        return

    # 选择搜索模式
    pattern = "**/*" if recursive else "*"

    # 获取支持的扩展名（直接使用 Pillow API）
    supported_extensions = set(Image.registered_extensions().keys())

    try:
        for file_path in directory.glob(pattern):
            if (
                file_path.is_file()
                and file_path.suffix.lower() in supported_extensions
                and not any(
                    exclude_dir in file_path.parts for exclude_dir in exclude_dirs
                )
            ):
                yield file_path
    except PermissionError:
        logger.error(MessageFormatter.permission_error(directory, "访问目录"))
    except Exception as e:
        logger.error(MessageFormatter.operation_failed("搜索图像文件", directory, e))


def get_image_mime_type(file_path: str | Path) -> str | None:
    """获取图片文件的 MIME 类型

    使用统一的常量映射获取准确的 MIME 类型

    Args:
        file_path: 图片文件路径

    Returns:
        str | None: MIME 类型，如 'image/jpeg'，失败时返回 None
    """
    try:
        with Image.open(file_path) as img:
            if img.format:
                # 使用统一的常量映射
                mime_type = get_mime_type(img.format)
                return mime_type or f"image/{img.format.lower()}"
            return None
    except Exception as e:
        logger.debug(MessageFormatter.operation_failed("获取 MIME 类型", file_path, e))
        return None
