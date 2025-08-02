"""并发执行器模块。

提供通用的并发任务执行功能，消除重复的并发处理逻辑。
"""

import logging
from collections.abc import Callable, Sequence
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from ..exceptions import ErrorHandler
from ..models.compression_result import CompressionResult


logger = logging.getLogger(__name__)


class TaskConfig:
    """任务配置基类"""

    def __init__(self, file_path: Path, **kwargs: Any) -> None:
        self.file_path = file_path
        self.kwargs = kwargs


class ConcurrentExecutor:
    """通用并发执行器

    消除重复的并发处理逻辑，提供统一的任务执行接口。
    """

    def __init__(self, max_workers: int = 4, force_executor_type: str | None = None):
        """初始化并发执行器

        Args:
            max_workers: 最大并发数
            force_executor_type: 强制指定执行器类型 ('thread'/'process'/None为自动选择)
        """
        self.max_workers = max_workers
        self.force_executor_type = force_executor_type

    def execute_tasks(
        self,
        compression_configs: Sequence[Any],  # CompressionConfig objects
        task_function: Callable[[Any], CompressionResult],
    ) -> list[CompressionResult]:
        """执行并发任务

        Args:
            compression_configs: 压缩配置对象列表
            task_function: 要执行的任务函数

        Returns:
            List[CompressionResult]: 任务执行结果列表
        """
        if not compression_configs:
            return []

        results: list[CompressionResult] = []
        executor_class = self._choose_executor(compression_configs)

        with executor_class(max_workers=self.max_workers) as executor:
            # 提交任务阶段
            future_to_config = self._submit_tasks(
                executor, compression_configs, task_function, results
            )

            # 收集结果阶段
            self._collect_results(future_to_config, results)

        return results

    def _submit_tasks(
        self,
        executor: Any,
        compression_configs: Sequence[Any],
        task_function: Callable[[Any], CompressionResult],
        results: list[CompressionResult],
    ) -> dict[Any, Any]:
        """提交任务到执行器"""
        future_to_config = {}

        for config in compression_configs:
            try:
                # 直接提交任务，无需额外的配置构建
                future = executor.submit(task_function, config)
                future_to_config[future] = config

            except Exception as e:
                error_result = ErrorHandler.handle_with_context(
                    e, config.input_path, "任务提交", log_level="error"
                )
                results.append(error_result)

        return future_to_config

    def _collect_results(
        self, future_to_config: dict[Any, Any], results: list[CompressionResult]
    ) -> None:
        """收集任务执行结果"""
        for future in as_completed(future_to_config):
            config = future_to_config[future]
            file_path = config.input_path

            try:
                result = future.result()
                results.append(result)

                # 记录执行结果
                if hasattr(result, "success"):
                    if result.success:
                        logger.debug(f"处理成功: {file_path}")
                    else:
                        logger.warning(
                            f"处理失败: {file_path} - {getattr(result, 'error', 'Unknown error')}"
                        )

            except Exception as e:
                error_result = ErrorHandler.handle_with_context(
                    e, file_path, "并发任务处理", log_level="error"
                )
                results.append(error_result)

    def _choose_executor(self, compression_configs: Sequence[Any]) -> type:
        """根据任务特征选择合适的执行器

        Args:
            compression_configs: 压缩配置列表

        Returns:
            执行器类 (ThreadPoolExecutor 或 ProcessPoolExecutor)
        """
        # 如果用户强制指定了执行器类型
        if self.force_executor_type == "thread":
            return ThreadPoolExecutor
        if self.force_executor_type == "process":
            return ProcessPoolExecutor

        task_count = len(compression_configs)

        # 计算平均文件大小
        try:
            total_size = sum(
                config.input_path.stat().st_size
                for config in compression_configs
                if config.input_path.exists()
            )
            avg_size = total_size / task_count if task_count > 0 else 0
        except Exception:
            avg_size = 0

        # 智能选择策略
        # 大文件或大批量任务使用进程池
        if avg_size > 5 * 1024 * 1024 or task_count > 20:  # 5MB 或 20个文件以上
            logger.debug(
                f"使用ProcessPoolExecutor: 任务数={task_count}, 平均大小={avg_size / 1024 / 1024:.1f}MB"
            )
            return ProcessPoolExecutor

        # 小文件或少量任务使用线程池
        logger.debug(
            f"使用ThreadPoolExecutor: 任务数={task_count}, 平均大小={avg_size / 1024 / 1024:.1f}MB"
        )
        return ThreadPoolExecutor
