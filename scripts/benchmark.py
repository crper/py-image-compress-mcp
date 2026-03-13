#!/usr/bin/env python3
"""项目基准脚本。"""

from __future__ import annotations

import argparse
import json
import tempfile
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path
from statistics import mean
from typing import Any

from py_image_compress_mcp.compressor import ImageCompressor
from py_image_compress_mcp.core.compression_engine import process_image
from py_image_compress_mcp.core.image_info import ImageInfoExtractor
from py_image_compress_mcp.models.compression_config import (
    CompressionConfig,
    QualityMode,
)


BASELINE_MS = {
    "extract_public_images_3_jpg": 1706.39,
    "compress_public_images_3_jpg": 1793.75,
    "batch_public_images": 2221.73,
}


def measure(
    label: str,
    action: Callable[[], Any],
    *,
    runs: int,
) -> dict[str, float]:
    """测量平均耗时与近似峰值内存。"""
    timings: list[float] = []
    peaks: list[float] = []

    for _ in range(runs):
        tracemalloc.start()
        started = time.perf_counter()
        action()
        elapsed_ms = (time.perf_counter() - started) * 1000
        _, peak_bytes = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        timings.append(elapsed_ms)
        peaks.append(peak_bytes / (1024 * 1024))

    average_ms = mean(timings)
    baseline = BASELINE_MS.get(label)
    improvement = None
    if baseline:
        improvement = ((baseline - average_ms) / baseline) * 100

    return {
        "avg_ms": round(average_ms, 2),
        "min_ms": round(min(timings), 2),
        "max_ms": round(max(timings), 2),
        "peak_memory_mb": round(max(peaks), 2),
        "improvement_vs_baseline_pct": round(improvement, 2)
        if improvement is not None
        else 0.0,
    }


def find_default_extra_image() -> Path | None:
    """尝试从下载目录找到一张真实 PNG 样本。"""
    candidates = sorted(
        Path.home().glob("Downloads/**/*.png"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def build_report(runs: int, extra_image: Path | None) -> dict[str, Any]:
    """执行基准并构建报告。"""
    project_root = Path(__file__).resolve().parent.parent
    repo_image = project_root / "public" / "images" / "3.jpg"
    batch_dir = project_root / "public" / "images"

    extractor = ImageInfoExtractor()
    compressor = ImageCompressor()

    with tempfile.TemporaryDirectory() as temp_dir_str:
        temp_dir = Path(temp_dir_str)

        def benchmark_extract() -> None:
            extractor.extract(repo_image)

        def benchmark_compress() -> None:
            output_dir = temp_dir / "single"
            config = CompressionConfig(
                input_path=repo_image,
                output_dir=output_dir,
                quality_mode=QualityMode.CUSTOM,
                custom_quality=80,
                target_format="JPEG",
            )
            result = process_image(config)
            result.output_path.unlink(missing_ok=True)

        def benchmark_batch() -> None:
            result = compressor.compress_universal(
                batch_dir,
                output=temp_dir / "batch",
                quality=80,
                recursive=False,
            )
            batch_output = temp_dir / "batch"
            if batch_output.exists():
                for file_path in batch_output.rglob("*"):
                    if file_path.is_file():
                        file_path.unlink()

            if not result["success"]:
                raise RuntimeError(result["error"] or "批量压缩失败")

        report: dict[str, Any] = {
            "runs": runs,
            "benchmarks": {
                "extract_public_images_3_jpg": measure(
                    "extract_public_images_3_jpg",
                    benchmark_extract,
                    runs=runs,
                ),
                "compress_public_images_3_jpg": measure(
                    "compress_public_images_3_jpg",
                    benchmark_compress,
                    runs=runs,
                ),
                "batch_public_images": measure(
                    "batch_public_images",
                    benchmark_batch,
                    runs=runs,
                ),
            },
        }

        if extra_image:
            extra_path = extra_image.expanduser().resolve()

            def benchmark_extra_png() -> None:
                extractor.extract(extra_path)
                compressor.compress_image(
                    input_path=extra_path,
                    output_dir=temp_dir / "extra",
                    quality=80,
                    format="WEBP",
                )

            report["extra_image"] = str(extra_path)
            report["benchmarks"]["extract_and_compress_extra_png"] = measure(
                "extract_and_compress_extra_png",
                benchmark_extra_png,
                runs=max(1, min(3, runs)),
            )

    return report


def render_markdown(report: dict[str, Any]) -> str:
    """输出 Markdown 表格，方便直接贴进文档。"""
    lines = [
        "| Benchmark | Avg (ms) | Min (ms) | Max (ms) | Peak Memory (MB) | vs Baseline |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, metrics in report["benchmarks"].items():
        lines.append(
            "| "
            f"{name} | {metrics['avg_ms']} | {metrics['min_ms']} | {metrics['max_ms']} | "
            f"{metrics['peak_memory_mb']} | {metrics['improvement_vs_baseline_pct']}% |"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="运行项目性能基准")
    parser.add_argument("--runs", type=int, default=5, help="每个基准执行次数")
    parser.add_argument("--image", type=Path, default=None, help="额外测试图片路径")
    parser.add_argument(
        "--json-output",
        type=Path,
        default=Path("tmp/benchmark_results.json"),
        help="JSON 结果输出路径",
    )
    args = parser.parse_args()

    extra_image = args.image or find_default_extra_image()
    report = build_report(args.runs, extra_image)
    markdown = render_markdown(report)

    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(markdown)
    print()
    print(f"JSON saved to: {args.json_output}")
    if extra_image:
        print(f"Extra image: {extra_image}")


if __name__ == "__main__":
    main()
