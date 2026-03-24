"""MCP 服务器功能演示

展示简化后的 MCP 服务器核心功能：
- 🎯 compress_universal: 通用压缩工具（处理所有场景）
- 📊 get_image_info: 图片信息分析工具

让用户无感知底层复杂性，一个工具处理所有压缩需求。
"""

from pathlib import Path
from typing import Any

from py_image_compress_mcp import ImageCompressor
from py_image_compress_mcp.core.image_info import ImageInfoExtractor


def safe_get_attr(obj: Any, attr: str, default: Any = "N/A") -> Any:
    """安全地获取对象属性"""
    return getattr(obj, attr, default)


def safe_call_method(obj: Any, method: str, default: Any = "N/A") -> Any:
    """安全地调用对象方法"""
    try:
        method_func = getattr(obj, method, None)
        if method_func and callable(method_func):
            return method_func()
        return default
    except Exception:
        return default


def format_result_info(result_data: Any) -> str:
    """格式化结果信息"""
    summary = safe_call_method(result_data, "get_summary", "无摘要信息")
    format_used = safe_get_attr(result_data, "format_used", "未知格式")
    compression_ratio = safe_call_method(result_data, "get_compression_ratio", 0)

    return f"格式: {format_used}, 摘要: {summary}, 压缩比: {compression_ratio:.1f}%"


def get_sample_images() -> list[Path]:
    """获取 public/images 中的素材图片"""
    project_root = Path(__file__).parent.parent
    images_dir = project_root / "public" / "images"

    if not images_dir.exists():
        print("⚠️ public/images 目录不存在")
        return []

    # 收集所有图片文件
    image_files = []
    for ext in [".jpg", ".jpeg", ".png", ".webp"]:
        image_files.extend(images_dir.glob(f"*{ext}"))
        image_files.extend(images_dir.glob(f"*{ext.upper()}"))

    if not image_files:
        print("⚠️ public/images 目录中没有找到图片文件")
        return []

    image_files.sort()
    return image_files


def get_output_dir() -> Path:
    """获取输出目录 - 使用项目的 tmp 目录"""
    project_root = Path(__file__).parent.parent
    output_dir = project_root / "tmp" / "mcp_demo"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _display_metadata_info(metadata):
    """显示图片元数据信息"""
    print("\n✅ 图片信息获取成功:")
    print(f"  格式: {metadata.basic_info.format}")
    print(f"  尺寸: {metadata.basic_info.width}x{metadata.basic_info.height}")
    print(f"  文件大小: {metadata.get_file_size_human()}")
    print(f"  透明度: {'是' if metadata.basic_info.has_transparency else '否'}")
    print(f"  总像素: {metadata.basic_info.get_total_pixels_human()}")

    # 显示 EXIF 时间信息（如果有）
    if metadata.exif_data:
        exif = metadata.exif_data
        print("\n📅 EXIF 时间信息:")
        if exif.datetime_original:
            print(f"  拍摄时间: {exif.datetime_original}")
            human_time = exif.get_datetime_original_human()
            if human_time:
                print(f"  拍摄时间（人性化）: {human_time}")
        if exif.datetime_digitized:
            print(f"  数字化时间: {exif.datetime_digitized}")
            human_digitized = exif.get_datetime_digitized_human()
            if human_digitized:
                print(f"  数字化时间（人性化）: {human_digitized}")

    # 显示 ICC 配置文件信息（如果有）
    if metadata.icc_profile and metadata.icc_profile.creation_date:
        icc = metadata.icc_profile
        print("\n🎨 ICC 配置文件:")
        print(f"  创建时间: {icc.creation_date}")
        human_creation = icc.get_creation_date_human()
        if human_creation:
            print(f"  创建时间（人性化）: {human_creation}")

    # 显示复杂度信息（如果有）
    if metadata.complexity:
        complexity = metadata.complexity
        print("\n📈 复杂度分析:")
        print(f"  边缘密度: {complexity.edge_density:.3f}")
        print(f"  颜色多样性: {complexity.color_diversity:.3f}")
        print(f"  纹理复杂度: {complexity.texture_complexity:.3f}")
        print(f"  整体复杂度: {complexity.overall_complexity}")

    # 显示直方图信息（如果有）
    if metadata.histogram:
        histogram = metadata.histogram
        print("\n📊 颜色直方图:")
        print(f"  红色通道: {len(histogram.red_histogram)} 个值")
        print(f"  绿色通道: {len(histogram.green_histogram)} 个值")
        print(f"  蓝色通道: {len(histogram.blue_histogram)} 个值")
        print(f"  亮度通道: {len(histogram.luminance_histogram)} 个值")


def demo_image_info_tool():
    """演示 get_image_info MCP 工具（模拟MCP调用）"""
    print("📊 get_image_info 工具演示")
    print("=" * 40)

    sample_images = get_sample_images()
    if not sample_images:
        print("❌ 没有找到素材图片，跳过演示")
        return

    # 使用第一张图片
    test_image = sample_images[0]
    print(f"📸 分析图片: {test_image.name}")

    # 使用底层的图片信息提取器（模拟MCP工具调用）
    try:
        extractor = ImageInfoExtractor()
        metadata = extractor.extract(test_image)
        _display_metadata_info(metadata)

    except Exception as e:
        print(f"❌ 图片信息获取失败: {e}")
        import traceback

        traceback.print_exc()


def demo_compress_universal_tool():
    """演示 compress_universal MCP 工具（模拟MCP调用）"""
    print("\n🎯 compress_universal 工具演示")
    print("=" * 40)

    sample_images = get_sample_images()
    if not sample_images:
        print("❌ 没有找到素材图片，跳过演示")
        return

    # 使用最大的图片进行演示（更好的压缩效果）
    test_image = max(sample_images, key=lambda x: x.stat().st_size)
    output_dir = get_output_dir()
    print(f"📸 处理图片: {test_image.name}")

    # 创建压缩器实例
    compressor = ImageCompressor()
    single_output_path = output_dir / f"{test_image.stem}_single{test_image.suffix}"

    # 1. 单文件智能压缩
    print("\n1. 单文件智能压缩:")
    try:
        result = compressor.compress_universal(
            input_path=test_image,
            output=single_output_path,
            quality=None,  # 无损压缩
        )

        if result["success"]:
            result_data = result["result"]
            print(f"  ✅ 压缩成功: {format_result_info(result_data)}")
        else:
            print(f"  ❌ 压缩失败: {result.get('error', '未知错误')}")
    except Exception as e:
        print(f"  💥 异常: {e}")

    # 2. 多格式输出
    print("\n2. 多格式输出:")
    try:
        multi_result = compressor.compress_universal(
            input_path=test_image,
            output=output_dir,
            formats=["JPEG", "PNG", "WEBP"],
            quality=80,
        )

        if multi_result["success"]:
            result_data = multi_result["result"]
            print("  ✅ 多格式压缩成功")

            # 安全地获取结果列表
            results = safe_get_attr(result_data, "results", [])
            if results:
                print(f"  总格式: {len(results)}")
                success_count = sum(
                    1 for r in results if safe_get_attr(r, "success", False)
                )
                print(f"  成功格式: {success_count}")
                for fmt_result in results:
                    status = (
                        "✅" if safe_get_attr(fmt_result, "success", False) else "❌"
                    )
                    format_name = safe_get_attr(fmt_result, "format_used", "未知")
                    summary = safe_call_method(
                        fmt_result,
                        "get_summary",
                        safe_get_attr(fmt_result, "error", "无信息"),
                    )
                    print(f"    {status} {format_name}: {summary}")
            else:
                print(f"  单格式结果: {format_result_info(result_data)}")
        else:
            print(f"  ❌ 多格式压缩失败: {multi_result.get('error', '未知错误')}")
    except Exception as e:
        print(f"  💥 异常: {e}")

    # 3. 特定格式转换
    print("\n3. 特定格式转换:")
    try:
        convert_result = compressor.compress_universal(
            input_path=test_image,
            output=output_dir / f"{test_image.stem}_converted.jpg",
            formats="JPEG",
            quality=75,
        )

        if convert_result["success"]:
            result_data = convert_result["result"]
            print(f"  ✅ 格式转换成功: {format_result_info(result_data)}")
        else:
            print(f"  ❌ 格式转换失败: {convert_result.get('error', '未知错误')}")
    except Exception as e:
        print(f"  💥 异常: {e}")


def demo_batch_processing():
    """演示目录批量处理（模拟MCP调用）"""
    print("\n📁 目录批量处理演示")
    print("=" * 40)

    # 直接使用 public/images 目录进行批量处理
    images_dir = Path(__file__).parent.parent / "public" / "images"

    if not images_dir.exists():
        print("❌ public/images 目录不存在，跳过演示")
        return

    output_dir = get_output_dir()
    print(f"📁 批量处理目录: {images_dir}")

    # 创建压缩器实例
    compressor = ImageCompressor()

    # 使用 compress_universal 工具进行批量处理
    try:
        batch_result = compressor.compress_universal(
            input_path=images_dir,
            output=output_dir / "batch_output",
            formats="JPEG",
            quality=70,
            recursive=True,
        )

        if batch_result["success"]:
            result_data = batch_result["result"]
            print("  ✅ 批量处理成功")

            # 尝试获取批量结果信息
            total_count = safe_call_method(result_data, "get_total_count", 0)
            if total_count > 0:
                # 批量结果
                success_count = safe_call_method(result_data, "get_success_count", 0)
                success_rate = safe_call_method(result_data, "get_success_rate", 0)
                total_saved = safe_call_method(result_data, "get_total_size_saved", 0)

                print(f"  总文件: {total_count}")
                print(f"  成功文件: {success_count}")
                print(f"  成功率: {success_rate:.1f}%")
                if total_saved > 0:
                    print(f"  节省空间: {total_saved:,} bytes")

                # 显示前几个处理结果
                results = safe_get_attr(result_data, "results", [])
                if results:
                    print("  处理结果预览:")
                    for r in results[:3]:
                        status = "✅" if safe_get_attr(r, "success", False) else "❌"
                        input_path = safe_get_attr(r, "input_path", "未知文件")
                        input_name = getattr(input_path, "name", str(input_path))

                        if safe_get_attr(r, "success", False):
                            ratio = safe_call_method(r, "get_compression_ratio", 0)
                            print(f"    {status} {input_name}: {ratio:.1f}% 压缩")
                        else:
                            error = safe_get_attr(r, "error", "未知错误")
                            print(f"    {status} {input_name}: {error}")

                    if len(results) > 3:
                        print(f"    ... 还有 {len(results) - 3} 个文件")
            else:
                # 单文件结果
                print(f"  单文件结果: {format_result_info(result_data)}")
        else:
            print(f"  ❌ 批量处理失败: {batch_result.get('error', '未知错误')}")
    except Exception as e:
        print(f"  💥 异常: {e}")


def demo_mcp_response_format():
    """演示 MCP 工具的响应格式（模拟MCP调用）"""
    print("\n📡 MCP 工具响应格式演示")
    print("=" * 40)

    sample_images = get_sample_images()
    if not sample_images:
        print("❌ 没有找到素材图片，跳过演示")
        return

    # 使用第一张图片进行演示
    test_image = sample_images[0]
    output_dir = get_output_dir()
    print(f"📸 处理图片: {test_image.name}")

    # 创建压缩器实例
    compressor = ImageCompressor()

    # 演示 compress_universal 工具的响应格式
    try:
        result = compressor.compress_universal(
            input_path=test_image,
            output=output_dir / f"{test_image.stem}_demo.webp",
            formats="WEBP",
            quality=85,
        )

        print("\n🎯 compress_universal 工具响应格式:")
        print(f"  success: {result['success']}")
        if result["success"]:
            result_data = result["result"]
            # 安全地访问属性，适配不同的结果类型
            format_used = getattr(result_data, "format_used", "N/A")
            quality_used = getattr(result_data, "quality_used", "N/A")
            print(f"  result.format_used: {format_used}")
            print(f"  result.quality_used: {quality_used}")

            # 使用安全的方法获取结果信息
            summary = safe_call_method(
                result_data, "get_summary", f"类型: {type(result_data).__name__}"
            )
            print(f"  result.summary: {summary}")

            ratio = safe_call_method(result_data, "get_compression_ratio", 0)
            if ratio > 0:
                print(f"  result.compression_ratio: {ratio:.1f}%")

            saved = safe_call_method(result_data, "get_size_saved", 0)
            if saved > 0:
                print(f"  result.size_saved: {saved} bytes")
        else:
            print(f"  error: {result.get('error', '未知错误')}")

    except Exception as e:
        print(f"  💥 异常: {e}")


def main():
    """主函数"""
    print("🚀 简化后的 MCP 图片压缩服务演示")
    print("=" * 50)
    print("🎯 核心工具:")
    print("  1. compress_universal - 通用压缩工具（处理所有场景）")
    print("  2. get_image_info - 图片信息分析工具")
    print("=" * 50)

    try:
        demo_image_info_tool()
        demo_compress_universal_tool()
        demo_batch_processing()
        demo_mcp_response_format()

        print("\n" + "=" * 50)
        print("✅ MCP 演示完成！")
        print("🎉 简化后的 MCP 服务器只需要两个工具就能处理所有场景")
        print("🎯 AI助手可以直接调用，无需创建额外脚本")

    except Exception as e:
        print(f"\n❌ 演示过程中出现错误: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
