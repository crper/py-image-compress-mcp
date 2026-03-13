# py-image-compress-mcp

基于官方 Python MCP SDK 的本地图像压缩与图片信息分析服务。

这个项目面向桌面端 MCP 客户端和编码工具，故意把接口面控制得很小，只保留两个核心工具：

- `compress_universal`：压缩单图、转换格式、批量处理目录
- `get_image_info`：读取尺寸、透明度、EXIF、ICC 和轻量/完整分析信息

服务默认以本地 `stdio` 模式运行，并已经切到官方 `mcp[cli]` 技术栈。

## 项目特点

- 官方 Python MCP SDK：`mcp.server.fastmcp.FastMCP`
- 面向本地使用：适合 Codex、Claude Desktop 等 MCP 桌面客户端
- 工具少但覆盖核心场景：只有 2 个 MCP 工具
- 输出安全：先写临时文件，验证通过后再替换正式输出
- 批量结果稳定：文件发现顺序固定，返回顺序与输入一致
- 热路径优化：压缩默认走轻量分析，不做全量元数据提取

## 安装

环境要求：

- Python `3.10+`
- [`uv`](https://docs.astral.sh/uv/)

安装：

```bash
git clone https://github.com/crper/py-image-compress-mcp.git
cd py-image-compress-mcp
uv sync
```

## 快速开始

启动本地 MCP 服务：

```bash
uv run py-image-compress-mcp
```

或者直接运行模块：

```bash
uv run python -m py_image_compress_mcp
```

使用官方 MCP 调试工具查看：

```bash
uv run mcp dev src/py_image_compress_mcp/mcp_server.py
```

使用官方 CLI 安装到 MCP 客户端：

```bash
uv run mcp install src/py_image_compress_mcp/mcp_server.py
```

## MCP 工具

### `compress_universal`

一个工具覆盖以下场景：

- 单文件压缩
- 单文件格式转换
- 单文件多格式输出
- 目录批量压缩

参数：

- `input_path`：文件或目录路径
- `output_path`：可选输出文件或输出目录
- `formats`：`None`、单个格式字符串，或格式列表
- `quality`：`1-100`；`None` 表示无损模式
- `max_width`、`max_height`：可选尺寸限制
- `recursive`：目录模式是否递归

常见调用：

- `compress_universal("photo.jpg")`
- `compress_universal("photo.jpg", formats="WEBP", quality=82)`
- `compress_universal("photos/", output_path="compressed/", formats="WEBP", quality=80)`
- `compress_universal("photo.png", output_path="out/", formats=["WEBP", "JPEG", "PNG"], quality=80)`

### `get_image_info`

用于读取图片元数据和分析信息，支持三档返回级别，默认是 `summary`。

参数：

- `input_path`：图片路径
- `detail`：`basic`、`summary`、`full`
- `include_histogram`：可选覆盖直方图返回
- `include_analysis`：可选覆盖复杂度分析返回

三档含义：

- `basic`：尺寸、文件大小、透明度、方向
- `summary`：默认级别，在 `basic` 基础上增加 EXIF / ICC / complexity
- `full`：在 `summary` 基础上再返回 histogram

## Python 用法

Python 侧 API 现在比以前更小，推荐显式创建 `ImageCompressor`。

```python
from py_image_compress_mcp import ImageCompressor

compressor = ImageCompressor()

result = compressor.compress_universal(
    input_path="photo.jpg",
    output="photo.webp",
    formats="WEBP",
    quality=82,
)

if result["success"]:
    print(result["result"].get_summary())
```

需要更细控制时，仍可直接调用单文件/多格式接口：

```python
from py_image_compress_mcp import ImageCompressor

compressor = ImageCompressor(max_workers=4)
single = compressor.compress_image("photo.jpg", output_dir="out", quality=80, format="JPEG")
multi = compressor.compress_multi_format("photo.jpg", "out", ["JPEG", "WEBP"], quality=80)
```

## Codex App / Codex CLI

把服务注册为本地 MCP：

```bash
codex mcp add py-image-compress-local -- \
  uv run --project /absolute/path/to/py-image-compress-mcp py-image-compress-mcp
```

查看配置：

```bash
codex mcp get py-image-compress-local
```

## Claude Desktop

配置示例：

```json
{
  "mcpServers": {
    "py-image-compress": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/absolute/path/to/py-image-compress-mcp",
        "py-image-compress-mcp"
      ]
    }
  }
}
```

## 升级说明

这轮 API 收敛删除了几个兼容入口：

- `from py_image_compress_mcp import compress_universal` 已删除
- `py_image_compress_mcp.engine.config.build_config` 已删除

请改为显式使用 `ImageCompressor()`。

## 开发

常用命令：

```bash
make dev
make test
make typecheck
make benchmark
make examples
```

当前仓库使用的验证命令：

```bash
uv run ruff check .
uv run mypy src tests
uv run pytest -q
```

## 性能基准

运行：

```bash
uv run python scripts/benchmark.py
```

基准覆盖：

- `public/images/3.jpg` 元数据提取
- `public/images/3.jpg` 单图压缩
- `public/images` 目录批量压缩
- 如果本机 `~/Downloads` 下存在真实 `png`，还会额外补一轮

## 项目说明

- 传输方式：`stdio`
- SDK：官方 `mcp[cli]`
- 服务入口：[src/py_image_compress_mcp/mcp_server.py](/Users/linqunhe/code/self-github/projects/py-image-compress-mcp/src/py_image_compress_mcp/mcp_server.py)
- 优化与基准报告：[OPTIMIZATION.md](/Users/linqunhe/code/self-github/projects/py-image-compress-mcp/OPTIMIZATION.md)

## License

MIT
