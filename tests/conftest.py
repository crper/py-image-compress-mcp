"""测试配置文件。

提供测试所需的fixtures和配置。
"""

import tempfile
from pathlib import Path

import pytest
from PIL import Image, ImageDraw


def _create_missing_test_images(images: dict[str, Path]) -> None:
    """创建缺失的测试图片"""
    if len(images) >= 3:
        return

    temp_dir = Path("tmp/test_images")
    temp_dir.mkdir(parents=True, exist_ok=True)

    if "large" not in images:
        large_path = temp_dir / "large.png"
        large_img = Image.new("RGB", (1000, 800), color="white")
        draw = ImageDraw.Draw(large_img)
        for i in range(50):
            x, y = (i * 20) % 1000, (i * 16) % 800
            color = (i * 5 % 256, i * 7 % 256, i * 11 % 256)
            draw.rectangle([x, y, x + 50, y + 40], fill=color)
        large_img.save(large_path, "PNG")
        images["large"] = large_path

    if "transparent" not in images:
        transparent_path = temp_dir / "transparent.png"
        transparent_img = Image.new("RGBA", (400, 400), color=(0, 0, 0, 0))
        draw = ImageDraw.Draw(transparent_img)
        for i in range(10):
            x, y = i * 40, i * 40
            alpha = 100 + (i * 15) % 155
            draw.ellipse(
                [x, y, x + 100, y + 100],
                fill=(255 - i * 20, 100 + i * 15, i * 25, alpha),
            )
        transparent_img.save(transparent_path, "PNG")
        images["transparent"] = transparent_path


def _create_standard_test_images(images: dict[str, Path]) -> None:
    """创建标准的小图片和超小图片"""
    temp_dir = Path("tmp/test_images")
    temp_dir.mkdir(parents=True, exist_ok=True)

    small_path = temp_dir / "small.png"
    small_img = Image.new("RGB", (50, 50), color="red")
    small_img.save(small_path, "PNG")
    images["small"] = small_path

    tiny_path = temp_dir / "tiny.png"
    tiny_img = Image.new("RGB", (20, 20), color="blue")
    tiny_img.save(tiny_path, "PNG")
    images["tiny"] = tiny_path


@pytest.fixture
def temp_dir():
    """临时目录fixture"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_images() -> dict[str, Path]:
    """使用 public/images 中的真实素材图片"""
    project_root = Path(__file__).parent.parent
    images_dir = project_root / "public" / "images"

    if not images_dir.exists():
        pytest.skip("public/images 目录不存在，跳过测试")

    # 收集所有可用的图片文件
    image_files = list(images_dir.glob("*"))
    image_files = [
        f for f in image_files if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ]

    if not image_files:
        pytest.skip("public/images 目录中没有找到图片文件")

    images = {}

    # 按文件大小排序，选择不同类型的图片
    image_files.sort(key=lambda x: x.stat().st_size, reverse=True)

    # 选择最大的作为 large
    if len(image_files) >= 1:
        images["large"] = image_files[0]

    # 选择 JPEG 格式的图片
    jpeg_files = [f for f in image_files if f.suffix.lower() in {".jpg", ".jpeg"}]
    if jpeg_files:
        images["jpeg"] = jpeg_files[0]
    elif len(image_files) >= 2:
        images["jpeg"] = image_files[1]

    # 选择 WebP 格式的图片作为透明图片测试（WebP支持透明度）
    webp_files = [f for f in image_files if f.suffix.lower() == ".webp"]
    if webp_files:
        images["transparent"] = webp_files[0]
    elif len(image_files) >= 3:
        images["transparent"] = image_files[2]

    # 创建必要的测试图片
    _create_missing_test_images(images)
    _create_standard_test_images(images)

    return images


@pytest.fixture
def output_dir() -> Path:
    """输出目录fixture - 使用项目的 tmp 目录"""
    project_root = Path(__file__).parent.parent
    output_dir = project_root / "tmp" / "test_output"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def create_config(**kwargs):
    """创建完整的CompressionConfig，提供默认值"""
    from py_image_compress_mcp.models.compression_config import (
        CompressionConfig,
        QualityMode,
    )

    defaults = {
        "output_path": None,
        "output_dir": None,
        "quality_mode": QualityMode.LOSSLESS,
        "custom_quality": None,
        "target_format": None,
        "target_formats": None,
        "preserve_format": True,
        "resize_config": None,
        "optimize": True,
        "progressive": True,
        "strip_metadata": False,
        "fallback_to_original": False,
    }
    defaults.update(kwargs)
    return CompressionConfig(**defaults)
