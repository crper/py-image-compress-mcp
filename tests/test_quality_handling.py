"""质量参数处理测试。"""

from pathlib import Path

from py_image_compress_mcp.core.compression_engine import process_image
from py_image_compress_mcp.models.compression_config import QualityMode
from tests.conftest import create_config


class TestQualityHandling:
    """质量参数核心测试"""

    def test_custom_quality_preserved(
        self, sample_images: dict[str, Path], output_dir: Path
    ):
        """测试用户指定的质量值被正确保留"""
        config = create_config(
            input_path=sample_images["large"],
            output_dir=output_dir,
            quality_mode=QualityMode.CUSTOM,
            custom_quality=85,
            target_format="JPEG",
        )

        result = process_image(config)
        assert result.success
        assert result.quality_used == 85
        assert result.output_path.exists()

    def test_quality_100_handling(
        self, sample_images: dict[str, Path], output_dir: Path
    ):
        """测试质量值100的处理 - 自动降到98避免文件过大"""
        config = create_config(
            input_path=sample_images["large"],
            output_dir=output_dir,
            quality_mode=QualityMode.CUSTOM,
            custom_quality=100,
            target_format="JPEG",
        )

        result = process_image(config)
        assert result.success
        # 质量100会被自动降到98以避免文件过大
        assert result.quality_used == 98
        assert result.output_path.exists()

    def test_lossless_mode(self, sample_images: dict[str, Path], output_dir: Path):
        """测试无损模式"""
        config = create_config(
            input_path=sample_images["large"],
            output_dir=output_dir,
            quality_mode=QualityMode.LOSSLESS,
            target_format="PNG",
        )

        result = process_image(config)
        assert result.success
        assert result.format_used == "PNG"
        assert result.output_path.exists()
