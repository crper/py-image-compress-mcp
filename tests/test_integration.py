"""集成测试。

测试端到端功能和核心集成。
"""

import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from py_image_compress_mcp.compressor import ImageCompressor
from py_image_compress_mcp.config import get_default_max_workers, reset_config
from py_image_compress_mcp.engine.batch import BatchProcessor
from py_image_compress_mcp.engine.concurrent_executor import ConcurrentExecutor
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
        from py_image_compress_mcp.mcp_server import (
            compress_universal,
            create_server,
            get_image_info,
            mcp,
        )

        # 测试通用压缩工具
        assert compress_universal is not None

        # 测试图片信息工具
        assert get_image_info is not None

        tool_names = {tool.name for tool in asyncio.run(mcp.list_tools())}
        assert tool_names == {"compress_universal", "get_image_info"}
        created_tool_names = {tool.name for tool in asyncio.run(create_server().list_tools())}
        assert created_tool_names == {"compress_universal", "get_image_info"}

    def test_get_image_info_supports_lightweight_detail(
        self, sample_images: dict[str, Path]
    ):
        """测试 get_image_info 轻量返回模式。"""
        from py_image_compress_mcp.mcp_server import get_image_info

        result = get_image_info(str(sample_images["large"]), detail="basic")

        assert result["success"] is True
        assert "histogram" not in result
        assert "complexity" not in result

    def test_get_image_info_defaults_to_summary(
        self, sample_images: dict[str, Path]
    ):
        """测试 get_image_info 默认返回 summary。"""
        from py_image_compress_mcp.mcp_server import get_image_info

        result = get_image_info(str(sample_images["large"]))

        assert result["success"] is True
        assert "complexity" in result
        assert "histogram" not in result

    def test_get_image_info_full_preserves_original_histogram(
        self, temp_dir: Path
    ):
        """测试 full 模式返回原图像素级直方图。"""
        from py_image_compress_mcp.mcp_server import get_image_info

        image_path = temp_dir / "large_histogram.png"
        Image.new("RGB", (1000, 1000), color="white").save(image_path)

        result = get_image_info(str(image_path), detail="full")

        assert result["success"] is True
        assert "histogram" in result
        assert sum(result["histogram"]["red_histogram"]) == 1000 * 1000

    def test_compress_universal_propagates_top_level_error(
        self, sample_images: dict[str, Path], temp_dir: Path
    ):
        """测试 MCP 顶层错误字段会透传处理失败。"""
        from py_image_compress_mcp.mcp_server import compress_universal

        output_dir = temp_dir / "existing-output-dir"
        output_dir.mkdir()

        result = compress_universal(
            input_path=str(sample_images["jpeg"]),
            output_path=str(output_dir),
            quality=80,
            formats="JPEG",
        )

        assert result["success"] is False
        assert isinstance(result["error"], str)
        assert result["error"]

    def test_compress_universal_empty_directory_returns_failure(self, temp_dir: Path):
        """测试空目录压缩返回明确失败，而不是成功+错误并存。"""
        from py_image_compress_mcp.mcp_server import compress_universal

        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        result = compress_universal(str(empty_dir))

        assert result["success"] is False
        assert result["error"] == "未找到图像文件"
        assert result["result"]["total_files"] == 0

    def test_compress_universal_rejects_invalid_format_list(
        self, sample_images: dict[str, Path], temp_dir: Path
    ):
        """测试多格式请求遇到非法格式时直接失败。"""
        from py_image_compress_mcp.mcp_server import compress_universal

        result = compress_universal(
            input_path=str(sample_images["jpeg"]),
            output_path=str(temp_dir / "out"),
            formats=["WEBP", "NOT_A_FORMAT"],
            quality=80,
        )

        assert result["success"] is False
        assert isinstance(result["error"], str)
        assert "NOT_A_FORMAT" in result["error"]

    def test_compress_universal_skip_uses_note_not_top_level_error(
        self, temp_dir: Path
    ):
        """测试 skip 信息放在 note，而不是顶层 error。"""
        from py_image_compress_mcp.mcp_server import compress_universal

        image_path = temp_dir / "skip-note.jpg"
        Image.new("RGB", (3000, 2000), color="white").save(
            image_path, "JPEG", quality=35, optimize=True
        )

        result = compress_universal(
            input_path=str(image_path),
            output_path=str(temp_dir / "out.jpg"),
            formats="JPEG",
            quality=80,
        )

        assert result["success"] is True
        assert result["error"] is None
        assert result["result"]["success"] is True
        assert result["result"]["error"] is None
        assert result["result"]["skipped"] is True
        assert isinstance(result["result"]["note"], str)
        assert result["result"]["note"]


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

    def test_batch_results_keep_input_order(
        self, sample_images: dict[str, Path], temp_dir: Path
    ):
        """测试批量结果顺序与输入顺序一致。"""
        source_dir = temp_dir / "ordered"
        source_dir.mkdir()

        ordered_inputs = [
            sample_images["large"],
            sample_images["jpeg"],
            sample_images["transparent"],
        ]
        expected_paths: list[Path] = []
        for index, source in enumerate(ordered_inputs):
            destination = source_dir / f"{index:02d}_{source.name}"
            destination.write_bytes(source.read_bytes())
            expected_paths.append(destination)

        processor = BatchProcessor(max_workers=3, force_executor_type="thread")
        result = processor.process_directory(
            input_dir=source_dir,
            output_dir=temp_dir / "output",
            quality=80,
            format="JPEG",
            recursive=False,
        )

        actual_paths = [item.input_path for item in result.results]
        assert actual_paths == expected_paths

    def test_batch_processing_skips_existing_output_tree(self, temp_dir: Path):
        """测试输出目录位于输入目录内时，不会重复处理旧产物。"""
        input_dir = temp_dir / "downloads"
        input_dir.mkdir()

        source_image = input_dir / "source.png"
        Image.new("RGB", (80, 80), color="red").save(source_image)

        old_output_root = input_dir / "minify-img"
        old_output_root.mkdir()
        old_output = old_output_root / "previous.webp"
        Image.new("RGB", (40, 40), color="blue").save(old_output, "WEBP")

        processor = BatchProcessor(max_workers=2, force_executor_type="thread")
        result = processor.process_directory(
            input_dir=input_dir,
            output_dir=old_output_root / "batch-webp",
            quality=80,
            format="WEBP",
            recursive=True,
        )

        processed_inputs = [item.input_path for item in result.results]

        assert result.success
        assert processed_inputs == [source_image]

    def test_fallback_cleanup_does_not_leave_temp_files(
        self, sample_images: dict[str, Path], temp_dir: Path
    ):
        """测试回退逻辑不会残留临时文件。"""
        compressor = ImageCompressor(max_workers=1)

        result = compressor.compress_image(
            input_path=sample_images["jpeg"],
            output_dir=temp_dir,
            quality=80,
            format="JPEG",
        )

        assert result.success
        assert result.output_path.exists()
        assert not list(temp_dir.glob(".*"))

    def test_default_max_workers_can_be_overridden(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """测试默认并发数支持环境变量覆盖。"""
        monkeypatch.setenv("PIC_MAX_WORKERS", "3")
        reset_config()

        try:
            assert get_default_max_workers() == 3
            assert ImageCompressor().max_workers == 3
        finally:
            monkeypatch.delenv("PIC_MAX_WORKERS", raising=False)
            reset_config()

    def test_zero_max_workers_still_raises_validation_error(self):
        """测试 max_workers=0 仍然视为无效配置。"""
        with pytest.raises(Exception, match="max_workers 必须大于 0"):
            ImageCompressor(max_workers=0)

    def test_embedded_context_falls_back_to_thread_pool(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """测试内嵌执行上下文会回退到线程池。"""
        monkeypatch.setitem(
            sys.modules, "__main__", SimpleNamespace(__file__="<stdin>")
        )

        executor = ConcurrentExecutor(max_workers=4)
        selected = executor._choose_executor([create_config(input_path=Path(__file__))])

        assert selected.__name__ == "ThreadPoolExecutor"

    def test_existing_directory_output_path_returns_failure(
        self, sample_images: dict[str, Path], temp_dir: Path
    ):
        """测试输出路径是目录时返回失败。"""
        compressor = ImageCompressor(max_workers=1)
        output_dir = temp_dir / "existing-output-dir"
        output_dir.mkdir()

        result = compressor.compress_image(
            input_path=sample_images["jpeg"],
            output_path=output_dir,
            quality=80,
            format="JPEG",
        )

        assert not result.success
        assert result.error is not None

    def test_batch_processing_default_output_skips_generated_files_on_rerun(
        self, temp_dir: Path
    ):
        """测试同目录重复运行时不会再次处理自动生成的压缩产物。"""
        input_dir = temp_dir / "photos"
        input_dir.mkdir()

        source_image = input_dir / "source.png"
        Image.new("RGB", (80, 80), color="red").save(source_image)

        processor = BatchProcessor(max_workers=1, force_executor_type="thread")

        first_result = processor.process_directory(
            input_dir=input_dir,
            output_dir=None,
            quality=80,
            format="JPEG",
            recursive=False,
        )
        assert first_result.success
        assert [item.input_path.name for item in first_result.results] == ["source.png"]

        second_result = processor.process_directory(
            input_dir=input_dir,
            output_dir=None,
            quality=80,
            format="JPEG",
            recursive=False,
        )

        assert second_result.success
        assert [item.input_path.name for item in second_result.results] == ["source.png"]
