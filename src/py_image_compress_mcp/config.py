"""统一配置管理模块。

提供应用程序的全局配置管理，包括默认值、环境变量支持等。
"""

import os
from dataclasses import dataclass, field


def _detect_default_max_workers() -> int:
    """根据当前机器能力推导默认并发数。"""
    cpu_count = os.cpu_count() or 4
    return max(1, min(cpu_count, 8))


@dataclass(frozen=True)
class CompressionDefaults:
    """压缩相关的默认配置"""

    # 质量设置 - 更保守的默认值
    JPEG_QUALITY: int = 85
    WEBP_QUALITY: int = 75  # 降低WebP默认质量，避免过度压缩

    # 尺寸限制 - 更保守的阈值
    SIZE_THRESHOLD_MB: float = 5.0  # 降低阈值，对中等文件更保守
    COMPLEXITY_THRESHOLD: float = 0.7

    # 并发设置
    MAX_WORKERS: int = field(default_factory=_detect_default_max_workers)


@dataclass(frozen=True)
class ProcessingDefaults:
    """处理相关的默认配置"""

    # 策略设置
    PREFER_QUALITY: bool = True


class AppConfig:
    """应用程序配置管理器

    支持环境变量覆盖默认配置
    """

    def __init__(self):
        self.compression = CompressionDefaults()
        self.processing = ProcessingDefaults()

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
            object.__setattr__(
                self.compression, "MAX_WORKERS", max(1, int(max_workers))
            )


# 全局配置实例
config = AppConfig()


def get_config() -> AppConfig:
    """获取全局配置实例"""
    return config


def get_default_max_workers() -> int:
    """获取默认并发数。"""
    return get_config().compression.MAX_WORKERS


def reset_config():
    """重置配置（主要用于测试）"""
    global config
    config = AppConfig()
