"""批量处理器模块。

专门处理批量图像压缩任务，支持并发和进度监控。
"""

from pathlib import Path

from ..core.compression_engine import process_image
from ..models.compression_result import (
    BatchResult,
    CompressionResult,
)
from ..utils import find_image_files
from ..utils.logging_helpers import get_logger
from ..utils.message_formatter import MessageFormatter
from .concurrent_executor import ConcurrentExecutor
from .config import ConfigBuilder


logger = get_logger()


class BatchProcessor:
    """批量图像处理器

    专门处理批量压缩任务，支持并发处理和智能执行器选择。
    """

    def __init__(
        self,
        max_workers: int = 4,
        force_executor_type: str | None = None,
        config_builder: ConfigBuilder | None = None,
    ):
        """初始化批量处理器

        Args:
            max_workers: 最大并发数
            force_executor_type: 强制指定执行器类型 ('thread'/'process'/None为自动选择)
            config_builder: 配置构建器实例
        """
        self.max_workers = max_workers
        self.force_executor_type = force_executor_type
        self.config_builder = config_builder or ConfigBuilder()
        self.concurrent_executor = ConcurrentExecutor(max_workers, force_executor_type)

    def process_directory(
        self,
        input_dir: str | Path,
        output_dir: str | Path | None = None,
        quality: int | None = None,
        format: str | None = None,
        max_width: int | None = None,
        max_height: int | None = None,
        recursive: bool = True,
        exclude_dirs: list[str] | None = None,
    ) -> BatchResult:
        """处理目录中的所有图像文件

        Args:
            input_dir: 输入目录
            output_dir: 输出目录（可选）
            quality: 压缩质量
            format: 输出格式
            max_width: 最大宽度
            max_height: 最大高度
            recursive: 是否递归处理子目录
            exclude_dirs: 要排除的目录名列表

        Returns:
            BatchResult: 批量处理结果
        """
        try:
            input_dir, output_dir = self._prepare_directories(input_dir, output_dir)

            # 查找图像文件，排除输出目录
            exclude_dirs = exclude_dirs or []
            if output_dir != input_dir:
                # 如果输出目录在输入目录内，添加到排除列表
                try:
                    output_dir.relative_to(input_dir)
                    exclude_dirs.append(output_dir.name)
                except ValueError:
                    # 输出目录不在输入目录内，无需排除
                    pass

            image_files = list(
                find_image_files(
                    input_dir,
                    recursive=recursive,
                    exclude_dirs=exclude_dirs,
                )
            )

            if not image_files:
                return self._create_empty_batch_result(input_dir, output_dir)

            # 并发处理图像文件，为每个文件计算正确的输出目录
            results = self._process_files_with_structure(
                image_files=image_files,
                input_dir=input_dir,
                output_dir=output_dir,
                quality=quality,
                format=format,
                max_width=max_width,
                max_height=max_height,
            )

            return self._create_batch_result(input_dir, output_dir, results)

        except Exception as e:
            from py_image_compress_mcp.exceptions import ErrorHandler

            ErrorHandler._log_error("目录批量处理", Path(input_dir), e, "error")
            return ErrorHandler.create_error_batch_result(
                input_dir=Path(input_dir),
                output_dir=Path(output_dir) if output_dir else None,
                error_message=str(e),
            )

    def process_files_concurrent(
        self,
        files: list[Path],
        output_dir: Path,
        quality: int | None = None,
        format: str | None = None,
        max_width: int | None = None,
        max_height: int | None = None,
    ) -> list[CompressionResult]:
        """并发处理文件列表

        Args:
            files: 文件路径列表
            output_dir: 输出目录
            quality: 压缩质量
            format: 输出格式
            max_width: 最大宽度
            max_height: 最大高度

        Returns:
            list[CompressionResult]: 处理结果列表
        """
        if not files:
            return []

        # 直接创建压缩配置列表
        compression_configs = [
            self.config_builder.build(
                input_path=file_path,
                output_dir=output_dir,
                quality=quality,
                format=format,
                max_width=max_width,
                max_height=max_height,
            )
            for file_path in files
        ]

        # 使用通用并发执行器
        return self.concurrent_executor.execute_tasks(
            compression_configs=compression_configs,
            task_function=process_image,
        )

    def _process_files_with_structure(
        self,
        image_files: list[Path],
        input_dir: Path,
        output_dir: Path,
        quality: int | None,
        format: str | None,
        max_width: int | None,
        max_height: int | None,
    ) -> list[CompressionResult]:
        """处理文件并保持目录结构"""
        if not image_files:
            return []

        # 为每个文件计算正确的输出目录并创建压缩配置
        compression_configs = []
        for file_path in image_files:
            # 计算相对路径以保持目录结构
            relative_path = file_path.relative_to(input_dir)
            file_output_dir = output_dir / relative_path.parent

            compression_configs.append(
                self.config_builder.build(
                    input_path=file_path,
                    output_dir=file_output_dir,
                    quality=quality,
                    format=format,
                    max_width=max_width,
                    max_height=max_height,
                )
            )

        # 使用通用并发执行器
        return self.concurrent_executor.execute_tasks(
            compression_configs=compression_configs,
            task_function=process_image,
        )

    def _prepare_directories(
        self, input_dir: str | Path, output_dir: str | Path | None
    ) -> tuple[Path, Path]:
        """准备输入和输出目录"""
        input_dir = Path(input_dir)
        if output_dir is None:
            output_dir = input_dir
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        return input_dir, output_dir

    def _create_empty_batch_result(
        self, input_dir: Path, output_dir: Path
    ) -> BatchResult:
        """创建空的批量结果"""
        return BatchResult(
            input_dir=input_dir,
            output_dir=output_dir,
            results=[],
            success=True,
            error="未找到图像文件",
        )

    def _create_batch_result(
        self, input_dir: Path, output_dir: Path, results: list[CompressionResult]
    ) -> BatchResult:
        """创建批量处理结果"""
        success_count = sum(1 for r in results if r.success)
        success = success_count > 0

        try:
            return BatchResult(
                input_dir=input_dir,
                output_dir=output_dir,
                results=results,
                success=success,
                error=None if success else "所有文件处理都失败",
            )
        except Exception as e:
            logger.error(
                MessageFormatter.operation_failed("创建 BatchResult", input_dir, e)
            )
            # 降级处理
            fallback_result: BatchResult = BatchResult.model_construct(
                input_dir=input_dir,
                output_dir=output_dir,
                results=results,
                success=success,
                error=None if success else "所有文件处理都失败",
            )
            return fallback_result
