"""工具函数模块。

提供图像处理相关的实用工具函数。
"""

from collections.abc import Iterator, Sequence
from pathlib import Path

from PIL import Image

from .logging_helpers import get_logger
from .message_formatter import MessageFormatter


logger = get_logger()


def find_image_files(
    directory: str | Path,
    recursive: bool = True,
    exclude_dirs: Sequence[str] | None = None,
    exclude_paths: Sequence[str | Path] | None = None,
) -> Iterator[Path]:
    """查找目录中的图像文件。

    Args:
        directory: 搜索目录
        recursive: 是否递归搜索子目录
        exclude_dirs: 要排除的目录名列表
        exclude_paths: 要排除的目录路径列表

    Yields:
        Path: 图像文件路径
    """
    directory = Path(directory)
    exclude_dirs = exclude_dirs or []
    normalized_exclude_paths = [
        path if path.is_absolute() else directory / path
        for path in (Path(path) for path in (exclude_paths or []))
    ]

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
        for file_path in sorted(directory.glob(pattern)):
            if (
                file_path.is_file()
                and file_path.suffix.lower() in supported_extensions
                and not any(
                    exclude_dir in file_path.parts for exclude_dir in exclude_dirs
                )
                and not any(
                    _is_relative_to(file_path, exclude_path)
                    for exclude_path in normalized_exclude_paths
                )
            ):
                yield file_path
    except PermissionError:
        logger.error(MessageFormatter.permission_error(directory, "访问目录"))
    except Exception as e:
        logger.error(MessageFormatter.operation_failed("搜索图像文件", directory, e))


def _is_relative_to(path: Path, parent: Path) -> bool:
    """兼容性检查 path 是否位于 parent 目录内。"""
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
