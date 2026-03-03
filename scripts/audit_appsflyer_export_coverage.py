#!/usr/bin/env python3
"""Audit AppsFlyer export field coverage for Cat-Scan attribution readiness.

This script is phase-A tooling: it validates whether real AppsFlyer exports
contain the fields needed for exact (`clickid`) and fallback joins.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_FIELD_MAP: dict[str, list[str]] = {
    "click_id": ["clickid", "af_click_id", "click_id"],
    "creative_id": ["creative_id", "af_sub2", "af_ad_id", "af_ad"],
    "buyer_hint": ["buyer_id", "af_sub1"],
    "campaign_id": ["campaign_id", "campaign", "c", "af_c_id"],
    "site_id": ["af_siteid", "site_id"],
    "event_ts": ["event_time", "install_time", "eventTime", "timestamp"],
}


@dataclass
class CoverageStats:
    rows: int = 0
    click_id_present: int = 0
    creative_id_present: int = 0
    buyer_hint_present: int = 0
    exact_ready_rows: int = 0
    fallback_ready_rows: int = 0
    timestamp_present: int = 0
    site_id_present: int = 0
    campaign_id_present: int = 0


def _coalesce(row: dict[str, str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        value = row.get(candidate)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return None


def _normalize_row_keys(row: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in row.items():
        if key is None:
            continue
        normalized[str(key).strip()] = value
        normalized[str(key).strip().lower()] = value
    return normalized


def _read_csv_rows(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(handle, dialect=dialect)
        for row in reader:
            if row:
                yield {str(k): ("" if v is None else str(v)) for k, v in row.items() if k is not None}


def _read_jsonl_rows(path: Path) -> Iterable[dict[str, str]]:
    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                out: dict[str, str] = {}
                for key, value in payload.items():
                    if value is None:
                        out[str(key)] = ""
                    elif isinstance(value, (str, int, float, bool)):
                        out[str(key)] = str(value)
                    else:
                        out[str(key)] = json.dumps(value, separators=(",", ":"), sort_keys=True)
                yield out


def _read_rows(path: Path, input_format: str) -> Iterable[dict[str, str]]:
    if input_format == "jsonl":
        return _read_jsonl_rows(path)
    if input_format == "csv":
        return _read_csv_rows(path)
    # auto detect by extension
    if path.suffix.lower() in {".jsonl", ".ndjson"}:
        return _read_jsonl_rows(path)
    return _read_csv_rows(path)


def _load_field_map(path: Path | None) -> dict[str, list[str]]:
    if path is None:
        return dict(DEFAULT_FIELD_MAP)
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("field_map"), dict):
        data = data["field_map"]
    if not isinstance(data, dict):
        raise ValueError("mapping profile must be object or {'field_map': object}")

    normalized: dict[str, list[str]] = {}
    for canonical, candidates in data.items():
        if isinstance(candidates, str):
            values = [candidates]
        elif isinstance(candidates, list):
            values = [str(item) for item in candidates if item]
        else:
            continue
        cleaned: list[str] = []
        for value in values:
            name = value.strip()
            if not name:
                continue
            cleaned.append(name)
            cleaned.append(name.lower())
        if cleaned:
            # preserve order while deduping
            deduped = list(dict.fromkeys(cleaned))
            normalized[str(canonical)] = deduped

    merged = dict(DEFAULT_FIELD_MAP)
    merged.update(normalized)
    return merged


def _pct(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return (part / total) * 100.0


def _decision(exact_ready_pct: float) -> tuple[str, str]:
    if exact_ready_pct >= 80.0:
        return "exact_ready", "Exact attribution join is viable for this dataset."
    if exact_ready_pct >= 40.0:
        return (
            "mixed_mode",
            "Mixed mode recommended: exact join where possible, fallback join with confidence scoring.",
        )
    return (
        "fallback_only",
        "Exact join is not yet viable; prioritize clickid propagation before strict optimizer automation.",
    )


def _stats_payload(stats: CoverageStats) -> dict[str, float | int]:
    return {
        "rows": stats.rows,
        "click_id_present": stats.click_id_present,
        "creative_id_present": stats.creative_id_present,
        "buyer_hint_present": stats.buyer_hint_present,
        "timestamp_present": stats.timestamp_present,
        "site_id_present": stats.site_id_present,
        "campaign_id_present": stats.campaign_id_present,
        "exact_ready_rows": stats.exact_ready_rows,
        "fallback_ready_rows": stats.fallback_ready_rows,
        "click_id_present_pct": round(_pct(stats.click_id_present, stats.rows), 4),
        "creative_id_present_pct": round(_pct(stats.creative_id_present, stats.rows), 4),
        "buyer_hint_present_pct": round(_pct(stats.buyer_hint_present, stats.rows), 4),
        "timestamp_present_pct": round(_pct(stats.timestamp_present, stats.rows), 4),
        "site_id_present_pct": round(_pct(stats.site_id_present, stats.rows), 4),
        "campaign_id_present_pct": round(_pct(stats.campaign_id_present, stats.rows), 4),
        "exact_ready_pct": round(_pct(stats.exact_ready_rows, stats.rows), 4),
        "fallback_ready_pct": round(_pct(stats.fallback_ready_rows, stats.rows), 4),
    }


def _summary_payload(
    *,
    stats_by_file: dict[str, CoverageStats],
    combined: CoverageStats,
    mapping_path: Path | None,
    field_map: dict[str, list[str]],
) -> dict[str, object]:
    exact_pct = _pct(combined.exact_ready_rows, combined.rows)
    decision_code, decision_message = _decision(exact_pct)
    return {
        "files_scanned": len(stats_by_file),
        "mapping_profile": str(mapping_path) if mapping_path else None,
        "field_map": field_map,
        "combined": _stats_payload(combined),
        "per_file": {name: _stats_payload(stats) for name, stats in stats_by_file.items()},
        "decision": {
            "mode": decision_code,
            "message": decision_message,
        },
    }


def _audit_rows(rows: Iterable[dict[str, str]], field_map: dict[str, list[str]]) -> CoverageStats:
    stats = CoverageStats()
    for row in rows:
        stats.rows += 1
        normalized = _normalize_row_keys(row)

        click_id = _coalesce(normalized, field_map["click_id"])
        creative_id = _coalesce(normalized, field_map["creative_id"])
        buyer_hint = _coalesce(normalized, field_map["buyer_hint"])
        timestamp = _coalesce(normalized, field_map["event_ts"])
        site_id = _coalesce(normalized, field_map["site_id"])
        campaign_id = _coalesce(normalized, field_map["campaign_id"])

        if click_id:
            stats.click_id_present += 1
        if creative_id:
            stats.creative_id_present += 1
        if buyer_hint:
            stats.buyer_hint_present += 1
        if timestamp:
            stats.timestamp_present += 1
        if site_id:
            stats.site_id_present += 1
        if campaign_id:
            stats.campaign_id_present += 1

        if click_id and timestamp:
            stats.exact_ready_rows += 1
        if creative_id and timestamp:
            stats.fallback_ready_rows += 1
    return stats


def _render_markdown(
    *,
    stats_by_file: dict[str, CoverageStats],
    combined: CoverageStats,
    mapping_path: Path | None,
    field_map: dict[str, list[str]],
) -> str:
    lines: list[str] = []
    lines.append("# AppsFlyer Export Coverage Audit")
    lines.append("")
    lines.append(f"- files_scanned: {len(stats_by_file)}")
    lines.append(f"- mapping_profile: `{mapping_path}`" if mapping_path else "- mapping_profile: `builtin default`")
    lines.append("")
    lines.append("## Field Map")
    lines.append("")
    for canonical, candidates in field_map.items():
        lines.append(f"- `{canonical}` <= {', '.join(f'`{c}`' for c in candidates)}")
    lines.append("")
    lines.append("## Per-file Summary")
    lines.append("")
    lines.append(
        "| file | rows | click_id % | creative_id % | buyer_hint % | timestamp % | exact_ready % | fallback_ready % |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for file_name, stats in stats_by_file.items():
        lines.append(
            f"| {file_name} | {stats.rows} | "
            f"{_pct(stats.click_id_present, stats.rows):.1f} | "
            f"{_pct(stats.creative_id_present, stats.rows):.1f} | "
            f"{_pct(stats.buyer_hint_present, stats.rows):.1f} | "
            f"{_pct(stats.timestamp_present, stats.rows):.1f} | "
            f"{_pct(stats.exact_ready_rows, stats.rows):.1f} | "
            f"{_pct(stats.fallback_ready_rows, stats.rows):.1f} |"
        )
    lines.append("")
    lines.append("## Combined Summary")
    lines.append("")
    lines.append(f"- total_rows: `{combined.rows}`")
    lines.append(f"- click_id_present: `{combined.click_id_present}` ({_pct(combined.click_id_present, combined.rows):.1f}%)")
    lines.append(f"- creative_id_present: `{combined.creative_id_present}` ({_pct(combined.creative_id_present, combined.rows):.1f}%)")
    lines.append(f"- buyer_hint_present: `{combined.buyer_hint_present}` ({_pct(combined.buyer_hint_present, combined.rows):.1f}%)")
    lines.append(f"- timestamp_present: `{combined.timestamp_present}` ({_pct(combined.timestamp_present, combined.rows):.1f}%)")
    lines.append(f"- exact_ready_rows (click_id + timestamp): `{combined.exact_ready_rows}` ({_pct(combined.exact_ready_rows, combined.rows):.1f}%)")
    lines.append(f"- fallback_ready_rows (creative_id + timestamp): `{combined.fallback_ready_rows}` ({_pct(combined.fallback_ready_rows, combined.rows):.1f}%)")
    lines.append("")
    lines.append("## Decision Hint")
    lines.append("")
    _, decision_message = _decision(_pct(combined.exact_ready_rows, combined.rows))
    lines.append(f"- {decision_message}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit AppsFlyer export field coverage")
    parser.add_argument("--input", action="append", required=True, help="Input CSV/JSONL file (repeatable)")
    parser.add_argument("--input-format", choices=["auto", "csv", "jsonl"], default="auto")
    parser.add_argument("--mapping-profile", help="Optional JSON mapping profile file")
    parser.add_argument("--out", help="Optional markdown output path")
    parser.add_argument("--json-out", help="Optional JSON summary output path")
    args = parser.parse_args()

    mapping_path = Path(args.mapping_profile).expanduser().resolve() if args.mapping_profile else None
    field_map = _load_field_map(mapping_path)

    stats_by_file: dict[str, CoverageStats] = {}
    combined = CoverageStats()

    for raw_path in args.input:
        file_path = Path(raw_path).expanduser().resolve()
        file_rows = _read_rows(file_path, args.input_format)
        file_stats = _audit_rows(file_rows, field_map)
        stats_by_file[str(file_path)] = file_stats

        combined.rows += file_stats.rows
        combined.click_id_present += file_stats.click_id_present
        combined.creative_id_present += file_stats.creative_id_present
        combined.buyer_hint_present += file_stats.buyer_hint_present
        combined.exact_ready_rows += file_stats.exact_ready_rows
        combined.fallback_ready_rows += file_stats.fallback_ready_rows
        combined.timestamp_present += file_stats.timestamp_present
        combined.site_id_present += file_stats.site_id_present
        combined.campaign_id_present += file_stats.campaign_id_present

    output = _render_markdown(
        stats_by_file=stats_by_file,
        combined=combined,
        mapping_path=mapping_path,
        field_map=field_map,
    )
    summary = _summary_payload(
        stats_by_file=stats_by_file,
        combined=combined,
        mapping_path=mapping_path,
        field_map=field_map,
    )
    print(output, end="")

    if args.out:
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"Wrote report: {out_path}")
    if args.json_out:
        json_path = Path(args.json_out).expanduser().resolve()
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote summary JSON: {json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
