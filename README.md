# Python Image Compress MCP

[English](README.md) | [中文](README_zh.md)

A modern image compression MCP server built with Python 3.10+ and Pillow 11+. Provides intelligent compression with unified API and comprehensive metadata analysis for AI assistants.

## ✨ Features

- **🎯 Simplified MCP Interface**: Only 2 core tools - `compress_universal` and `get_image_info`
- **🔄 Universal Processing**: Single tool handles files, directories, single/multi-format output intelligently
- **🧠 Smart PNG Processing**: Optimized PNG handling that avoids file size increases
- **⚡ Intelligent Processing**: Automatic format selection and quality optimization based on image characteristics
- **🚀 Parallel Processing**: High-performance batch compression with configurable thread/process pools
- **📊 Rich Metadata**: EXIF data, ICC profiles, complexity analysis, and histogram data extraction
- **🤖 MCP Integration**: Native support for Claude Desktop and other MCP-compatible AI assistants
- **🐍 Modern Python**: Built with Python 3.10+ features, Pillow 11+, and comprehensive type safety

## demo video
[mcp-demo.webm](https://github.com/user-attachments/assets/b9550ebe-b329-40fe-bce8-449c98931d34)

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/crper/py-image-compress-mcp.git
cd py-image-compress-mcp

# Install dependencies
uv sync

# Test functionality
make examples

# Start MCP server
make run
```

### Basic Usage

```python
from py_image_compress_mcp.compressor import compress_universal

# Single file compression with intelligent format selection
result = compress_universal("photo.jpg")
if result['success']:
    comp_result = result['result']
    print(f"✅ {comp_result.get_summary()}")
    # Output: "2.1 MB → 856 KB (59.2% compression)"
    # Output file: "photo_compress.jpg" (lossless) or "photo_compress_80.jpg" (quality 80)

# Specific format and quality
result = compress_universal(
    input_path="photo.jpg",
    formats="WEBP",
    quality=80,
    max_width=1920,
    max_height=1080
)

# Batch folder compression
result = compress_universal(
    input_path="photos/",
    output_path="compressed_photos/",
    quality=80,
    recursive=True
)
if result['success']:
    batch_result = result['result']
    print(f"📁 {batch_result.get_summary()}")
    # Output: "Processed 15/16 files (93.8% success), saved 12.3 MB"
```

## 📖 API Reference

### 🎯 MCP Tools (Simplified Interface)

The MCP server provides **only 2 core tools** for maximum simplicity and user-friendliness:

#### 1. compress_universal(input_path, output_path=None, formats=None, quality=None, max_width=None, max_height=None, recursive=True)

**Universal compression tool** - intelligently handles all scenarios (files, directories, single/multi-format output):

Universal compression function that automatically detects whether the input is a file or directory and processes accordingly.

**Parameters**:
- `input_path` (str): Input file or directory path
- `output_path` (str | None): Output path (auto-generated with `_compress` suffix if not specified)
- `formats` (str | list[str] | None): Output format(s) - single format like "WEBP" or multiple formats like ["JPEG", "PNG", "WEBP"] (intelligent selection if None)
- `quality` (int | None): Compression quality 1-100 (lossless if None)
- `max_width`, `max_height` (int | None): Maximum dimensions for automatic resizing
- `recursive` (bool): Process subdirectories recursively when input is a directory (default: True)

**Output Naming**:
- Lossless: `original_name_compress.extension`
- Lossy: `original_name_compress_[quality].extension`
- Example: `photo.jpg` → `photo_compress_80.jpg` (quality 80)

#### 2. get_image_info(input_path)

**Image analysis tool** - extracts comprehensive metadata and analysis reports:

**Parameters**:
- `input_path` (str): Image file path

**Returns**: Complete image analysis including:
- Basic info: dimensions, format, file size (with human-readable format), transparency, pixel count (with human-readable format)
- EXIF data: camera info, shooting parameters, GPS data, timestamps (with human-readable format)
- ICC profiles: color space information, creation dates (with human-readable format)
- Complexity analysis: edge density, texture complexity, compression difficulty
- Color histograms: RGB and luminance distribution with brightness statistics

**New Human-Readable Methods**:
- `basic_info.get_file_size_human()` - "2.1 MB", "856 KB"
- `basic_info.get_total_pixels_human()` - "2.1 million", "800 thousand"
- `exif_data.get_datetime_original_human()` - "2 hours ago", "3 days ago"
- `exif_data.get_datetime_digitized_human()` - "1 week ago", "2 months ago"
- `icc_profile.get_creation_date_human()` - "5 years ago", "last month"

### Advanced Usage

```python
from py_image_compress_mcp.compressor import compress_universal

# Multi-format compression - generates multiple output files
result = compress_universal(
    input_path="photo.jpg",
    formats=["JPEG", "PNG", "WEBP"],
    quality=85
)
# Generates: photo_compress_85.jpg, photo_compress_85.png, photo_compress_85.webp

# Directory compression with size constraints
result = compress_universal(
    input_path="photos/",
    output_path="compressed/",
    formats="WEBP",
    quality=80,
    max_width=1920,
    max_height=1080,
    recursive=True
)

# PNG-specific handling (automatically optimized)
result = compress_universal(
    input_path="image.png",
    quality=70  # Small PNGs stay PNG, large ones may convert to JPEG
)
```

## 📊 Result Objects

All operations return a unified `ProcessingResult` format with consistent structure:

### CompressionResult
Single file compression result with detailed metrics:
```python
result["result"].input_path          # Path: Input file path
result["result"].output_path         # Path: Output file path
result["result"].original_size       # int: Original file size in bytes
result["result"].compressed_size     # int: Compressed file size in bytes
result["result"].format_used         # str: Format used for compression
result["result"].quality_used        # int | None: Quality setting used
result["result"].success             # bool: Whether compression succeeded
result["result"].original_dimensions # tuple[int, int]: Original (width, height)
result["result"].final_dimensions    # tuple[int, int]: Final (width, height)
result["result"].was_resized         # bool: Whether image was resized

# Utility methods
result["result"].get_summary()                # "2.1 MB → 856 KB (59.2% compression)"
result["result"].get_compression_ratio()      # 59.2 (percentage)
result["result"].get_size_saved()            # 1244160 (bytes saved)
result["result"].get_original_size_human()   # "2.1 MB"
result["result"].get_compressed_size_human() # "856 KB"
```

### BatchResult
Directory processing with comprehensive statistics:
```python
result["result"].input_dir           # Path: Input directory path
result["result"].output_dir          # Path: Output directory path
result["result"].results             # list[CompressionResult]: All file results
result["result"].success             # bool: Whether any files succeeded

# Utility methods
result["result"].get_summary()               # "Processed 15/16 files (93.8%), saved 12.3 MB"
result["result"].get_success_rate()         # 93.75 (percentage)
result["result"].get_total_size_saved()     # 12884901888 (total bytes saved)
result["result"].get_success_count()        # 15 (number of successful files)
```

## 🤖 MCP Server Integration

### Claude Desktop Configuration

Add to your Claude Desktop configuration:

```json
{
  "mcpServers": {
    "py-image-compress": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/path/to/py-image-compress-mcp",
        "py-image-compress-mcp"
      ]
    }
  }
}
```

### Available Tools

- **compress_universal**: Universal compression function for files and directories
- **get_image_info**: Extract comprehensive image metadata and analysis

### Key Improvements

- **Smart PNG Handling**: PNG files with transparency stay PNG, others may convert to JPEG for better compression
- **No File Size Increase**: Optimized algorithms prevent compressed files from becoming larger than originals
- **Consistent Naming**: Predictable output naming with `_compress` and `_compress_[quality]` suffixes
- **Fast Processing**: Simplified logic for better performance without complex analysis overhead

## �️ Development

```bash
# Setup
git clone https://github.com/crper/py-image-compress-mcp.git
cd py-image-compress-mcp
make setup

# Development workflow
make dev     # Format + lint + test
make test    # Run tests only
make run     # Start MCP server
```

## 📝 License

MIT License - see LICENSE file for details.

## 🔗 Related Projects

- [Pillow](https://pillow.readthedocs.io/) - Python Imaging Library
- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP specification
- [Claude Desktop](https://claude.ai/desktop) - AI assistant with MCP support
