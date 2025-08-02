#!/usr/bin/env python3
"""现代化图像压缩演示脚本。

展示 py_image_compress_mcp 库的核心功能，包括：
- 单文件压缩（智能策略、质量对比）
- 多格式压缩
- 批量目录处理
- 智能压缩策略分析
- JPEG质量估算和参数优化
"""

import shutil
from pathlib import Path

from PIL import Image

from py_image_compress_mcp import (
    BatchResult,
    CompressionResult,
    ImageCompressor,
    MultiFormatResult,
    compress_universal,
)
from py_image_compress_mcp.core.image_info import ImageInfoExtractor
from py_image_compress_mcp.core.strategy import CompressionStrategy
from py_image_compress_mcp.models import (
    CompressionValidators,
    ImageFormats,
)


def get_sample_images() -> list[Path]:
    """获取 public/images 中的素材图片"""
    project_root = Path(__file__).parent.parent
    images_dir = project_root / "public" / "images"

    if not images_dir.exists():
        print("⚠️ public/images 目录不存在，将创建测试图像")
        return []

    # 收集所有图片文件
    image_files = []
    for ext in [".jpg", ".jpeg", ".png", ".webp"]:
        image_files.extend(images_dir.glob(f"*{ext}"))
        image_files.extend(images_dir.glob(f"*{ext.upper()}"))

    if not image_files:
        print("⚠️ public/images 目录中没有找到图片文件")
        return []

    # 按文件名排序
    image_files.sort()
    print(f"📁 找到 {len(image_files)} 张素材图片:")
    for img in image_files:
        size_kb = img.stat().st_size / 1024
        print(f"  - {img.name} ({size_kb:.1f} KB)")

    return image_files


def get_output_dir(subdir: str = "") -> Path:
    """获取输出目录 - 使用项目的 tmp 目录"""
    project_root = Path(__file__).parent.parent
    output_dir = project_root / "tmp" / "examples"
    if subdir:
        output_dir = output_dir / subdir
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def get_result_summary(result_obj) -> str:
    """获取结果摘要，兼容不同类型的结果对象"""
    match result_obj:
        case CompressionResult():
            return result_obj.get_summary()
        case MultiFormatResult():
            successful = result_obj.get_successful_items()
            if successful:
                best = result_obj.get_best_result()
                return f"多格式: {len(successful)}/{len(result_obj.results)} 成功, 最佳: {best.format_used if best else 'N/A'}"
            return f"多格式: 0/{len(result_obj.results)} 成功"
        case BatchResult():
            return f"批量: {result_obj.get_success_count()}/{result_obj.get_total_count()} 成功"
        case _:
            return "未知结果类型"


def get_output_paths(result_obj) -> list[Path]:
    """获取输出路径列表，兼容不同类型的结果对象"""
    match result_obj:
        case CompressionResult():
            return [result_obj.output_path] if result_obj.success else []
        case MultiFormatResult():
            return [r.output_path for r in result_obj.results if r.success]
        case BatchResult():
            return [r.output_path for r in result_obj.results if r.success]
        case _:
            return []


def demo_single_file_compression():
    """单文件压缩演示"""
    print("=== 单文件压缩演示 ===")

    sample_images = get_sample_images()
    if not sample_images:
        print("❌ 没有找到素材图片，跳过演示")
        return

    # 使用最大的图片进行演示（更好的压缩效果）
    test_image = max(sample_images, key=lambda x: x.stat().st_size)
    output_dir = get_output_dir("single_file")
    print(f"📸 使用素材: {test_image.name}")
    print(f"📁 输出目录: {output_dir}")

    # 1. 智能压缩分析和演示
    print("\n🧠 智能策略分析:")
    analyze_smart_strategy(test_image)

    output_file1 = output_dir / f"{test_image.stem}_smart{test_image.suffix}"
    result1 = compress_universal(
        str(test_image),
        output=str(output_file1),  # 不指定质量，让智能策略决定
    )
    if result1["success"]:
        print(f"智能压缩: {get_result_summary(result1['result'])}")

    # 2. 指定格式和质量
    output_file2 = output_dir / f"{test_image.stem}_q70.jpg"
    result2 = compress_universal(
        str(test_image), output=str(output_file2), formats="JPEG", quality=70
    )
    if result2["success"]:
        print(f"JPEG Q70: {get_result_summary(result2['result'])}")

    # 3. 带尺寸调整
    output_file3 = output_dir / f"{test_image.stem}_resized.webp"
    result3 = compress_universal(
        str(test_image),
        output=str(output_file3),
        formats="WEBP",
        max_width=600,
        max_height=400,
    )
    if result3["success"]:
        print(f"WebP 缩放: {get_result_summary(result3['result'])}")


def demo_multi_format_compression():
    """多格式压缩演示"""
    print("\n=== 多格式压缩演示 ===")

    sample_images = get_sample_images()
    if not sample_images:
        print("❌ 没有找到素材图片，跳过演示")
        return

    # 使用第二大的图片进行演示
    sorted_images = sorted(sample_images, key=lambda x: x.stat().st_size, reverse=True)
    test_image = sorted_images[1] if len(sorted_images) > 1 else sorted_images[0]
    output_dir = get_output_dir("multi_format")

    print(f"📸 使用素材: {test_image.name}")

    # 多格式输出
    result = compress_universal(
        str(test_image),
        output=str(output_dir),
        formats=["JPEG", "WEBP", "PNG"],
        quality=80,
    )

    if result["success"]:
        multi_result: MultiFormatResult = result["result"]  # type: ignore
        print(f"处理结果: {get_result_summary(multi_result)}")

        # 显示各格式详情
        for r in multi_result.results:
            if r.success:
                print(f"  {r.output_path.name}: {r.get_summary()}")

    # 清理输出文件（不删除原始素材）
    if result["success"]:
        for output_path in get_output_paths(result["result"]):
            output_path.unlink(missing_ok=True)

    if Path("output").exists():
        shutil.rmtree("output")


def demo_batch_processing():
    """批量处理演示"""
    print("\n=== 批量处理演示 ===")

    sample_images = get_sample_images()
    if not sample_images:
        print("❌ 没有找到素材图片，跳过演示")
        return

    # 直接使用 public/images 目录进行批量处理
    images_dir = Path(__file__).parent.parent / "public" / "images"
    output_dir = get_output_dir("batch_processing")

    print(f"📁 批量处理目录: {images_dir}")

    # 批量压缩
    result = compress_universal(
        str(images_dir),
        output=str(output_dir),
        formats="JPEG",
        quality=75,
        recursive=True,
    )

    if result["success"]:
        batch_result: BatchResult = result["result"]  # type: ignore
        print(f"批量处理: {get_result_summary(batch_result)}")

        # 显示处理详情
        for r in batch_result.results:
            if r.success:
                print(
                    f"  {r.input_path.name} -> {r.output_path.name}: {r.get_summary()}"
                )


def demo_advanced_features():
    """高级功能演示"""
    print("\n=== 高级功能演示 ===")

    sample_images = get_sample_images()
    if not sample_images:
        print("❌ 没有找到素材图片，跳过演示")
        return

    # 使用 ImageCompressor 类进行更精细的控制
    compressor = ImageCompressor(max_workers=2)

    # 使用最大的图片进行演示
    test_image = max(sample_images, key=lambda x: x.stat().st_size)
    output_dir = get_output_dir("advanced")

    print(f"📸 使用素材: {test_image.name}")

    # 1. 单格式压缩
    result1 = compressor.compress_image(
        test_image,
        output_dir=str(output_dir),
        quality=85,
        format="WEBP",
        max_width=1000,
    )

    if result1.success:
        print(f"单格式压缩: {result1.get_summary()}")

    # 2. 多格式比较
    output_dir = Path("comparison")
    result2 = compressor.compress_multi_format(
        test_image, output_dir, formats=["JPEG", "WEBP", "PNG"], quality=80
    )

    if result2.success:
        print(f"多格式比较: {get_result_summary(result2)}")
        best = result2.get_best_result()
        if best:
            print(f"最佳选择: {best.format_used} (节省 {best.get_size_saved()} 字节)")

    # 清理
    if result1.success:
        result1.output_path.unlink(missing_ok=True)

    if result2.success:
        for output_path in get_output_paths(result2):
            output_path.unlink(missing_ok=True)

    if output_dir.exists():
        shutil.rmtree(output_dir)

    # 3. 展示动态格式支持
    print(f"\n📋 动态支持格式: {len(ImageFormats.get_supported_formats())} 种")

    # 4. 展示智能验证
    try:
        validated = CompressionValidators.validate_format("jpg")
        print(f"格式验证示例: 'jpg' -> '{validated}'")
    except Exception as e:
        print(f"验证错误: {e}")


def analyze_smart_strategy(image_path: Path):
    """分析智能压缩策略的决策过程"""
    try:
        # 提取图片元数据
        extractor = ImageInfoExtractor()
        metadata = extractor.extract(image_path)
        basic = metadata.basic_info

        print(
            f"  📊 图片分析: {basic.format} {basic.width}x{basic.height} ({basic.get_file_size_human()})"
        )
        print(f"  📏 总像素: {basic.get_total_pixels_human()}")
        if metadata.complexity:
            print(f"  🎯 复杂度: {metadata.complexity.overall_complexity}")

        # 获取智能策略决策
        strategy = CompressionStrategy()
        decision = strategy.select_optimal(metadata)

        print(
            f"  🤖 AI决策: {decision.strategy_type} | {decision.recommended_format} | Q{decision.recommended_quality or 'auto'}"
        )
        print(f"  💡 原因: {decision.reason}")

        # 如果是JPEG，尝试估算原始质量
        if basic.format == "JPEG":
            estimated_quality = estimate_jpeg_quality(image_path)
            if estimated_quality:
                print(f"  🔍 估算原始质量: {estimated_quality}")

    except Exception as e:
        print(f"  ❌ 策略分析失败: {e}")


def estimate_jpeg_quality(image_path: Path) -> int | None:
    """估算JPEG文件的原始质量"""
    try:
        original_size = image_path.stat().st_size
        best_quality = None
        best_diff = float("inf")

        with Image.open(image_path) as img:
            for quality in range(60, 95, 5):
                import io

                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=quality)
                test_size = buffer.tell()
                buffer.close()

                diff = abs(test_size - original_size)
                if diff < best_diff:
                    best_diff = diff
                    best_quality = quality

        return best_quality
    except Exception:
        return None


def main():
    """主函数"""
    print("🖼️  现代化图像压缩演示")
    print("=" * 50)

    try:
        demo_single_file_compression()
        demo_multi_format_compression()
        demo_batch_processing()
        demo_advanced_features()

        print("\n✅ 所有演示完成！")

    except Exception as e:
        print(f"\n❌ 演示过程中出现错误: {e}")
        raise


if __name__ == "__main__":
    main()
