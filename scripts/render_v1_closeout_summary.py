#!/usr/bin/env python3
"""Render V1 closeout JSON report into a markdown summary."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


def _sanitize_cell(value: Any) -> str:
    return str(value or "").replace("\n", " ").replace("|", "\\|").strip()


def build_summary_markdown(title: str, payload: dict[str, Any] | None, report_path: Path) -> str:
    lines: list[str] = [f"## {title}", ""]
    if payload is None:
        lines.append(f"- report missing: `{report_path}`")
        lines.append("")
        return "\n".join(lines)

    lines.append(f"- branch: `{_sanitize_cell(payload.get('branch'))}`")
    lines.append(f"- commit: `{_sanitize_cell(payload.get('commit'))}`")
    lines.append(f"- profile: `{_sanitize_cell(payload.get('profile'))}`")
    lines.append(f"- timestamp_utc: `{_sanitize_cell(payload.get('timestamp_utc'))}`")
    lines.append("")
    lines.append("| Step | Status | Notes |")
    lines.append("|---|---|---|")
    for step in payload.get("steps", []) or []:
        row = step if isinstance(step, dict) else {}
        lines.append(
            f"| {_sanitize_cell(row.get('step'))} | {_sanitize_cell(row.get('status'))} | {_sanitize_cell(row.get('notes'))} |"
        )
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render closeout JSON report to markdown summary.")
    parser.add_argument(
        "--report-json",
        default="/tmp/v1_closeout_last_run.json",
        help="Path to closeout JSON report (default: /tmp/v1_closeout_last_run.json)",
    )
    parser.add_argument(
        "--title",
        default="V1 Closeout Report",
        help="Markdown heading title (default: V1 Closeout Report)",
    )
    parser.add_argument(
        "--summary-path",
        default="",
        help="Optional markdown output path; defaults to GITHUB_STEP_SUMMARY when set.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report_path = Path(args.report_json)

    payload: dict[str, Any] | None = None
    if report_path.exists():
        payload = json.loads(report_path.read_text(encoding="utf-8"))

    markdown = build_summary_markdown(args.title, payload, report_path)

    output_path = args.summary_path.strip() or os.getenv("GITHUB_STEP_SUMMARY", "").strip()
    if output_path:
        summary_path = Path(output_path)
        with summary_path.open("a", encoding="utf-8") as f:
            f.write(markdown)
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
