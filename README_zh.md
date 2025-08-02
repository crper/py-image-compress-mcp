# Python Image Compress MCP

[English](README.md) | [中文](README_zh.md)

基于 Python 3.10+ 和 Pillow 11+ 构建的现代化图像压缩 MCP 服务器。为 AI 助手提供智能压缩、统一 API 和全面的元数据分析功能。

## ✨ 特性

- **🎯 简化MCP接口**: 仅提供2个核心工具 - `compress_universal` 和 `get_image_info`
- **🔄 通用处理**: 单一工具智能处理文件、目录、单/多格式输出
- **🧠 智能PNG处理**: 优化的PNG处理逻辑，避免文件大小增加
- **⚡ 智能处理**: 基于图像特征的自动格式选择和质量优化
- **🚀 并行处理**: 可配置线程/进程池的高性能批量压缩
- **📊 丰富元数据**: EXIF 数据、ICC 配置文件、复杂度分析和直方图数据提取
- **🤖 MCP 集成**: 原生支持 Claude Desktop 和其他 MCP 兼容的 AI 助手
- **🐍 现代 Python**: 基于 Python 3.10+ 特性、Pillow 11+ 和全面的类型安全

## 演示视频
[mcp-demo.webm](https://github.com/user-attachments/assets/b9550ebe-b329-40fe-bce8-449c98931d34)

## 🚀 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/crper/py-image-compress-mcp.git
cd py-image-compress-mcp

# 安装依赖
uv sync

# 测试功能
make examples

# 启动 MCP 服务器
make run
```

### 基本用法

```python
from py_image_compress_mcp.compressor import compress_universal

# 单文件压缩，智能格式选择
result = compress_universal("photo.jpg")
if result['success']:
    comp_result = result['result']
    print(f"✅ {comp_result.get_summary()}")
    # 输出: "2.1 MB → 856 KB (59.2% 压缩)"
    # 输出文件: "photo_compress.jpg" (无损) 或 "photo_compress_80.jpg" (质量80)

# 指定格式和质量
result = compress_universal(
    input_path="photo.jpg",
    formats="WEBP",
    quality=80,
    max_width=1920,
    max_height=1080
)

# 批量文件夹压缩
result = compress_universal(
    input_path="photos/",
    output_path="compressed_photos/",
    quality=80,
    recursive=True
)
if result['success']:
    batch_result = result['result']
    print(f"📁 {batch_result.get_summary()}")
    # 输出: "处理 15/16 个文件 (成功率 93.8%), 总节省 12.3 MB"
```

## 📖 API 参考

### 🎯 MCP 工具（简化接口）

MCP 服务器**仅提供2个核心工具**，最大化简洁性和用户友好性：

#### 1. compress_universal(input_path, output_path=None, formats=None, quality=None, max_width=None, max_height=None, recursive=True)

**通用压缩工具** - 智能处理所有场景（文件、目录、单/多格式输出）：

通用压缩函数，自动检测输入是文件还是目录并相应处理。

**参数**:
- `input_path` (str): 输入文件或目录路径
- `output_path` (str | None): 输出路径（未指定时自动生成，带 `_compress` 后缀）
- `formats` (str | list[str] | None): 输出格式 - 单格式如 "WEBP" 或多格式如 ["JPEG", "PNG", "WEBP"]（None 为智能选择）
- `quality` (int | None): 压缩质量 1-100（None 为无损）
- `max_width`, `max_height` (int | None): 自动调整尺寸的最大尺寸
- `recursive` (bool): 当输入为目录时递归处理子目录（默认: True）

**输出命名**:
- 无损: `原文件名_compress.扩展名`
- 有损: `原文件名_compress_[质量].扩展名`
- 示例: `photo.jpg` → `photo_compress_80.jpg` (质量80)

#### 2. get_image_info(input_path)

**图片分析工具** - 提取全面的元数据和分析报告：

**参数**:
- `input_path` (str): 图像文件路径

**返回**: 完整的图片分析，包括：
- 基础信息: 尺寸、格式、文件大小（含人性化格式）、透明度、像素数量（含人性化格式）
- EXIF数据: 相机信息、拍摄参数、GPS数据、时间戳（含人性化格式）
- ICC配置: 色彩空间信息、创建日期（含人性化格式）
- 复杂度分析: 边缘密度、纹理复杂度、压缩难度
- 颜色直方图: RGB和亮度分布，含亮度统计信息

**新增人性化显示方法**:
- `basic_info.get_file_size_human()` - "2.1 MB", "856 KB"
- `basic_info.get_total_pixels_human()` - "210万", "80万"
- `exif_data.get_datetime_original_human()` - "2小时前", "3天前"
- `exif_data.get_datetime_digitized_human()` - "1周前", "2个月前"
- `icc_profile.get_creation_date_human()` - "5年前", "上个月"

### 高级用法

```python
from py_image_compress_mcp.compressor import compress_universal

# 多格式压缩 - 生成多个输出文件
result = compress_universal(
    input_path="photo.jpg",
    formats=["JPEG", "PNG", "WEBP"],
    quality=85
)
# 生成: photo_compress_85.jpg, photo_compress_85.png, photo_compress_85.webp

# 目录压缩，带尺寸限制
result = compress_universal(
    input_path="photos/",
    output_path="compressed/",
    formats="WEBP",
    quality=80,
    max_width=1920,
    max_height=1080,
    recursive=True
)

# PNG特殊处理（自动优化）
result = compress_universal(
    input_path="image.png",
    quality=70  # 小PNG保持PNG格式，大PNG可能转换为JPEG
)
```

## 📊 结果对象

所有操作返回统一的 `ProcessingResult` 格式，具有一致的结构：

### CompressionResult
单文件压缩结果，包含详细指标：
```python
result["result"].input_path          # Path: 输入文件路径
result["result"].output_path         # Path: 输出文件路径
result["result"].original_size       # int: 原始文件大小（字节）
result["result"].compressed_size     # int: 压缩后文件大小（字节）
result["result"].format_used         # str: 使用的压缩格式
result["result"].quality_used        # int | None: 使用的质量设置
result["result"].success             # bool: 压缩是否成功
result["result"].original_dimensions # tuple[int, int]: 原始尺寸 (宽, 高)
result["result"].final_dimensions    # tuple[int, int]: 最终尺寸 (宽, 高)
result["result"].was_resized         # bool: 是否进行了尺寸调整

# 实用方法
result["result"].get_summary()                # "2.1 MB → 856 KB (59.2% 压缩)"
result["result"].get_compression_ratio()      # 59.2 (压缩百分比)
result["result"].get_size_saved()            # 1244160 (节省的字节数)
result["result"].get_original_size_human()   # "2.1 MB"
result["result"].get_compressed_size_human() # "856 KB"
```

### BatchResult
目录处理，包含全面统计信息：
```python
result["result"].input_dir           # Path: 输入目录路径
result["result"].output_dir          # Path: 输出目录路径
result["result"].results             # list[CompressionResult]: 所有文件结果
result["result"].success             # bool: 是否有任何文件成功

# 实用方法
result["result"].get_summary()               # "处理 15/16 个文件 (成功率 93.8%), 总节省 12.3 MB"
result["result"].get_success_rate()         # 93.75 (成功率百分比)
result["result"].get_total_size_saved()     # 12884901888 (总节省字节数)
result["result"].get_success_count()        # 15 (成功处理的文件数)
```

## 🤖 MCP 服务器集成

### Claude Desktop 配置

添加到您的 Claude Desktop 配置中：

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

### 可用工具

- **compress_universal**: 文件和目录的通用压缩函数
- **get_image_info**: 提取全面的图像元数据和分析

### 主要改进

- **智能PNG处理**: 有透明度的PNG保持PNG格式，其他可能转换为JPEG以获得更好压缩
- **避免文件变大**: 优化算法防止压缩后文件比原文件更大
- **一致命名**: 可预测的输出命名，使用 `_compress` 和 `_compress_[质量]` 后缀
- **快速处理**: 简化逻辑提高性能，无复杂分析开销

## �️ 开发

```bash
# 设置
git clone https://github.com/crper/py-image-compress-mcp.git
cd py-image-compress-mcp
make setup

# 开发工作流
make dev     # 格式化 + 代码检查 + 测试
make test    # 仅运行测试
make run     # 启动 MCP 服务器
```

## 📝 许可证

MIT 许可证 - 详见 LICENSE 文件。

## 🔗 相关项目

- [Pillow](https://pillow.readthedocs.io/) - Python 图像库
- [Model Context Protocol](https://modelcontextprotocol.io/) - MCP 规范
- [Claude Desktop](https://claude.ai/desktop) - 支持 MCP 的 AI 助手
