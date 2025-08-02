"""智能压缩策略模块。

基于图片特征的自适应压缩决策系统。
"""

from ..config import get_config
from ..models.compression_config import (
    CompressionConfig,
    CompressionDecision,
    QualityMode,
    StrategyType,
)
from ..models.image_metadata import ImageMetadata
from ..utils.logging_helpers import get_logger
from .image_info import analyze_image_from_metadata


logger = get_logger()
config = get_config()


class CompressionStrategy:
    """智能压缩策略选择器"""

    def __init__(
        self,
        prefer_quality: bool | None = None,
        size_threshold_mb: float | None = None,
        complexity_threshold: float | None = None,
    ):
        """初始化策略选择器

        Args:
            prefer_quality: 是否优先考虑质量（None时使用配置默认值）
            size_threshold_mb: 文件大小阈值（MB），超过此值倾向于有损压缩
            complexity_threshold: 复杂度阈值，超过此值倾向于有损压缩
        """
        self.prefer_quality = (
            prefer_quality
            if prefer_quality is not None
            else config.processing.PREFER_QUALITY
        )
        self.size_threshold_mb = (
            size_threshold_mb
            if size_threshold_mb is not None
            else config.compression.SIZE_THRESHOLD_MB
        )
        self.complexity_threshold = (
            complexity_threshold
            if complexity_threshold is not None
            else config.compression.COMPLEXITY_THRESHOLD
        )

    def select_optimal(
        self, metadata: ImageMetadata, config: CompressionConfig | None = None
    ) -> CompressionDecision:
        """选择最优压缩策略

        Args:
            metadata: 图片元数据
            config: 用户配置（可选）

        Returns:
            CompressionDecision: 压缩决策结果
        """
        # 如果用户明确指定了策略，优先使用
        if config and config.quality_mode != QualityMode.LOSSLESS:
            return self._apply_user_config(config, metadata)

        # 基于图片特征进行智能决策
        return self._analyze_and_decide(metadata)

    def _apply_user_config(
        self, config: CompressionConfig, metadata: ImageMetadata
    ) -> CompressionDecision:
        """应用用户配置"""
        quality = config.effective_quality
        format_hint = self._suggest_format(metadata, config.target_format)

        strategy_type = StrategyType.LOSSLESS if quality is None else StrategyType.LOSSY

        return CompressionDecision(
            strategy_type=strategy_type,
            recommended_quality=quality,
            recommended_format=format_hint,
            reason="用户指定配置",
        )

    def _analyze_and_decide(self, metadata: ImageMetadata) -> CompressionDecision:
        """基于图片特征分析并决策 - 优先保守策略避免负优化"""
        basic = metadata.basic_info
        complexity = metadata.complexity

        # 计算文件大小（MB）
        file_size_mb = basic.file_size / (1024 * 1024)

        # 首先检查是否应该跳过压缩（避免负优化）
        if self._should_skip_compression(metadata):
            return CompressionDecision(
                strategy_type=StrategyType.SKIP,
                recommended_format=basic.format,
                recommended_quality=None,
                skip_compression=True,
                reason="文件已经高度优化，跳过压缩避免负优化",
            )

        # 优先尝试原格式优化（类似 TinyPNG 的策略）
        original_format_decision = self._try_original_format_optimization(metadata)
        if original_format_decision:
            return original_format_decision

        # 决策因子
        factors: dict[str, bool] = {
            "large_file": file_size_mb > self.size_threshold_mb,
            "high_complexity": bool(
                complexity and complexity.overall_complexity == "complex"
            ),
            "has_transparency": basic.has_transparency,
            "is_photo": self._is_photo_like(metadata),
            "is_simple_graphic": self._is_simple_graphic(metadata),
        }

        # 决策逻辑
        decision = self._make_decision(factors, metadata)

        logger.debug(f"压缩决策: {decision.strategy_type}, 原因: {decision.reason}")
        return decision

    def _make_decision(
        self, factors: dict[str, bool], metadata: ImageMetadata
    ) -> CompressionDecision:
        """基于因子做出决策，使用 match-case 简化逻辑"""

        # 跳过压缩的情况
        if self._should_skip_compression(metadata):
            return CompressionDecision(
                strategy_type=StrategyType.SKIP,
                recommended_quality=None,
                recommended_format=None,
                skip_compression=True,
                reason="文件已经很小或已经高度压缩",
            )

        # 构建决策上下文元组
        context = (
            factors["has_transparency"],
            factors["is_simple_graphic"],
            factors["is_photo"],
            factors["large_file"],
            factors["high_complexity"],
        )

        match context:
            # 透明图片处理
            case (True, _, _, True, _):  # 大文件透明图片
                return CompressionDecision(
                    strategy_type=StrategyType.LOSSY,
                    recommended_format="WEBP",
                    recommended_quality=90,
                    reason="大文件透明图片，使用WebP有损压缩平衡质量和大小",
                )
            case (True, _, _, False, _):  # 小文件透明图片
                return CompressionDecision(
                    strategy_type=StrategyType.LOSSLESS,
                    recommended_format="PNG",
                    recommended_quality=None,
                    reason="透明图片，使用PNG无损压缩保持质量",
                )

            # 简单图形处理
            case (False, True, _, _, _):  # 简单图形
                return self._handle_simple_graphic(metadata)

            # 照片类图片处理
            case (False, False, True, True, _) | (
                False,
                False,
                True,
                _,
                True,
            ):  # 大文件或复杂照片
                quality = config.compression.JPEG_QUALITY if self.prefer_quality else 75
                return CompressionDecision(
                    strategy_type=StrategyType.LOSSY,
                    recommended_quality=quality,
                    recommended_format="JPEG",
                    reason="照片类图片，文件大或复杂，使用JPEG有损压缩",
                )
            case (False, False, True, False, False):  # 小文件简单照片
                return CompressionDecision(
                    strategy_type=StrategyType.LOSSLESS,
                    recommended_format="WEBP",
                    recommended_quality=None,
                    reason="小尺寸照片，尝试WebP无损压缩",
                )

            # 默认策略
            case (False, False, False, True, _):  # 大文件其他类型
                return CompressionDecision(
                    strategy_type=StrategyType.LOSSY,
                    recommended_quality=config.compression.WEBP_QUALITY,
                    recommended_format="WEBP",
                    reason="大文件，使用WebP有损压缩平衡质量和大小",
                )
            case _:  # 其他情况
                return CompressionDecision(
                    strategy_type=StrategyType.LOSSLESS,
                    recommended_format="WEBP",
                    recommended_quality=None,
                    reason="中小文件，使用WebP无损压缩",
                )

    def _handle_simple_graphic(self, metadata: ImageMetadata) -> CompressionDecision:
        """处理简单图形的压缩决策"""
        basic = metadata.basic_info
        color_count = self._estimate_color_count(metadata)
        file_size_mb = basic.file_size / (1024 * 1024)

        # 对于已经是JPEG的图片，优先考虑保持JPEG格式
        if basic.format == "JPEG" and file_size_mb > 0.1:  # 大于100KB
            return CompressionDecision(
                strategy_type=StrategyType.LOSSY,
                recommended_format="JPEG",
                recommended_quality=75,
                reason="JPEG图片使用适中质量压缩，保持格式一致性",
            )

        # 对于非常小的简单图形，且颜色很少，才考虑PNG无损
        if color_count <= 64 and file_size_mb < 0.05:  # 小于50KB且颜色很少
            return CompressionDecision(
                strategy_type=StrategyType.LOSSLESS,
                recommended_format="PNG",
                recommended_quality=None,
                reason="极简单小图形，PNG无损压缩效果最佳",
            )

        # 其他情况使用WebP适中质量压缩
        return CompressionDecision(
            strategy_type=StrategyType.LOSSY,
            recommended_format="WEBP",
            recommended_quality=80,
            reason="简单图形，使用WebP适中质量压缩",
        )

    def _should_skip_compression(self, metadata: ImageMetadata) -> bool:
        """判断是否应该跳过压缩 - 更保守的策略避免负优化"""
        basic = metadata.basic_info

        # 文件很小（小于5KB）- 小文件压缩收益有限且容易变大
        if basic.file_size < 5 * 1024:
            return True

        # 已经是高度压缩的格式且文件较小，直接跳过
        if basic.format in ("WEBP", "JPEG") and basic.file_size < 50 * 1024:
            return True

        # PNG小文件（<100KB）且可能是简单图形，保守处理
        if basic.format == "PNG" and basic.file_size < 100 * 1024:
            # 检查是否为简单图形（基于尺寸和文件大小比例）
            pixel_count = basic.width * basic.height
            bytes_per_pixel = basic.file_size / pixel_count if pixel_count > 0 else 0
            # 如果每像素字节数很小，可能是简单图形，跳过压缩
            if bytes_per_pixel < 1.5:  # 简单图形通常每像素占用很少字节
                return True

        return False

    def _try_original_format_optimization(
        self, metadata: ImageMetadata
    ) -> CompressionDecision | None:
        """尝试在原格式基础上优化，类似 TinyPNG 的策略"""
        basic = metadata.basic_info
        file_size_mb = basic.file_size / (1024 * 1024)

        # 对于 JPEG 图片，使用智能质量检测和优化
        if basic.format == "JPEG":
            # 对于JPEG，最安全的策略是使用optimize参数进行无损优化
            # 这类似于TinyPNG的做法：保持质量，优化编码
            return CompressionDecision(
                strategy_type=StrategyType.LOSSLESS,  # 使用optimize是无损的
                recommended_format="JPEG",
                recommended_quality=None,  # 不指定质量，让优化器处理
                reason="JPEG 无损优化，使用 optimize 参数减小文件大小",
            )

        # 对于 PNG 图片，更保守的处理策略
        if basic.format == "PNG":
            # 小PNG文件（<200KB）优先保持PNG格式
            if file_size_mb < 0.2:
                return CompressionDecision(
                    strategy_type=StrategyType.LOSSLESS,
                    recommended_format="PNG",
                    recommended_quality=None,
                    reason="PNG 小文件无损优化，保持原格式",
                )
            # 大PNG文件才考虑格式转换，但仍然优先PNG优化
            return CompressionDecision(
                strategy_type=StrategyType.LOSSLESS,
                recommended_format="PNG",
                recommended_quality=None,
                reason="PNG 无损优化，使用最佳压缩参数",
            )

        # 对于 WebP 图片，保持原格式
        if basic.format == "WEBP":
            if file_size_mb < 0.2:  # 小文件保持无损
                return CompressionDecision(
                    strategy_type=StrategyType.LOSSLESS,
                    recommended_format="WEBP",
                    recommended_quality=None,
                    reason="WebP 小文件无损优化",
                )
            # 大文件使用高质量有损
            return CompressionDecision(
                strategy_type=StrategyType.LOSSY,
                recommended_format="WEBP",
                recommended_quality=85,
                reason="WebP 高质量压缩",
            )

        # 其他格式返回 None，使用通用策略
        return None

    def _estimate_color_count(self, metadata: ImageMetadata) -> int:
        """估算图像的颜色数量"""
        try:
            # 基于图像复杂度和尺寸估算颜色数量
            basic = metadata.basic_info
            complexity = metadata.complexity

            # 基础估算：基于像素数量
            pixel_count = basic.width * basic.height

            if complexity and complexity.overall_complexity in ("very_low", "simple"):
                # 极简单/简单图像：颜色数量较少
                # 对于大图片也要合理限制颜色数量估算
                return min(256, max(16, pixel_count // 1000))
            if complexity and complexity.overall_complexity == "complex":
                # 复杂图像：颜色数量较多
                return min(65536, pixel_count // 10)
            # 中等复杂度
            return min(4096, pixel_count // 100)

        except Exception:
            # 默认估算
            return 1024

    def _is_photo_like(self, metadata: ImageMetadata) -> bool:
        """判断是否为照片类图片"""
        characteristics = analyze_image_from_metadata(metadata)
        return characteristics.is_photo_like

    def _is_simple_graphic(self, metadata: ImageMetadata) -> bool:
        """判断是否为简单图形"""
        characteristics = analyze_image_from_metadata(metadata)
        return characteristics.is_simple_graphic

    def _suggest_format(
        self, metadata: ImageMetadata, user_preference: str | None = None
    ) -> str:
        """建议输出格式，内联格式选择逻辑避免循环导入"""

        # 如果用户指定了格式，优先使用
        if user_preference:
            return user_preference.upper()

        characteristics = analyze_image_from_metadata(metadata)
        has_transparency = metadata.basic_info.has_transparency

        # 使用 match-case 简化格式选择逻辑
        context = (
            has_transparency,
            characteristics.is_photo_like,
            characteristics.is_simple_graphic,
            self.prefer_quality,
        )

        match context:
            case (True, _, _, _):  # 有透明度
                return "WEBP" if self.prefer_quality else "PNG"
            case (False, True, _, True):  # 照片且偏好质量
                return "WEBP"
            case (False, True, _, False):  # 照片且偏好大小
                return "JPEG"
            case (False, False, True, _):  # 简单图形
                return "PNG"
            case _:  # 默认情况
                return "WEBP"
