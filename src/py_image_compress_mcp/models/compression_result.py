"""压缩结果模型。

定义图片压缩操作的结果数据结构。
"""

from pathlib import Path
from typing import Any, TypedDict

from humanize import naturalsize
from pydantic import BaseModel, Field


class BaseResult(BaseModel):
    """结果基类，包含通用字段和方法"""

    success: bool = Field(description="是否成功")
    error: str | None = Field(None, description="错误信息")

    def is_successful(self) -> bool:
        """检查是否成功"""
        return self.success and self.error is None

    @staticmethod
    def format_size(size_bytes: int) -> str:
        """格式化文件大小为人类可读格式"""
        return naturalsize(size_bytes, binary=True)


class ResultCollection(BaseResult):
    """结果集合基类，提供通用的统计方法"""

    results: list[Any] = Field(description="结果列表")

    def get_successful_items(self) -> list[Any]:
        """获取成功的结果项"""
        return [r for r in self.results if getattr(r, "success", False)]

    def get_failed_items(self) -> list[Any]:
        """获取失败的结果项"""
        return [r for r in self.results if not getattr(r, "success", False)]

    def get_total_count(self) -> int:
        """获取总数量"""
        return len(self.results)

    def get_success_count(self) -> int:
        """获取成功数量"""
        return len(self.get_successful_items())

    def get_failure_count(self) -> int:
        """获取失败数量"""
        return len(self.get_failed_items())

    def get_success_rate(self) -> float:
        """获取成功率（百分比）"""
        total = self.get_total_count()
        if total == 0:
            return 0.0
        return (self.get_success_count() / total) * 100


class CompressionResult(BaseResult):
    """单个图片压缩结果"""

    input_path: Path = Field(description="输入文件路径")
    output_path: Path = Field(description="输出文件路径")
    original_size: int = Field(description="原始文件大小（字节）")
    compressed_size: int = Field(description="压缩后文件大小（字节）")

    # 压缩参数
    format_used: str = Field(description="使用的格式")
    quality_used: int | None = Field(None, description="使用的质量值")

    # 处理信息
    was_resized: bool = Field(False, description="是否调整了尺寸")
    original_dimensions: tuple[int, int] | None = Field(None, description="原始尺寸")
    final_dimensions: tuple[int, int] | None = Field(None, description="最终尺寸")

    def get_size_saved(self) -> int:
        """节省的字节数"""
        return max(0, self.original_size - self.compressed_size)

    def get_compression_ratio(self) -> float:
        """压缩比例（百分比）"""
        if self.original_size == 0:
            return 0.0
        size_saved = self.get_size_saved()
        return (size_saved / self.original_size) * 100

    def get_original_size_human(self) -> str:
        """人类可读的原始文件大小"""
        return self.format_size(self.original_size)

    def get_compressed_size_human(self) -> str:
        """人类可读的压缩后文件大小"""
        return self.format_size(self.compressed_size)

    def get_summary(self) -> str:
        """压缩结果摘要"""
        if not self.success:
            return f"失败: {self.error}"

        return (
            f"{self.get_original_size_human()} → {self.get_compressed_size_human()} "
            f"({self.get_compression_ratio():.1f}% 压缩)"
        )


class MultiFormatResult(ResultCollection):
    """多格式压缩结果"""

    input_path: Path = Field(description="输入文件路径")
    results: list[CompressionResult] = Field(description="各格式压缩结果")

    def get_best_result(self) -> CompressionResult | None:
        """最佳压缩结果（节省最多）"""
        successful = self.get_successful_items()
        if not successful:
            return None
        return max(successful, key=lambda r: r.get_size_saved())


class BatchResult(ResultCollection):
    """批量处理结果"""

    input_dir: Path = Field(description="输入目录")
    output_dir: Path | None = Field(None, description="输出目录")
    results: list[CompressionResult] = Field(description="所有文件的处理结果")

    def get_total_original_size(self) -> int:
        """总原始大小"""
        return sum(r.original_size for r in self.results)

    def get_total_compressed_size(self) -> int:
        """总压缩后大小"""
        return sum(r.compressed_size for r in self.results if r.success)

    def get_total_size_saved(self) -> int:
        """总节省大小"""
        return sum(r.get_size_saved() for r in self.results if r.success)

    def get_overall_compression_ratio(self) -> float:
        """整体压缩比例"""
        total_original = self.get_total_original_size()
        if total_original == 0:
            return 0.0
        return (self.get_total_size_saved() / total_original) * 100

    def get_summary(self) -> str:
        """批量处理摘要"""
        if not self.success:
            return f"批量处理失败: {self.error}"

        total = self.get_total_count()
        successful = self.get_success_count()
        success_rate = self.get_success_rate()
        size_saved = self.format_size(self.get_total_size_saved())

        return (
            f"处理 {successful}/{total} 个文件 "
            f"(成功率 {success_rate:.1f}%), "
            f"总节省 {size_saved}"
        )


# ============================================================================
# 类型定义 - 统一的输入输出类型
# ============================================================================


class ProcessingResult(TypedDict):
    """统一的处理结果类型定义

    用于所有压缩操作的返回值，提供一致的接口。
    """

    success: bool
    result: BatchResult | CompressionResult | MultiFormatResult
    error: str | None


class ImageInfoResponse(TypedDict):
    """图像信息响应类型定义"""

    success: bool
    metadata: dict[str, Any] | None
    error: str | None
