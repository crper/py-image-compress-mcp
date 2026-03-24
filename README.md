# py-image-compress-mcp

Image compression and image metadata inspection over the official Python MCP SDK.

This project exposes a small local MCP server for desktop agents and coding tools. It keeps the MCP surface intentionally small:

- `compress_universal`: compress a file, convert formats, or batch-process a directory
- `get_image_info`: inspect dimensions, transparency, EXIF, ICC, and lightweight/full analysis

The server is designed for local `stdio` use and follows the official Python MCP stack via `mcp[cli]`.

## Why this project

- Official Python MCP SDK: `mcp.server.fastmcp.FastMCP`
- Local-first: optimized for Codex, Claude Desktop, and other MCP desktop clients
- Small API surface: two tools cover the main workflows
- Safe output behavior: writes temp files first, then replaces the final output only when valid
- Stable batch behavior: deterministic file discovery and ordered batch results
- Conservative same-format behavior: skips likely negative recompression instead of wasting time re-encoding
- Fast hot path: compression uses lightweight analysis instead of full metadata extraction

## Installation

Requirements:

- Python `3.10+`
- [`uv`](https://docs.astral.sh/uv/)

Install:

```bash
git clone https://github.com/crper/py-image-compress-mcp.git
cd py-image-compress-mcp
uv sync
```

## Quick Start

Run the local MCP server:

```bash
uv run py-image-compress-mcp
```

Or run the module directly:

```bash
uv run python -m py_image_compress_mcp
```

Inspect with the official MCP dev tool:

```bash
uv run mcp dev src/py_image_compress_mcp/mcp_server.py
```

Install into an MCP desktop client with the official CLI:

```bash
uv run mcp install src/py_image_compress_mcp/mcp_server.py
```

## MCP Tools

### `compress_universal`

Compress one file, convert one file into multiple formats, or batch-process a directory.

Parameters:

- `input_path`: file or directory path
- `output_path`: optional output file or output directory
- `formats`: `None`, a single format string, or a list of formats
- `quality`: `1-100`; `None` keeps lossless mode
- `max_width`, `max_height`: optional resize limits
- `recursive`: recurse into subdirectories in directory mode

Typical examples:

- `compress_universal("photo.jpg")`
- `compress_universal("photo.jpg", formats="WEBP", quality=82)`
- `compress_universal("photos/", output_path="compressed/", formats="WEBP", quality=80)`
- `compress_universal("photo.png", output_path="out/", formats=["WEBP", "JPEG", "PNG"], quality=80)`

Behavior notes:

- `compress_universal` may short-circuit some same-format lossy requests such as `JPEG -> JPEG` or `WEBP -> WEBP` when the engine predicts a likely negative optimization.
- In that case the server still returns `success: true`, copies the original bytes to the output path, and marks the file result with `format_used: "SKIPPED"`.
- For MCP callers, the skip reason is exposed in the structured result via `skipped: true` and a human-readable `note` field.
- The top-level `error` field is reserved for real failures and stays `null` for successful skips.

### `get_image_info`

Inspect image metadata and analysis with three response levels. The default level is `summary`.

Parameters:

- `input_path`: image path
- `detail`: `basic`, `summary`, or `full`
- `include_histogram`: optional override
- `include_analysis`: optional override

Detail levels:

- `basic`: dimensions, file size, transparency, orientation
- `summary`: default; `basic` plus EXIF / ICC / complexity
- `full`: `summary` plus histogram data

## Python Usage

The Python-facing API is intentionally smaller than before. Create an `ImageCompressor` explicitly.

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

For the Python API, a skipped same-format recompression still returns `success=True`. Inspect `result["result"].skipped` and `result["result"].note` if you need to distinguish a true re-encode from a conservative no-op copy.

Direct single-file APIs are still available when you need more control:

```python
from py_image_compress_mcp import ImageCompressor

compressor = ImageCompressor(max_workers=4)
single = compressor.compress_image("photo.jpg", output_dir="out", quality=80, format="JPEG")
multi = compressor.compress_multi_format("photo.jpg", "out", ["JPEG", "WEBP"], quality=80)
```

## Codex App / Codex CLI

Add the server as a local MCP server:

```bash
codex mcp add py-image-compress-local -- \
  uv run --project /absolute/path/to/py-image-compress-mcp py-image-compress-mcp
```

Check the registered config:

```bash
codex mcp get py-image-compress-local
```

## Claude Desktop

Example configuration:

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

## More Docs

- [CONTRIBUTING.md](CONTRIBUTING.md)
- [PYPI_RELEASE.md](PYPI_RELEASE.md)

## Upgrade Notes

Recent API cleanup further narrowed the public surface:

- `from py_image_compress_mcp import compress_universal` was removed
- `from py_image_compress_mcp import BatchResult`, `CompressionResult`, and `MultiFormatResult` were removed
- `py_image_compress_mcp.mcp_server.create_server` was removed
- `build_config()` was removed from `py_image_compress_mcp.engine.config`

Use `ImageCompressor()` directly instead. The package root now guarantees only `ImageCompressor` and `__version__`.

## Development

Common commands:

```bash
make dev
make test
make typecheck
make benchmark
make examples
```

Run the remaining example script directly when needed:

```bash
uv run python examples/mcp_usage.py
```

Validation currently used in this repo:

```bash
uv run ruff check .
uv run mypy src tests
uv run pytest -q
```

## Benchmarks

Run:

```bash
uv run python scripts/benchmark.py
```

The benchmark covers:

- metadata extraction on `public/images/3.jpg`
- single-image compression on `public/images/3.jpg`
- batch compression on `public/images`
- one extra real PNG from `~/Downloads` when available

## Project Notes

- Transport: `stdio`
- SDK: official `mcp[cli]`
- Server entry: [src/py_image_compress_mcp/mcp_server.py](/Users/linqunhe/code/self-github/projects/py-image-compress-mcp/src/py_image_compress_mcp/mcp_server.py)

## License

MIT
