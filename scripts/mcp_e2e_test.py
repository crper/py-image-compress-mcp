#!/usr/bin/env python3
"""通过官方 MCP stdio client 做端到端能力测试。"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_DIR = Path.home() / "Downloads"
SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tiff"}


@dataclass
class CapabilityCheck:
    name: str
    passed: bool
    details: str


def _list_image_candidates(source_dir: Path) -> list[Path]:
    """递归收集图片候选文件。"""
    return sorted(
        [
            path
            for path in source_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
        ],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def _pick_sample_files(source_dir: Path) -> dict[str, Path]:
    """选择真实样本文件。"""
    candidates = _list_image_candidates(source_dir)
    if len(candidates) < 5:
        raise RuntimeError(f"样本不足，{source_dir} 中仅找到 {len(candidates)} 个图片文件")

    pngs = [path for path in candidates if path.suffix.lower() == ".png"]
    tiffs = [path for path in candidates if path.suffix.lower() == ".tiff"]
    if len(pngs) < 3:
        raise RuntimeError("PNG 样本不足，无法覆盖全部能力测试")

    batch_root = _pick_batch_directory(candidates, source_dir)

    return {
        "analysis_basic": pngs[0],
        "analysis_full": pngs[1],
        "single": pngs[0],
        "multi": pngs[1],
        "batch_dir": batch_root,
        "fallback_probe": tiffs[0] if tiffs else pngs[2],
    }


def _pick_batch_directory(candidates: list[Path], source_dir: Path) -> Path:
    """选择适合做目录批处理的目录。"""
    directory_counts: dict[Path, int] = {}
    for path in candidates:
        directory_counts[path.parent] = directory_counts.get(path.parent, 0) + 1

    ranked = sorted(
        directory_counts.items(),
        key=lambda item: (item[1], item[0] == source_dir),
        reverse=True,
    )
    if not ranked:
        raise RuntimeError(f"{source_dir} 下没有可用于批量处理的图片目录")
    return ranked[0][0]


def _server_parameters() -> StdioServerParameters:
    """构建本地 stdio MCP 服务参数。"""
    return StdioServerParameters(
        command="uv",
        args=[
            "run",
            "--project",
            str(PROJECT_ROOT),
            "py-image-compress-mcp",
        ],
        cwd=PROJECT_ROOT,
    )


def _resolve_output_dir(output_dir: Path | None) -> Path:
    """解析测试输出目录。"""
    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = Path.home() / "Downloads" / f"mcp-capability-test-{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _serialize_tool_result(result: Any) -> dict[str, Any]:
    """序列化 MCP tool result。"""
    content = []
    for item in result.content:
        text = getattr(item, "text", None)
        if text is not None:
            content.append(text)
    return {
        "is_error": result.isError,
        "structured": result.structuredContent,
        "content": content,
    }


def _write_report_files(output_dir: Path, report: dict[str, Any]) -> tuple[Path, Path]:
    """写入 JSON 和 Markdown 报告。"""
    json_path = output_dir / "report.json"
    md_path = output_dir / "SUMMARY.md"

    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    checks = report["checks"]
    lines = [
        "# MCP Capability Test Report",
        "",
        f"- Time: `{report['timestamp']}`",
        f"- Source: `{report['source_dir']}`",
        f"- Output: `{report['output_dir']}`",
        "",
        "## Tools",
        "",
    ]
    for tool in report["tools"]:
        lines.append(
            f"- `{tool['name']}`: "
            f"readOnly={tool['annotations'].get('readOnlyHint')} "
            f"idempotent={tool['annotations'].get('idempotentHint')} "
            f"destructive={tool['annotations'].get('destructiveHint')}"
        )

    lines.extend(
        [
            "",
            "## Checks",
            "",
            "| Capability | Passed | Details |",
            "| --- | --- | --- |",
        ]
    )
    for check in checks:
        status = "yes" if check["passed"] else "no"
        lines.append(f"| {check['name']} | {status} | {check['details']} |")

    batch = report["results"]["batch_compress"]["structured"]["result"]
    lines.extend(
        [
            "",
            "## Batch Summary",
            "",
            f"- Total files: `{batch['total_files']}`",
            f"- Successful files: `{batch['successful_files']}`",
            f"- Failed files: `{batch['failed_files']}`",
            f"- Summary: `{batch['summary']}`",
        ]
    )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


async def run_e2e(source_dir: Path, output_dir: Path | None = None) -> dict[str, Any]:
    """运行端到端测试。"""
    samples = _pick_sample_files(source_dir)
    output_dir = _resolve_output_dir(output_dir)
    single_dir = output_dir / "single"
    multi_dir = output_dir / "multi"
    batch_dir = output_dir / "batch"
    single_dir.mkdir()
    multi_dir.mkdir()
    batch_dir.mkdir()

    checks: list[CapabilityCheck] = []

    async with stdio_client(_server_parameters()) as (
        read_stream,
        write_stream,
    ), ClientSession(read_stream, write_stream) as session:
        await session.initialize()
        tools = await session.list_tools()

        tool_payload = [
            {
                "name": tool.name,
                "description": tool.description,
                "annotations": tool.annotations.model_dump() if tool.annotations else {},
            }
            for tool in tools.tools
        ]

        tool_names = {tool["name"] for tool in tool_payload}
        checks.append(
            CapabilityCheck(
                name="tool_registration",
                passed=tool_names == {"compress_universal", "get_image_info"},
                details=", ".join(sorted(tool_names)),
            )
        )

        results: dict[str, dict[str, Any]] = {}

        basic_info = await session.call_tool(
            "get_image_info",
            {
                "input_path": str(samples["analysis_basic"]),
                "detail": "basic",
            },
        )
        results["get_image_info_basic"] = _serialize_tool_result(basic_info)
        basic_structured = results["get_image_info_basic"]["structured"]
        checks.append(
            CapabilityCheck(
                name="get_image_info_basic",
                passed=(
                    not results["get_image_info_basic"]["is_error"]
                    and "histogram" not in basic_structured
                    and "complexity" not in basic_structured
                ),
                details=f"fields={sorted(basic_structured.keys())}",
            )
        )

        full_info = await session.call_tool(
            "get_image_info",
            {
                "input_path": str(samples["analysis_full"]),
                "detail": "full",
                "include_histogram": True,
                "include_analysis": True,
            },
        )
        results["get_image_info_full"] = _serialize_tool_result(full_info)
        full_structured = results["get_image_info_full"]["structured"]
        checks.append(
            CapabilityCheck(
                name="get_image_info_full",
                passed=(
                    not results["get_image_info_full"]["is_error"]
                    and "histogram" in full_structured
                    and "complexity" in full_structured
                ),
                details=f"format={full_structured.get('format')}",
            )
        )

        single_output = single_dir / f"{samples['single'].stem}_single.webp"
        single_result = await session.call_tool(
            "compress_universal",
            {
                "input_path": str(samples["single"]),
                "output_path": str(single_output),
                "formats": "WEBP",
                "quality": 82,
            },
        )
        results["single_compress"] = _serialize_tool_result(single_result)
        single_structured = results["single_compress"]["structured"]
        checks.append(
            CapabilityCheck(
                name="single_compress",
                passed=(
                    not results["single_compress"]["is_error"]
                    and single_structured.get("success") is True
                    and single_output.exists()
                ),
                details=str(single_output),
            )
        )

        multi_result = await session.call_tool(
            "compress_universal",
            {
                "input_path": str(samples["multi"]),
                "output_path": str(multi_dir),
                "formats": ["WEBP", "JPEG", "PNG"],
                "quality": 80,
            },
        )
        results["multi_format"] = _serialize_tool_result(multi_result)
        multi_structured = results["multi_format"]["structured"]
        multi_outputs = list(multi_dir.glob("*"))
        checks.append(
            CapabilityCheck(
                name="multi_format",
                passed=(
                    not results["multi_format"]["is_error"]
                    and multi_structured.get("success") is True
                    and len(multi_outputs) >= 3
                ),
                details=f"outputs={len(multi_outputs)}",
            )
        )

        batch_result = await session.call_tool(
            "compress_universal",
            {
                "input_path": str(samples["batch_dir"]),
                "output_path": str(batch_dir),
                "formats": "WEBP",
                "quality": 80,
                "recursive": False,
            },
        )
        results["batch_compress"] = _serialize_tool_result(batch_result)
        batch_structured = results["batch_compress"]["structured"]["result"]
        batch_outputs = [path for path in batch_dir.iterdir() if path.is_file()]
        checks.append(
            CapabilityCheck(
                name="batch_compress",
                passed=(
                    not results["batch_compress"]["is_error"]
                    and results["batch_compress"]["structured"].get("success") is True
                    and batch_structured["successful_files"]
                    == batch_structured["total_files"]
                    and len(batch_outputs) == batch_structured["total_files"]
                ),
                details=(
                    f"successful={batch_structured['successful_files']}, "
                    f"total={batch_structured['total_files']}"
                ),
            )
        )

        invalid_result = await session.call_tool(
            "get_image_info",
            {"input_path": str(output_dir / "missing-file.png"), "detail": "basic"},
        )
        results["error_handling"] = _serialize_tool_result(invalid_result)
        invalid_structured = results["error_handling"]["structured"]
        checks.append(
            CapabilityCheck(
                name="error_handling",
                passed=invalid_structured.get("success") is False
                and invalid_structured.get("error_type") == "file",
                details=invalid_structured.get("error", ""),
            )
        )

    report = {
        "timestamp": datetime.now().isoformat(),
        "source_dir": str(source_dir),
        "output_dir": str(output_dir),
        "samples": {name: str(path) for name, path in samples.items()},
        "tools": tool_payload,
        "checks": [asdict(item) for item in checks],
        "results": results,
    }

    json_path, md_path = _write_report_files(output_dir, report)
    report["report_json"] = str(json_path)
    report["report_markdown"] = str(md_path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="验证 MCP 所有能力并输出测试产物")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_SOURCE_DIR,
        help="样本来源目录，默认 ~/Downloads",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="测试输出目录，默认自动创建到 ~/Downloads/mcp-capability-test-时间戳",
    )
    args = parser.parse_args()

    resolved_output_dir = args.output_dir.expanduser() if args.output_dir else None
    report = asyncio.run(run_e2e(args.source_dir.expanduser(), resolved_output_dir))
    print(
        json.dumps(
            {
                "output_dir": report["output_dir"],
                "report_json": report["report_json"],
                "report_markdown": report["report_markdown"],
                "passed": sum(1 for item in report["checks"] if item["passed"]),
                "total": len(report["checks"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
