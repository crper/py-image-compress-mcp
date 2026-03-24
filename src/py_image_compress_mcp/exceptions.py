"""图像压缩异常处理模块。

定义统一的异常类和错误处理机制，包含现代化的异常处理装饰器。
"""

from pathlib import Path

from .models.compression_result import BatchResult, CompressionResult
from .utils.logging_helpers import get_logger
from .utils.message_formatter import MessageFormatter


logger = get_logger()


# 统一的异常类型
class CompressionError(Exception):
    """压缩相关错误基类"""

    def __init__(self, message: str, input_path: Path | None = None):
        super().__init__(message)
        self.message = message
        self.input_path = input_path


class ValidationError(CompressionError):
    """参数验证错误 - 统一的验证错误类型"""

    pass


class ProcessingError(CompressionError):
    """处理过程错误"""

    pass


class UnsupportedFormatError(CompressionError):
    """不支持的格式错误"""

    pass


class ErrorHandler:
    """统一错误处理器

    提供标准化的错误处理和日志记录功能。
    """

    @staticmethod
    def _log_error(
        operation: str, path: Path, error: Exception, level: str = "error"
    ) -> None:
        """标准化的错误日志记录

        Args:
            operation: 操作名称（如"图像压缩"、"文件读取"等）
            path: 相关文件路径
            error: 异常对象
            level: 日志级别 ("error", "warning", "debug")
        """
        log_msg = MessageFormatter.format_error(operation, path, error)
        getattr(logger, level, logger.error)(log_msg)

    @staticmethod
    def _create_error_result(
        input_path: Path,
        error_msg: str,
        output_path: Path | None = None,
        original_size: int | None = None,
    ) -> CompressionResult:
        """创建标准化的错误结果

        Args:
            input_path: 输入文件路径
            error_msg: 错误消息
            output_path: 输出文件路径（可选）
            original_size: 原始文件大小（可选）
        """
        if original_size is None:
            try:
                original_size = input_path.stat().st_size if input_path.exists() else 0
            except Exception:
                original_size = 0

        return CompressionResult(
            input_path=input_path,
            output_path=output_path or input_path.with_suffix(".compressed"),
            original_size=original_size,
            compressed_size=0,
            success=False,
            error=error_msg,
            format_used="UNKNOWN",
            quality_used=None,
            was_resized=False,
            original_dimensions=None,
            final_dimensions=None,
        )

    @staticmethod
    def handle_validation_error(
        error: ValidationError, input_path: Path, output_path: Path | None = None
    ) -> CompressionResult:
        """处理验证错误"""
        ErrorHandler._log_error("参数验证", input_path, error, "warning")
        return ErrorHandler._create_error_result(
            input_path=input_path,
            error_msg=f"参数验证失败: {error.message}",
            output_path=output_path,
        )

    @staticmethod
    def handle_with_context(
        error: Exception,
        input_path: Path,
        operation: str = "未知操作",
        output_path: Path | None = None,
        log_level: str = "error",
    ) -> CompressionResult:
        """增强的错误处理，包含更多上下文信息

        Args:
            error: 异常对象
            input_path: 输入文件路径
            operation: 操作名称（如"图像压缩"、"格式转换"等）
            output_path: 输出文件路径（可选）
            log_level: 日志级别 ("error", "warning", "debug")

        Returns:
            CompressionResult: 标准化的错误结果
        """
        ErrorHandler._log_error(operation, input_path, error, log_level)
        return ErrorHandler._create_error_result(
            input_path=input_path,
            error_msg=f"{operation}: {error}",
            output_path=output_path,
        )

    @staticmethod
    def handle_compression_error(
        error: Exception, input_path: Path, operation: str = "图像压缩"
    ) -> CompressionResult:
        """统一的压缩错误处理，从 compressor.py 移入，支持 match-case 错误分发"""
        match error:
            case ValidationError() as ve:
                return ErrorHandler.handle_validation_error(ve, input_path)
            case UnsupportedFormatError() as ufe:
                return ErrorHandler.handle_with_context(
                    ufe, input_path, operation, log_level="warning"
                )
            case FileNotFoundError() as fnfe:
                return ErrorHandler.handle_with_context(
                    fnfe, input_path, operation, log_level="warning"
                )
            case PermissionError() as pe:
                return ErrorHandler.handle_with_context(
                    pe, input_path, f"{operation} - 权限错误", log_level="error"
                )
            case OSError() as ose:
                return ErrorHandler.handle_with_context(
                    ose, input_path, f"{operation} - 系统错误", log_level="error"
                )
            case _:
                return ErrorHandler.handle_with_context(
                    error, input_path, operation, log_level="error"
                )

    @staticmethod
    def create_error_batch_result(
        input_dir: Path,
        output_dir: Path | None,
        error_message: str,
    ) -> BatchResult:
        """创建错误的批量处理结果，从 compressor.py 和 batch.py 移入"""
        return BatchResult(
            input_dir=input_dir,
            output_dir=output_dir or input_dir,
            results=[],
            success=False,
            error=error_message,
        )
