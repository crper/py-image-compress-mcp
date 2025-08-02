"""消息格式化工具模块。

提供统一的错误消息、成功消息格式化功能。
"""

from pathlib import Path
from typing import Any


class MessageFormatter:
    """统一的消息格式化器"""

    @staticmethod
    def file_not_found(file_path: str | Path) -> str:
        """文件不存在错误消息"""
        return f"文件不存在: {file_path}"

    @staticmethod
    def directory_not_found(directory: str | Path) -> str:
        """目录不存在错误消息"""
        return f"目录不存在: {directory}"

    @staticmethod
    def path_not_directory(path: str | Path) -> str:
        """路径不是目录错误消息"""
        return f"路径不是目录: {path}"

    @staticmethod
    def permission_error(path: str | Path, operation: str = "访问") -> str:
        """权限错误消息"""
        return f"权限错误，无法{operation}: {path}"

    @staticmethod
    def operation_failed(
        operation: str, target: str | Path, error: Exception | None = None
    ) -> str:
        """操作失败消息"""
        msg = f"{operation}失败: {target}"
        if error:
            msg += f" - {error}"
        return msg

    @staticmethod
    def validation_error(field: str, value: Any, reason: str | None = None) -> str:
        """参数验证错误消息"""
        msg = f"参数验证失败 - {field}: {value}"
        if reason:
            msg += f" ({reason})"
        return msg

    @staticmethod
    def format_error(operation: str, path: str | Path, error: Exception) -> str:
        """格式化通用错误消息"""
        return f"{operation}失败 [{path}]: {error}"


# 便捷函数
def format_file_error(operation: str, file_path: str | Path, error: Exception) -> str:
    """格式化文件操作错误消息"""
    return MessageFormatter.format_error(operation, file_path, error)


def format_validation_error(field: str, value: Any, expected: str | None = None) -> str:
    """格式化验证错误消息"""
    reason = f"期望: {expected}" if expected else None
    return MessageFormatter.validation_error(field, value, reason)
