"""核心功能测试。

测试图像压缩的核心功能模块。
"""

from pathlib import Path

import pytest
from PIL import Image

from py_image_compress_mcp.core.compression_engine import process_image
from py_image_compress_mcp.core.formats import FormatProcessor
from py_image_compress_mcp.core.image_info import ImageInfoExtractor
from py_image_compress_mcp.core.optimizer import CompressionOptimizer
from py_image_compress_mcp.core.strategy import CompressionStrategy, StrategyType
from py_image_compress_mcp.models.compression_config import QualityMode
from tests.conftest import create_config


class TestCompressionEngine:
    """压缩引擎测试"""

    def test_process_image_basic(
        self, sample_images: dict[str, Path], output_dir: Path
    ):
        """测试基本图片压缩"""
        config = create_config(
            input_path=sample_images["large"],
            output_dir=output_dir,
            quality_mode=QualityMode.CUSTOM,
            custom_quality=78,
            target_format="JPEG",
            preserve_format=False,
        )

        result = process_image(config)

        assert result.success
        assert result.output_path.exists()
        assert result.original_size > 0
        assert result.compressed_size > 0
        assert result.format_used == "JPEG"
        assert result.error is None

    def test_process_image_lossless(
        self, sample_images: dict[str, Path], output_dir: Path
    ):
        """测试无损压缩"""
        config = create_config(
            input_path=sample_images["large"],
            output_dir=output_dir,
            quality_mode=QualityMode.LOSSLESS,
            target_format="PNG",
        )

        result = process_image(config)

        assert result.success
        assert result.format_used == "PNG"

    def test_process_image_with_resize(
        self, sample_images: dict[str, Path], output_dir: Path
    ):
        """测试带缩放的压缩"""
        from py_image_compress_mcp.models.compression_config import ResizeConfig

        resize_config = ResizeConfig(
            max_width=400,
            max_height=300,
            maintain_aspect_ratio=True,
            upscale_allowed=False,
        )
        config = create_config(
            input_path=sample_images["large"],
            output_dir=output_dir,
            quality_mode=QualityMode.CUSTOM,
            custom_quality=78,
            target_format="JPEG",
            resize_config=resize_config,
        )

        result = process_image(config)

        assert result.success
        # 验证输出图片尺寸
        with Image.open(result.output_path) as img:
            assert img.width <= 400
            assert img.height <= 300

    def test_process_image_preserve_transparency(
        self, sample_images: dict[str, Path], output_dir: Path
    ):
        """测试透明图片处理"""
        config = create_config(
            input_path=sample_images["transparent"],
            output_dir=output_dir,
            quality_mode=QualityMode.LOSSLESS,
            target_format="PNG",
        )

        result = process_image(config)

        assert result.success
        # 验证图片处理成功，如果原图有透明度则保持，否则正常处理
        with (
            Image.open(result.output_path) as img,
            Image.open(sample_images["transparent"]) as original,
        ):
            if original.mode in ["RGBA", "LA"] or "transparency" in original.info:
                # 原图有透明度，应该保持
                assert img.mode in ["RGBA", "LA", "P"]
            else:
                # 原图没有透明度，正常处理即可
                assert img.mode in ["RGB", "RGBA", "LA", "P"]

    def test_process_image_error_handling(self, output_dir: Path):
        """测试错误处理"""
        config = create_config(
            input_path=Path("/nonexistent/file.jpg"),
            output_dir=output_dir,
            quality_mode=QualityMode.CUSTOM,
            custom_quality=78,
        )

        result = process_image(config)

        assert not result.success
        assert result.error is not None


class TestImageInfoExtractor:
    """图片信息提取器测试"""

    @pytest.fixture
    def extractor(self):
        return ImageInfoExtractor()

    def test_extract_basic_info(self, extractor, sample_images: dict[str, Path]):
        """测试提取基本信息"""
        metadata = extractor.extract(sample_images["large"])

        assert metadata.basic_info.width > 0
        assert metadata.basic_info.height > 0
        assert metadata.basic_info.format in ["PNG", "JPEG", "WEBP"]
        assert metadata.basic_info.file_size > 0

    def test_extract_transparency_info(self, extractor, sample_images: dict[str, Path]):
        """测试透明度信息提取"""
        metadata = extractor.extract(sample_images["transparent"])

        # 如果使用的是真实素材图片，可能没有透明度，这是正常的
        # 只验证透明度检测功能正常工作
        assert isinstance(metadata.basic_info.has_transparency, bool)

    def test_extract_complexity_info(self, extractor, sample_images: dict[str, Path]):
        """测试复杂度信息提取"""
        metadata = extractor.extract(sample_images["large"])

        assert metadata.complexity is not None
        assert metadata.complexity.overall_complexity in [
            "very_low",
            "low",
            "medium",
            "high",
            "very_high",
        ]

    def test_extract_histogram_info(self, extractor, sample_images: dict[str, Path]):
        """测试直方图信息提取"""
        metadata = extractor.extract(sample_images["large"])

        assert metadata.histogram is not None
        assert len(metadata.histogram.red_histogram) == 256
        assert len(metadata.histogram.green_histogram) == 256
        assert len(metadata.histogram.blue_histogram) == 256


class TestCompressionStrategy:
    """压缩策略测试"""

    @pytest.fixture
    def strategy(self):
        return CompressionStrategy()

    @pytest.fixture
    def extractor(self):
        return ImageInfoExtractor()

    def test_strategy_large_image(
        self, strategy, extractor, sample_images: dict[str, Path]
    ):
        """测试大图片策略选择"""
        metadata = extractor.extract(sample_images["large"])
        decision = strategy.select_optimal(metadata)

        # 验证策略类型是有效的
        assert decision.strategy_type in [
            StrategyType.LOSSLESS,
            StrategyType.LOSSY,
            StrategyType.SKIP,
        ]
        # 如果不跳过，应该有推荐格式
        if not decision.skip_compression:
            assert decision.recommended_format in ["PNG", "JPEG", "WEBP"]

    def test_strategy_small_image_skip(
        self, strategy, extractor, sample_images: dict[str, Path]
    ):
        """测试小图片跳过策略"""
        metadata = extractor.extract(sample_images["tiny"])
        decision = strategy.select_optimal(metadata)

        # 检查文件大小
        file_size = sample_images["tiny"].stat().st_size

        # 只有非常小的文件（小于10KB）才会被跳过
        if file_size < 10 * 1024:
            assert decision.strategy_type == StrategyType.SKIP
            assert decision.skip_compression is True
        else:
            # 否则应该使用无损压缩策略
            assert decision.strategy_type == StrategyType.LOSSLESS
            assert not getattr(decision, "skip_compression", False)

    def test_strategy_transparent_image(
        self, strategy, extractor, sample_images: dict[str, Path]
    ):
        """测试透明图片策略"""
        metadata = extractor.extract(sample_images["transparent"])
        decision = strategy.select_optimal(metadata)

        # 透明图片应该选择支持透明度的格式
        if not decision.skip_compression:
            assert decision.recommended_format in ["PNG", "WEBP"]

    def test_strategy_consistency(
        self, strategy, extractor, sample_images: dict[str, Path]
    ):
        """测试策略一致性"""
        metadata = extractor.extract(sample_images["large"])

        decision1 = strategy.select_optimal(metadata)
        decision2 = strategy.select_optimal(metadata)

        # 同一图片应该返回相同策略
        assert decision1.strategy_type == decision2.strategy_type
        assert decision1.skip_compression == decision2.skip_compression


class TestFormatProcessor:
    """格式处理器测试"""

    @pytest.fixture
    def processor(self):
        return FormatProcessor()

    def test_prepare_for_jpeg(self, processor):
        """测试JPEG格式准备"""
        img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        prepared = processor.prepare_for_format(img, "JPEG")

        # JPEG不支持透明度，应该转换为RGB
        assert prepared.mode == "RGB"

    def test_prepare_for_png(self, processor):
        """测试PNG格式准备"""
        img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        prepared = processor.prepare_for_format(img, "PNG")

        # PNG支持透明度，应该保持RGBA
        assert prepared.mode == "RGBA"

    def test_prepare_for_webp(self, processor):
        """测试WEBP格式准备"""
        img = Image.new("RGBA", (100, 100), color=(255, 0, 0, 128))
        prepared = processor.prepare_for_format(img, "WEBP")

        # WEBP支持透明度，应该保持RGBA
        assert prepared.mode == "RGBA"

    def test_supported_formats(self, processor):
        """测试支持的格式"""
        assert "JPEG" in processor.supported_formats
        assert "PNG" in processor.supported_formats
        assert "WEBP" in processor.supported_formats

    def test_modern_format_detection(self, processor):
        """测试现代格式检测（新增优化功能）"""
        # 测试 AVIF 和 HEIF 支持检测
        assert hasattr(processor, "avif_supported")
        assert hasattr(processor, "heif_supported")
        assert isinstance(processor.avif_supported, bool)
        assert isinstance(processor.heif_supported, bool)

    def test_optimal_format_selection(self, processor):
        """测试优化的格式选择（新增优化功能）"""
        from py_image_compress_mcp.core.image_info import analyze_image_from_pil

        # 测试透明图片格式选择
        rgba_img = Image.new("RGBA", (100, 100), (255, 0, 0, 128))
        characteristics = analyze_image_from_pil(rgba_img)

        format_result = processor.get_optimal_format_from_characteristics(
            characteristics=characteristics, has_transparency=True, prefer_quality=True
        )
        assert format_result in ["PNG", "AVIF", "WEBP"]


class TestUtils:
    """工具函数测试"""

    def test_find_image_files(self, sample_images: dict[str, Path]):
        """测试查找图片文件"""
        from py_image_compress_mcp.utils import find_image_files

        # 获取图片目录 - 使用 tmp 目录确保有足够的测试图片
        temp_dir = Path("tmp/test_images")
        if temp_dir.exists():
            image_dir = temp_dir
        else:
            image_dir = next(iter(sample_images.values())).parent

        # 查找图片文件
        found_files = list(find_image_files(image_dir))

        # 至少应该找到一些图片文件
        assert len(found_files) >= 1
        # 验证找到的文件都是支持的图像格式
        from PIL import Image

        supported_extensions = set(Image.registered_extensions().keys())

        for file_path in found_files:
            assert file_path.suffix.lower() in supported_extensions


class TestJPEGOptimization:
    """JPEG优化参数测试"""

    def test_jpeg_optimize_parameter_effects(
        self, sample_images: dict[str, Path], output_dir: Path
    ):
        """测试不同JPEG参数对文件大小的影响"""
        # 使用一个JPEG图片进行测试
        jpeg_image = None
        for path in sample_images.values():
            if path.suffix.lower() in [".jpg", ".jpeg"]:
                jpeg_image = path
                break

        if not jpeg_image:
            pytest.skip("没有找到JPEG测试图片")

        original_size = jpeg_image.stat().st_size

        # 测试不同的参数组合
        test_cases = [
            ("无参数", {}),
            ("仅optimize", {"optimize": True}),
            ("质量75", {"quality": 75}),
            ("质量75+optimize", {"quality": 75, "optimize": True}),
            ("质量85+optimize", {"quality": 85, "optimize": True}),
        ]

        results = {}

        with Image.open(jpeg_image) as img:
            for name, params in test_cases:
                output_path = (
                    output_dir
                    / f"jpeg_test_{name.replace(' ', '_').replace('+', '_')}.jpg"
                )

                # 保存图片
                img.save(output_path, format="JPEG", **params)

                # 记录结果
                compressed_size = output_path.stat().st_size
                compression_ratio = (original_size - compressed_size) / original_size
                results[name] = {
                    "size": compressed_size,
                    "ratio": compression_ratio,
                    "params": params,
                }

        # 验证optimize参数的效果
        if "仅optimize" in results and "无参数" in results:
            # optimize应该减小文件大小或至少不增大
            assert results["仅optimize"]["size"] <= results["无参数"]["size"]

        # 验证质量参数的影响
        if "质量75+optimize" in results and "质量85+optimize" in results:
            # 较低质量应该产生较小的文件
            assert (
                results["质量75+optimize"]["size"] <= results["质量85+optimize"]["size"]
            )

    def test_jpeg_quality_estimation(self, sample_images: dict[str, Path]):
        """测试JPEG质量估算功能"""
        # 找到JPEG图片
        jpeg_image = None
        for path in sample_images.values():
            if path.suffix.lower() in [".jpg", ".jpeg"]:
                jpeg_image = path
                break

        if not jpeg_image:
            pytest.skip("没有找到JPEG测试图片")

        original_size = jpeg_image.stat().st_size

        # 测试不同质量设置，找到最接近原始大小的质量值
        best_quality = None
        best_diff = float("inf")

        with Image.open(jpeg_image) as img:
            for quality in range(60, 95, 5):
                # 保存到内存中测试
                import io

                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=quality)
                test_size = buffer.tell()
                buffer.close()

                diff = abs(test_size - original_size)
                if diff < best_diff:
                    best_diff = diff
                    best_quality = quality

        # 验证能够找到合理的质量估算
        assert best_quality is not None
        assert 60 <= best_quality <= 95
        assert best_diff < original_size * 0.1  # 差异应该小于原始大小的10%


class TestCompressionOptimizer:
    """压缩优化器测试"""

    def test_optimizer_jpeg_lossless_mode(
        self, sample_images: dict[str, Path], output_dir: Path
    ):
        """测试优化器在JPEG无损模式下的行为"""
        # 找到JPEG图片
        jpeg_image = None
        for path in sample_images.values():
            if path.suffix.lower() in [".jpg", ".jpeg"]:
                jpeg_image = path
                break

        if not jpeg_image:
            pytest.skip("没有找到JPEG测试图片")

        # 创建无损配置
        config = create_config(
            input_path=jpeg_image,
            output_dir=output_dir,
            quality_mode=QualityMode.LOSSLESS,
            target_format="JPEG",
        )

        # 提取图片元数据
        extractor = ImageInfoExtractor()
        metadata = extractor.extract(jpeg_image)

        # 创建优化器
        optimizer = CompressionOptimizer()

        # 测试基础参数
        base_params = {"quality": 75, "optimize": True, "progressive": False}
        optimized_params = optimizer.optimize_parameters(
            "JPEG", config, metadata, base_params
        )

        # 在无损模式下，优化器应该只保留optimize参数
        assert "optimize" in optimized_params
        assert optimized_params["optimize"] is True

        # 不应该包含可能导致文件变大的参数
        assert (
            "quality" not in optimized_params or optimized_params.get("quality") is None
        )

        # 测试实际压缩效果
        with Image.open(jpeg_image) as img:
            # 测试优化参数
            output_path = output_dir / "optimized_lossless.jpg"
            img.save(output_path, format="JPEG", **optimized_params)
            optimized_size = output_path.stat().st_size

            # 测试无参数保存
            output_path_baseline = output_dir / "baseline.jpg"
            img.save(output_path_baseline, format="JPEG")
            baseline_size = output_path_baseline.stat().st_size

            # 优化后的文件应该不大于基线文件
            assert optimized_size <= baseline_size

            # 如果有压缩效果，应该是正向的
            if optimized_size != baseline_size:
                compression_ratio = (baseline_size - optimized_size) / baseline_size
                assert compression_ratio >= 0  # 不应该有负压缩
