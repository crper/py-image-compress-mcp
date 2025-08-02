"""文件命名工具模块。

提供统一的文件命名策略和路径生成功能。
"""

import itertools
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image

from ..models.compression_config import QualityMode


class FileNamingStrategy:
    """文件命名策略类"""

    @staticmethod
    def generate_output_name(
        input_path: Path,
        quality: int | None = None,
        quality_mode: QualityMode = QualityMode.LOSSLESS,
        target_format: str | None = None,
        custom_suffix: str | None = None,
    ) -> str:
        """生成输出文件名

        Args:
            input_path: 输入文件路径
            quality: 压缩质量
            quality_mode: 质量模式
            target_format: 目标格式
            custom_suffix: 自定义后缀

        Returns:
            str: 生成的文件名（不含路径）
        """
        base_name = input_path.stem

        # 添加自定义后缀或质量后缀
        if custom_suffix:
            base_name += custom_suffix
        else:
            suffix = FileNamingStrategy._get_quality_suffix(quality, quality_mode)
            if suffix:
                base_name += suffix

        # 确定扩展名
        ext = FileNamingStrategy._get_extension(input_path.suffix, target_format)

        return f"{base_name}{ext}"

    @staticmethod
    def _get_quality_suffix(quality: int | None, quality_mode: QualityMode) -> str:
        """获取质量后缀"""
        if quality_mode == QualityMode.LOSSLESS:
            return "_compress"
        if quality is not None:
            return f"_compress_{quality}"
        return "_compress"

    @staticmethod
    @lru_cache(maxsize=128)
    def _get_extension(input_path_suffix: str, target_format: str | None = None) -> str:
        """获取文件扩展名

        使用 Pillow 的动态格式注册表，支持所有已注册的格式。
        """
        if target_format:
            # 使用 Pillow 的格式到扩展名的反向映射
            format_upper = target_format.upper()

            # 从 Pillow 的注册表中查找对应的扩展名
            for ext, fmt in Image.registered_extensions().items():
                if fmt and fmt.upper() == format_upper:
                    return str(ext)

            # 如果没找到，使用常见的默认扩展名
            common_defaults = {
                "JPEG": ".jpg",
                "PNG": ".png",
                "WEBP": ".webp",
                "GIF": ".gif",
                "BMP": ".bmp",
                "TIFF": ".tiff",
                "ICO": ".ico",
            }
            return common_defaults.get(format_upper, ".jpg")

        return input_path_suffix


class PathResolver:
    """路径解析器"""

    @staticmethod
    def resolve_output_path(
        input_path: Path,
        output_path: Path | None = None,
        output_dir: Path | None = None,
        **naming_kwargs: Any,
    ) -> Path:
        """解析输出路径

        Args:
            input_path: 输入文件路径
            output_path: 用户指定的输出路径
            output_dir: 输出目录
            **naming_kwargs: 命名参数

        Returns:
            Path: 解析后的输出路径
        """
        # 优先使用用户指定的输出路径
        if output_path:
            return output_path

        # 确定输出目录
        target_dir = output_dir or input_path.parent

        # 生成文件名
        filename = FileNamingStrategy.generate_output_name(input_path, **naming_kwargs)

        return target_dir / filename

    @staticmethod
    def ensure_unique_path(path: Path) -> Path:
        """确保路径唯一，如果文件已存在则添加数字后缀

        Args:
            path: 原始路径

        Returns:
            Path: 唯一的路径
        """
        if not path.exists():
            return path

        base = path.stem
        suffix = path.suffix
        parent = path.parent

        # 使用 itertools.count 生成无限序列，更简洁
        for counter in itertools.count(1):
            new_path = parent / f"{base}_{counter}{suffix}"
            if not new_path.exists():
                return new_path

        # 理论上永远不会到达这里，但为了类型检查器
        return path  # pragma: no cover


def clean_temp_files(directory: Path, pattern: str = "*_compress_*") -> int:
    """清理临时压缩文件

    Args:
        directory: 目录路径
        pattern: 文件匹配模式

    Returns:
        int: 清理的文件数量
    """
    if not directory.exists() or not directory.is_dir():
        return 0

    count = 0
    for file_path in directory.glob(pattern):
        if file_path.is_file():
            try:
                file_path.unlink()
                count += 1
            except OSError:
                pass  # 忽略删除失败的文件

    return count
