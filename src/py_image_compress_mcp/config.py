"""统一配置管理模块。

提供应用程序的全局配置管理，包括默认值、环境变量支持等。
"""

import os
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CompressionDefaults:
    """压缩相关的默认配置"""

    # 质量设置 - 更保守的默认值
    JPEG_QUALITY: int = 85
    WEBP_QUALITY: int = 75  # 降低WebP默认质量，避免过度压缩
    PNG_COMPRESS_LEVEL: int = 6

    # 尺寸限制 - 更保守的阈值
    MAX_DIMENSION: int = 8192
    SIZE_THRESHOLD_MB: float = 5.0  # 降低阈值，对中等文件更保守
    COMPLEXITY_THRESHOLD: float = 0.7

    # 并发设置
    MAX_WORKERS: int = 4

    # 文件大小限制
    MAX_FILE_SIZE_MB: float = 100.0
    MIN_FILE_SIZE_BYTES: int = 2048

    def get_format_defaults(self, format_name: str) -> dict[str, Any]:
        """获取格式特定的默认参数"""
        defaults = {
            "JPEG": {
                "quality": self.JPEG_QUALITY,
                "optimize": True,
                "progressive": False,
            },
            "WEBP": {
                "quality": self.WEBP_QUALITY,
                "method": 6,
                "lossless": False,
            },
            "PNG": {
                "compress_level": self.PNG_COMPRESS_LEVEL,
                "optimize": True,
            },
        }
        return defaults.get(format_name, {})

    def get_quality_by_mode(self, mode: str) -> int:  # noqa: ARG002
        """根据质量模式获取具体质量值，简化设计"""
        # 只保留默认质量，自定义质量由用户指定
        # mode参数保留用于未来扩展
        return self.JPEG_QUALITY


@dataclass(frozen=True)
class ProcessingDefaults:
    """处理相关的默认配置"""

    # 策略设置
    PREFER_QUALITY: bool = True
    ENABLE_SMART_STRATEGY: bool = True

    # 优化设置
    ENABLE_OPTIMIZATION: bool = True
    ENABLE_PROGRESSIVE: bool = False

    # 批量处理设置
    BATCH_SIZE: int = 100
    PROGRESS_REPORT_INTERVAL: int = 10


@dataclass(frozen=True)
class LoggingDefaults:
    """日志相关的默认配置"""

    # 日志级别
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # 文件日志
    ENABLE_FILE_LOGGING: bool = False
    LOG_FILE_PATH: str = "py_image_compress.log"
    LOG_FILE_MAX_SIZE: int = 10 * 1024 * 1024  # 10MB
    LOG_FILE_BACKUP_COUNT: int = 5


class AppConfig:
    """应用程序配置管理器

    支持环境变量覆盖默认配置
    """

    def __init__(self):
        self.compression = CompressionDefaults()
        self.processing = ProcessingDefaults()
        self.logging = LoggingDefaults()

        # 从环境变量加载配置
        self._load_from_env()

    def _load_from_env(self):
        """从环境变量加载配置"""
        # 压缩配置
        if jpeg_quality := os.getenv("PIC_JPEG_QUALITY"):
            object.__setattr__(self.compression, "JPEG_QUALITY", int(jpeg_quality))

        if webp_quality := os.getenv("PIC_WEBP_QUALITY"):
            object.__setattr__(self.compression, "WEBP_QUALITY", int(webp_quality))

        if max_workers := os.getenv("PIC_MAX_WORKERS"):
            object.__setattr__(self.compression, "MAX_WORKERS", int(max_workers))

        # 日志配置
        if log_level := os.getenv("PIC_LOG_LEVEL"):
            object.__setattr__(self.logging, "LOG_LEVEL", log_level.upper())

        if enable_file_log := os.getenv("PIC_ENABLE_FILE_LOGGING"):
            object.__setattr__(
                self.logging,
                "ENABLE_FILE_LOGGING",
                enable_file_log.lower() in ("true", "1", "yes"),
            )

    @staticmethod
    def get_executor_type(file_count: int) -> str:
        """根据文件数量智能选择执行器类型"""
        if file_count <= 5:
            return "thread"  # 少量文件使用线程池
        return "process"  # 大量文件使用进程池

    @staticmethod
    def should_use_optimization(file_size_mb: float) -> bool:
        """判断是否应该启用优化"""
        return file_size_mb > 1.0  # 大于1MB的文件启用优化


# 全局配置实例
config = AppConfig()


def get_config() -> AppConfig:
    """获取全局配置实例"""
    return config


def reset_config():
    """重置配置（主要用于测试）"""
    global config
    config = AppConfig()
