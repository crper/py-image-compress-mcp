"""清理工具模块。

提供临时文件清理和资源管理功能。
"""

from pathlib import Path
from typing import Any

from .logging_helpers import get_logger


logger = get_logger()


class TempFileManager:
    """临时文件管理器"""

    def __init__(self):
        self.temp_files: set[Path] = set()

    def register_temp_file(self, file_path: Path) -> None:
        """注册临时文件"""
        self.temp_files.add(file_path)

    def cleanup_temp_files(self) -> int:
        """清理所有注册的临时文件"""
        cleaned_count = 0
        for file_path in self.temp_files:
            try:
                if file_path.exists():
                    file_path.unlink()
                    cleaned_count += 1
                    logger.debug(f"已清理临时文件: {file_path}")
            except OSError as e:
                logger.warning(f"清理临时文件失败 {file_path}: {e}")

        self.temp_files.clear()
        return cleaned_count

    def __enter__(self):
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """上下文管理器退出时清理临时文件"""
        # 忽略异常信息，总是清理临时文件
        del exc_type, exc_val, exc_tb  # 明确表示这些参数未使用
        self.cleanup_temp_files()


class OutputCleaner:
    """输出目录清理器"""

    @staticmethod
    def remove_duplicate_files(directory: Path, pattern: str = "*_compress_*") -> int:
        """移除重复的压缩文件

        Args:
            directory: 目录路径
            pattern: 文件匹配模式

        Returns:
            int: 移除的文件数量
        """
        if not directory.exists() or not directory.is_dir():
            return 0

        removed_count = 0
        compress_files = list(directory.glob(pattern))

        # 按文件名分组，找出重复文件
        file_groups: dict[str, list[Path]] = {}
        for file_path in compress_files:
            # 提取基础名称（去掉 _compress_XX 后缀）
            base_name = OutputCleaner._extract_base_name(file_path.stem)
            if base_name not in file_groups:
                file_groups[base_name] = []
            file_groups[base_name].append(file_path)

        # 对于每组文件，保留最新的，删除其他的
        for files in file_groups.values():
            if len(files) > 1:
                # 按修改时间排序，保留最新的
                files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
                for file_to_remove in files[1:]:
                    try:
                        file_to_remove.unlink()
                        removed_count += 1
                        logger.info(f"移除重复文件: {file_to_remove}")
                    except OSError as e:
                        logger.warning(f"移除文件失败 {file_to_remove}: {e}")

        return removed_count

    @staticmethod
    def _extract_base_name(filename: str) -> str:
        """提取文件的基础名称，去掉压缩后缀"""
        # 移除 _compress 或 _compress_XX 后缀
        if "_compress_" in filename:
            return filename.split("_compress_")[0]
        if filename.endswith("_compress"):
            return filename[:-9]  # 移除 "_compress"
        return filename

    @staticmethod
    def cleanup_failed_outputs(directory: Path, success_files: list[Path]) -> int:
        """清理失败的输出文件

        Args:
            directory: 输出目录
            success_files: 成功生成的文件列表

        Returns:
            int: 清理的文件数量
        """
        if not directory.exists():
            return 0

        success_set = set(success_files)
        cleaned_count = 0

        # 查找所有压缩文件
        for file_path in directory.glob("*_compress*"):
            if file_path not in success_set:
                try:
                    # 检查文件是否为空或损坏
                    if file_path.stat().st_size == 0:
                        file_path.unlink()
                        cleaned_count += 1
                        logger.info(f"清理空文件: {file_path}")
                except OSError as e:
                    logger.warning(f"清理文件失败 {file_path}: {e}")

        return cleaned_count


def validate_output_integrity(file_path: Path) -> bool:
    """验证输出文件的完整性

    Args:
        file_path: 文件路径

    Returns:
        bool: 文件是否完整
    """
    try:
        if not file_path.exists():
            return False

        # 检查文件大小
        if file_path.stat().st_size == 0:
            return False

        # 对于图片文件，尝试打开验证
        # 使用 Pillow 的动态扩展名注册表
        from PIL import Image

        if file_path.suffix.lower() in Image.registered_extensions():
            try:
                with Image.open(file_path) as img:
                    img.verify()
                return True
            except Exception:
                return False

        return True

    except Exception as e:
        logger.debug(f"验证文件完整性失败 {file_path}: {e}")
        return False
