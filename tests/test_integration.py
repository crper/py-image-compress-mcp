"""集成测试。

测试端到端功能和核心集成。
"""

from pathlib import Path

import pytest

from py_image_compress_mcp.compressor import ImageCompressor
from py_image_compress_mcp.models.compression_config import QualityMode
from tests.conftest import create_config


class TestImageCompressor:
    """图像压缩器核心功能测试"""

    @pytest.fixture
    def compressor(self):
        return ImageCompressor()

    def test_compress_basic_functionality(
        self, compressor, sample_images: dict[str, Path], output_dir: Path
    ):
        """测试基本压缩功能"""
        output_path = output_dir / "test_basic.jpg"
        result = compressor.compress_image(
            input_path=sample_images["large"],
            output_path=output_path,
            quality=80,
            format="JPEG",
        )

        assert result.success
        assert result.output_path.exists()
        assert result.get_compression_ratio() >= 0

    def test_compress_transparent_image(
        self, compressor, sample_images: dict[str, Path], output_dir: Path
    ):
        """测试透明图片压缩"""
        output_path = output_dir / "test_transparent.png"
        result = compressor.compress_image(
            input_path=sample_images["transparent"],
            output_path=output_path,
            quality=95,
        )

        assert result.success
        assert result.format_used in ["PNG", "WEBP"]


class TestMCPServer:
    """MCP服务器功能测试"""

    def test_mcp_server_imports(self):
        """测试MCP服务器模块导入"""
        from py_image_compress_mcp.mcp_server import mcp

        assert mcp is not None

    def test_mcp_core_tools(self):
        """测试 MCP 核心工具 - 只有两个工具"""
        from py_image_compress_mcp.mcp_server import compress_universal, get_image_info

        # 测试通用压缩工具
        assert compress_universal is not None
        assert hasattr(compress_universal, "name")
        assert compress_universal.name == "compress_universal"

        # 测试图片信息工具
        assert get_image_info is not None
        assert hasattr(get_image_info, "name")
        assert get_image_info.name == "get_image_info"


class TestEndToEnd:
    """端到端核心测试"""

    def test_complete_workflow(self, sample_images: dict[str, Path], output_dir: Path):
        """测试完整工作流程"""
        from py_image_compress_mcp.core.compression_engine import process_image

        config = create_config(
            input_path=sample_images["large"],
            output_dir=output_dir,
            quality_mode=QualityMode.CUSTOM,
            custom_quality=78,
        )

        result = process_image(config)
        assert result.success
        assert result.output_path.exists()

    def test_error_recovery(self, output_dir: Path):
        """测试错误恢复"""
        from py_image_compress_mcp.core.compression_engine import process_image

        config = create_config(
            input_path=Path("/nonexistent/file.jpg"),
            output_dir=output_dir,
            quality_mode=QualityMode.CUSTOM,
            custom_quality=78,
        )

        result = process_image(config)
        assert not result.success
        assert result.error is not None
