"""日志工具模块。

提供统一的日志记录功能，标准化日志格式和配置。
"""

import inspect
import logging


def get_logger(name: str | None = None) -> logging.Logger:
    """获取标准化配置的日志记录器。

    Args:
        name: 日志记录器名称，默认使用调用模块的 __name__

    Returns:
        logging.Logger: 配置好的日志记录器
    """
    if name is None:
        # 获取调用者的模块名
        frame = inspect.currentframe()
        if frame and frame.f_back:
            name = frame.f_back.f_globals.get("__name__", "unknown")
        else:
            name = "unknown"

    return logging.getLogger(name)
