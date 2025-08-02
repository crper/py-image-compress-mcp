"""Entry point for python -m py_image_compress_mcp.

默认启动 MCP 服务器。
"""

import sys


def main() -> None:
    """主入口函数 - 启动 MCP 服务器"""
    # 检查版本信息
    if len(sys.argv) > 1 and sys.argv[1] in ["--version", "-v"]:
        from . import __version__

        print(f"py-image-compress-mcp {__version__}")
        return

    # 启动 MCP 服务器
    from .mcp_server import main as server_main

    server_main()


if __name__ == "__main__":
    main()
