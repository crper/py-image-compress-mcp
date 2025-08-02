"""现代化图像压缩 MCP 服务器。

利用 Pillow 11 现代 API 和简化的数据模型。
"""

import logging
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from .compressor import ImageCompressor
from .core.image_info import ImageInfoExtractor
from .utils.message_formatter import MessageFormatter


# MCP 服务器响应类型定义
MCPCompressionResponse = dict[str, Any]
MCPImageInfoResponse = dict[str, Any]


class MCPResponseBuilder:
    """MCP 服务器响应构建器，专门用于构建符合 MCP 协议的响应格式。"""

    @staticmethod
    def error(
        message: str,
        error_type: str = "general",
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """构建错误结果。

        Args:
            message: 错误消息
            error_type: 错误类型
            details: 额外的错误详情

        Returns:
            dict: 标准化的错误响应
        """
        result = {
            "success": False,
            "error": message,
            "error_type": error_type,
        }

        if details:
            result["details"] = details

        return result

    @staticmethod
    def validation_error(message: str, field: str | None = None) -> dict[str, Any]:
        """构建验证错误结果。

        Args:
            message: 错误消息
            field: 相关字段名

        Returns:
            dict: 验证错误响应
        """
        details = {"field": field} if field else None
        return MCPResponseBuilder.error(
            message=message,
            error_type="validation",
            details=details,
        )

    @staticmethod
    def file_error(message: str, file_path: str | None = None) -> dict[str, Any]:
        """构建文件相关错误结果。

        Args:
            message: 错误消息
            file_path: 相关文件路径

        Returns:
            dict: 文件错误响应
        """
        details = {"file_path": file_path} if file_path else None
        return MCPResponseBuilder.error(
            message=message,
            error_type="file",
            details=details,
        )

    @staticmethod
    def processing_error(message: str, operation: str | None = None) -> dict[str, Any]:
        """构建处理错误结果。

        Args:
            message: 错误消息
            operation: 相关操作名称

        Returns:
            dict: 处理错误响应
        """
        details = {"operation": operation} if operation else None
        return MCPResponseBuilder.error(
            message=message,
            error_type="processing",
            details=details,
        )


# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建MCP应用
mcp: FastMCP[Any] = FastMCP("现代化图像压缩服务")

# 全局压缩器实例
compressor = ImageCompressor(max_workers=4)

# 全局图片信息提取器实例
image_info_extractor = ImageInfoExtractor()


# ============================================================================
# 🎯 核心工具 - 只提供两个统一接口，让用户无感知底层复杂性
# ============================================================================


@mcp.tool()
def compress_universal(
    input_path: str,
    output_path: str | None = None,
    formats: list[str] | str | None = None,
    quality: int | None = None,
    max_width: int | None = None,
    max_height: int | None = None,
    recursive: bool = True,
) -> MCPCompressionResponse:
    """🎯 通用图像压缩工具 - 处理所有压缩场景的统一接口

    智能检测输入类型（单文件/多文件/目录）并自动选择最优处理策略。
    支持单格式、多格式输出，批量处理，让用户无感知底层复杂性。

    Args:
        input_path: 输入路径（支持单个文件或目录）
        output_path: 输出路径（可选，默认智能生成）
        formats: 输出格式，支持：
            - None: 智能选择最优格式
            - 字符串: 单格式如 "WEBP"
            - 列表: 多格式如 ["JPEG", "PNG", "WEBP"]
        quality: 压缩质量 1-100（None 为无损压缩）
        max_width: 最大宽度限制（像素）
        max_height: 最大高度限制（像素）
        recursive: 目录处理时是否递归子目录

    Returns:
        dict: 统一的压缩结果，自动适配不同场景的返回格式

    使用场景:
        # 📁 单文件压缩（智能优化）
        compress_universal("photo.jpg")

        # 📁 单文件多格式输出
        compress_universal("photo.jpg", formats=["JPEG", "PNG", "WEBP"], quality=80)

        # 📂 目录批量压缩
        compress_universal("photos/", output_path="output/", quality=60)

        # 🔄 格式转换
        compress_universal("image.webp", output_path="image.jpg", formats="JPEG", quality=70)

        # 📐 尺寸限制批量处理
        compress_universal("images/", max_width=1920, max_height=1080, recursive=True)
    """
    try:
        input_path_obj = Path(input_path)
        if not input_path_obj.exists():
            return MCPResponseBuilder.file_error(
                MessageFormatter.file_not_found(input_path)
            )

        output_path_obj = Path(output_path) if output_path else None

        # 使用通用压缩器
        result = compressor.compress_universal(
            input_path=input_path_obj,
            output=output_path_obj,
            formats=formats,
            quality=quality,
            max_width=max_width,
            max_height=max_height,
            recursive=recursive,
        )

        return {
            "success": result["success"],
            "result": _format_universal_result(result["result"]),
            "error": result.get("error"),
        }

    except (ValueError, FileNotFoundError) as e:
        logger.error(MessageFormatter.operation_failed("路径处理", input_path, e))
        return MCPResponseBuilder.file_error(
            MessageFormatter.validation_error("路径", input_path, str(e))
        )
    except Exception as e:
        logger.error(MessageFormatter.operation_failed("通用压缩", input_path, e))
        return MCPResponseBuilder.processing_error(
            MessageFormatter.operation_failed("通用压缩", input_path, e), "通用压缩"
        )


def _format_universal_result(result: Any) -> dict[str, Any]:
    """格式化通用压缩结果为MCP响应格式"""
    # 检查结果类型并相应格式化
    if hasattr(result, "get_summary"):
        # 单文件结果 (CompressionResult)
        return {
            "type": "single_file",
            "input_path": str(result.input_path),
            "output_path": str(result.output_path),
            "original_size": result.original_size,
            "compressed_size": result.compressed_size,
            "format_used": result.format_used,
            "quality_used": result.quality_used,
            "compression_ratio": result.get_compression_ratio(),
            "size_saved": result.get_size_saved(),
            "summary": result.get_summary(),
            "success": result.success,
            "error": result.error,
        }
    if hasattr(result, "results") and hasattr(result, "input_dir"):
        # 批量结果 (BatchResult)
        return {
            "type": "batch",
            "input_dir": str(result.input_dir),
            "output_dir": str(result.output_dir),
            "total_files": result.get_total_count(),
            "successful_files": result.get_success_count(),
            "failed_files": result.get_failure_count(),
            "success_rate": result.get_success_rate(),
            "total_size_saved": result.get_total_size_saved(),
            "summary": result.get_summary(),
            "results": [
                {
                    "input_path": str(r.input_path),
                    "output_path": str(r.output_path),
                    "success": r.success,
                    "format_used": r.format_used,
                    "compression_ratio": r.get_compression_ratio() if r.success else 0,
                    "size_saved": r.get_size_saved() if r.success else 0,
                    "error": r.error,
                }
                for r in result.results
            ],
        }
    if hasattr(result, "results") and hasattr(result, "input_path"):
        # 多格式结果 (MultiFormatResult)
        return {
            "type": "multi_format",
            "input_path": str(result.input_path),
            "total_formats": len(result.results),
            "successful_formats": sum(1 for r in result.results if r.success),
            "results": [
                {
                    "format": r.format_used,
                    "output_path": str(r.output_path),
                    "success": r.success,
                    "compression_ratio": r.get_compression_ratio() if r.success else 0,
                    "size_saved": r.get_size_saved() if r.success else 0,
                    "summary": r.get_summary() if r.success else None,
                    "error": r.error,
                }
                for r in result.results
            ],
        }
    # 未知结果类型，返回基本信息
    return {
        "type": "unknown",
        "result": str(result),
    }


# ============================================================================
# 图片信息获取工具
# ============================================================================


@mcp.tool()
def get_image_info(
    input_path: str,
) -> MCPImageInfoResponse:
    """获取图片的详细信息和元数据。

    提取图片的基础信息、EXIF数据、ICC配置文件等详细元数据。
    所有分析功能默认启用，包括颜色直方图和复杂度分析。

    Args:
        input_path: 输入图像文件路径

    Returns:
        dict: 图片信息，包含基础信息、EXIF、ICC配置文件、直方图、复杂度分析等
    """
    try:
        # 直接使用 Path 进行路径处理
        input_path_obj = Path(input_path)
        if not input_path_obj.exists():
            return MCPResponseBuilder.file_error(
                MessageFormatter.file_not_found(input_path)
            )

        # 创建提取器实例（所有分析功能默认启用）
        extractor = ImageInfoExtractor()

        # 提取元数据
        metadata = extractor.extract(input_path_obj)

        # 构建返回数据
        result = {
            "success": True,
            "file_path": str(metadata.basic_info.file_path),
            "file_size": metadata.basic_info.file_size,
            "file_size_human": metadata.get_file_size_human(),
            "format": metadata.basic_info.format,
            "mode": metadata.basic_info.mode,
            "width": metadata.basic_info.width,
            "height": metadata.basic_info.height,
            "aspect_ratio": metadata.basic_info.aspect_ratio,
            "total_pixels": metadata.basic_info.total_pixels,
            "orientation": metadata.basic_info.orientation,
            "has_transparency": metadata.basic_info.has_transparency,
            "is_animated": metadata.basic_info.is_animated,
            "frame_count": metadata.basic_info.frame_count,
        }

        # 添加EXIF数据（如果存在）
        if metadata.exif_data:
            result["exif"] = {
                "camera_make": metadata.exif_data.camera_make,
                "camera_model": metadata.exif_data.camera_model,
                "lens_model": metadata.exif_data.lens_model,
                "datetime_original": metadata.exif_data.datetime_original.isoformat()
                if metadata.exif_data.datetime_original
                else None,
                "datetime_digitized": metadata.exif_data.datetime_digitized.isoformat()
                if metadata.exif_data.datetime_digitized
                else None,
                "gps_latitude": metadata.exif_data.gps_latitude,
                "gps_longitude": metadata.exif_data.gps_longitude,
                "iso": metadata.exif_data.iso,  # 修正字段名
                "aperture": metadata.exif_data.aperture,
                "shutter_speed": metadata.exif_data.shutter_speed,
                "focal_length": metadata.exif_data.focal_length,
                "flash": metadata.exif_data.flash,
                "white_balance": metadata.exif_data.white_balance,
                "exposure_mode": metadata.exif_data.exposure_mode,
                "metering_mode": metadata.exif_data.metering_mode,  # 修正字段名
            }

        # 添加ICC配置文件信息（如果存在）
        if metadata.icc_profile:
            result["icc_profile"] = {
                "profile_description": metadata.icc_profile.profile_description,
                "color_space": metadata.icc_profile.color_space,
                "profile_size": metadata.icc_profile.profile_size,
            }

        # 添加直方图数据（如果启用）
        if metadata.histogram:
            result["histogram"] = {
                "red_histogram": metadata.histogram.red_histogram,
                "green_histogram": metadata.histogram.green_histogram,
                "blue_histogram": metadata.histogram.blue_histogram,
                "luminance_histogram": metadata.histogram.luminance_histogram,
                "brightness_stats": metadata.histogram.brightness_stats,
            }

        # 添加复杂度分析（如果启用）
        if metadata.complexity:
            result["complexity"] = {
                "edge_density": metadata.complexity.edge_density,
                "color_diversity": metadata.complexity.color_diversity,
                "texture_complexity": metadata.complexity.texture_complexity,
                "compression_difficulty": metadata.complexity.compression_difficulty,
                "overall_complexity": metadata.complexity.overall_complexity,
            }

        return result

    except (ValueError, FileNotFoundError) as e:
        logger.error(MessageFormatter.operation_failed("路径处理", input_path, e))
        return MCPResponseBuilder.file_error(
            MessageFormatter.validation_error("路径", input_path, str(e))
        )
    except Exception as e:
        logger.error(MessageFormatter.operation_failed("获取图片信息", input_path, e))
        return MCPResponseBuilder.processing_error(str(e), "图片信息获取")


# ============================================================================
# 应用入口
# ============================================================================


def main() -> None:
    """启动 MCP 服务器"""
    logger.info("启动图片压缩 MCP 服务器")
    mcp.run()


if __name__ == "__main__":
    main()
