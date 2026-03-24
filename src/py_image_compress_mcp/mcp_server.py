"""现代化图像压缩 MCP 服务器。

利用 Pillow 11 现代 API 和简化的数据模型。
"""

import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .compressor import ImageCompressor
from .core.image_info import ImageInfoExtractor
from .models import BatchResult, CompressionResult, ImageMetadata, MultiFormatResult
from .utils.message_formatter import MessageFormatter


# MCP 服务器响应类型定义
MCPCompressionResponse = dict[str, Any]
MCPImageInfoResponse = dict[str, Any]


@dataclass(frozen=True)
class ServerServices:
    """MCP 服务器依赖容器。"""

    compressor: ImageCompressor
    image_info_extractor: ImageInfoExtractor
    lightweight_image_info_extractor: ImageInfoExtractor
    summary_image_info_extractor: ImageInfoExtractor


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


logger = logging.getLogger(__name__)

def build_services() -> ServerServices:
    """构建 MCP 服务器使用的服务对象。"""
    return ServerServices(
        compressor=ImageCompressor(),
        image_info_extractor=ImageInfoExtractor(),
        lightweight_image_info_extractor=ImageInfoExtractor(
            include_exif=False,
            include_icc=False,
            include_xmp=False,
            include_histogram=False,
            include_complexity=False,
        ),
        summary_image_info_extractor=ImageInfoExtractor(
            include_histogram=False,
            include_xmp=False,
        ),
    )


@lru_cache(maxsize=1)
def get_default_services() -> ServerServices:
    """获取默认的服务对象集合。"""
    return build_services()


def _create_base_server() -> FastMCP[Any]:
    """创建基础 MCP 应用实例。"""
    return FastMCP(
        name="py-image-compress",
        instructions=(
            "Compress local images and inspect image metadata. "
            "Use compress_universal for file or directory workflows. "
            "Use get_image_info when you need dimensions, transparency, EXIF, ICC, "
            "or complexity details."
        ),
        dependencies=["pillow", "numpy", "humanize", "defusedxml"],
    )


# 默认 MCP 应用实例。
mcp: FastMCP[Any] = _create_base_server()


# ============================================================================
# 🎯 核心工具 - 只提供两个统一接口，让用户无感知底层复杂性
# ============================================================================


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        idempotentHint=False,
        destructiveHint=False,
        openWorldHint=False,
    ),
    structured_output=True,
)
def compress_universal(
    input_path: str,
    output_path: str | None = None,
    formats: list[str] | str | None = None,
    quality: int | None = None,
    max_width: int | None = None,
    max_height: int | None = None,
    recursive: bool = True,
) -> MCPCompressionResponse:
    """压缩图片或批量处理目录。

    支持单文件压缩、单文件多格式输出、格式转换和目录批量压缩。
    返回统一的结构化结果，包含输出路径、压缩比例、节省空间和错误信息。
    """
    try:
        input_path_obj = Path(input_path)
        if not input_path_obj.exists():
            return MCPResponseBuilder.file_error(
                MessageFormatter.file_not_found(input_path)
            )

        output_path_obj = Path(output_path) if output_path else None

        # 使用通用压缩器
        result = get_default_services().compressor.compress_universal(
            input_path=input_path_obj,
            output=output_path_obj,
            formats=formats,
            quality=quality,
            max_width=max_width,
            max_height=max_height,
            recursive=recursive,
        )
        formatted_result = _format_universal_result(result["result"])
        error_message = result.get("error") or _extract_result_error(result["result"])

        return {
            "success": result["success"],
            "result": formatted_result,
            "error": error_message,
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
    if isinstance(result, CompressionResult):
        return _format_compression_result(result)
    if isinstance(result, BatchResult):
        return _format_batch_result(result)
    if isinstance(result, MultiFormatResult):
        return _format_multi_format_result(result)

    # 未知结果类型，返回基本信息
    return {
        "type": "unknown",
        "result": str(result),
    }


def _extract_result_error(
    result: BatchResult | CompressionResult | MultiFormatResult | Any,
) -> str | None:
    """从领域结果对象提取统一错误信息。"""
    if isinstance(result, BatchResult | CompressionResult | MultiFormatResult):
        return result.error
    return None


def _format_compression_result(result: CompressionResult) -> dict[str, Any]:
    """格式化单文件压缩结果。"""
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
        "skipped": result.skipped,
        "note": result.note,
        "error": result.error,
    }


def _format_batch_result(result: BatchResult) -> dict[str, Any]:
    """格式化批量压缩结果。"""
    return {
        "type": "batch",
        "input_dir": str(result.input_dir),
        "output_dir": str(result.output_dir),
        "success": result.success,
        "error": result.error,
        "total_files": result.get_total_count(),
        "successful_files": result.get_success_count(),
        "failed_files": result.get_failure_count(),
        "success_rate": result.get_success_rate(),
        "total_size_saved": result.get_total_size_saved(),
        "summary": result.get_summary(),
        "results": [_format_collection_item(item) for item in result.results],
    }


def _format_multi_format_result(result: MultiFormatResult) -> dict[str, Any]:
    """格式化多格式压缩结果。"""
    return {
        "type": "multi_format",
        "input_path": str(result.input_path),
        "success": result.success,
        "error": result.error,
        "total_formats": len(result.results),
        "successful_formats": sum(1 for item in result.results if item.success),
        "results": [
            {
                "format": item.format_used,
                "summary": item.get_summary() if item.success else None,
                **_format_collection_item(item),
            }
            for item in result.results
        ],
    }


def _format_collection_item(result: CompressionResult) -> dict[str, Any]:
    """格式化集合中的压缩结果项。"""
    return {
        "input_path": str(result.input_path),
        "output_path": str(result.output_path),
        "success": result.success,
        "skipped": result.skipped,
        "note": result.note,
        "format_used": result.format_used,
        "compression_ratio": result.get_compression_ratio() if result.success else 0,
        "size_saved": result.get_size_saved() if result.success else 0,
        "error": result.error,
    }


# ============================================================================
# 图片信息获取工具
# ============================================================================


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        idempotentHint=True,
        destructiveHint=False,
        openWorldHint=False,
    ),
    structured_output=True,
)
def get_image_info(
    input_path: str,
    detail: str = "summary",
    include_histogram: bool | None = None,
    include_analysis: bool | None = None,
) -> MCPImageInfoResponse:
    """读取图片元数据和分析信息。

    `basic` 返回基础尺寸与透明度信息。
    `summary` 额外返回 EXIF、ICC 和复杂度信息。
    `full` 再额外返回完整直方图数据。
    """
    try:
        # 直接使用 Path 进行路径处理
        input_path_obj = Path(input_path)
        if not input_path_obj.exists():
            return MCPResponseBuilder.file_error(
                MessageFormatter.file_not_found(input_path)
            )

        normalized_detail = detail.strip().lower()
        if normalized_detail not in {"basic", "summary", "full"}:
            return MCPResponseBuilder.validation_error(
                'detail 必须是 "basic"、"summary" 或 "full"', "detail"
            )

        extractor = _resolve_extractor(
            normalized_detail,
            include_histogram=include_histogram,
            include_analysis=include_analysis,
        )

        # 提取元数据
        metadata = extractor.extract(input_path_obj)
        return _format_image_info_response(metadata)

    except (ValueError, FileNotFoundError) as e:
        logger.error(MessageFormatter.operation_failed("路径处理", input_path, e))
        return MCPResponseBuilder.file_error(
            MessageFormatter.validation_error("路径", input_path, str(e))
        )
    except Exception as e:
        logger.error(MessageFormatter.operation_failed("获取图片信息", input_path, e))
        return MCPResponseBuilder.processing_error(str(e), "图片信息获取")


def _resolve_extractor(
    detail: str,
    *,
    include_histogram: bool | None,
    include_analysis: bool | None,
) -> ImageInfoExtractor:
    """根据请求粒度选择图片信息提取器。"""
    services = get_default_services()

    if include_histogram is None and include_analysis is None:
        if detail == "basic":
            return services.lightweight_image_info_extractor
        if detail == "summary":
            return services.summary_image_info_extractor
        return services.image_info_extractor

    return _build_extractor(
        detail=detail,
        include_histogram=include_histogram,
        include_analysis=include_analysis,
    )


@lru_cache(maxsize=12)
def _build_extractor(
    *,
    detail: str,
    include_histogram: bool | None,
    include_analysis: bool | None,
) -> ImageInfoExtractor:
    """缓存自定义图片信息提取器。"""
    return ImageInfoExtractor(
        include_exif=detail != "basic",
        include_icc=detail != "basic",
        include_xmp=detail == "full",
        include_histogram=include_histogram
        if include_histogram is not None
        else detail == "full",
        include_complexity=include_analysis
        if include_analysis is not None
        else detail != "basic",
    )


def _format_image_info_response(metadata: ImageMetadata) -> MCPImageInfoResponse:
    """格式化图片信息响应。"""
    basic = metadata.basic_info
    result: MCPImageInfoResponse = {
        "success": True,
        "file_path": str(basic.file_path),
        "file_size": basic.file_size,
        "file_size_human": metadata.get_file_size_human(),
        "format": basic.format,
        "mode": basic.mode,
        "width": basic.width,
        "height": basic.height,
        "aspect_ratio": basic.aspect_ratio,
        "total_pixels": basic.total_pixels,
        "orientation": basic.orientation,
        "has_transparency": basic.has_transparency,
        "is_animated": basic.is_animated,
        "frame_count": basic.frame_count,
    }

    if metadata.exif_data:
        exif = metadata.exif_data
        result["exif"] = {
            "camera_make": exif.camera_make,
            "camera_model": exif.camera_model,
            "lens_model": exif.lens_model,
            "datetime_original": exif.datetime_original.isoformat()
            if exif.datetime_original
            else None,
            "datetime_digitized": exif.datetime_digitized.isoformat()
            if exif.datetime_digitized
            else None,
            "gps_latitude": exif.gps_latitude,
            "gps_longitude": exif.gps_longitude,
            "iso": exif.iso,
            "aperture": exif.aperture,
            "shutter_speed": exif.shutter_speed,
            "focal_length": exif.focal_length,
            "flash": exif.flash,
            "white_balance": exif.white_balance,
            "exposure_mode": exif.exposure_mode,
            "metering_mode": exif.metering_mode,
        }

    if metadata.icc_profile:
        icc_profile = metadata.icc_profile
        result["icc_profile"] = {
            "profile_description": icc_profile.profile_description,
            "color_space": icc_profile.color_space,
            "profile_size": icc_profile.profile_size,
        }

    if metadata.histogram:
        histogram = metadata.histogram
        result["histogram"] = {
            "red_histogram": histogram.red_histogram,
            "green_histogram": histogram.green_histogram,
            "blue_histogram": histogram.blue_histogram,
            "luminance_histogram": histogram.luminance_histogram,
            "brightness_stats": histogram.brightness_stats,
        }

    if metadata.complexity:
        complexity = metadata.complexity
        result["complexity"] = {
            "edge_density": complexity.edge_density,
            "color_diversity": complexity.color_diversity,
            "texture_complexity": complexity.texture_complexity,
            "compression_difficulty": complexity.compression_difficulty,
            "overall_complexity": complexity.overall_complexity,
        }

    return result


# ============================================================================
# 应用入口
# ============================================================================


def main() -> None:
    """启动 MCP 服务器"""
    logging.basicConfig(level=logging.INFO)
    logger.info("启动图片压缩 MCP 服务器")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
