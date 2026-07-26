#!/usr/bin/env python3
"""Repeatedly compare read-only CatScan HTTP contracts across two deployments.

The report deliberately stores hashes, status, latency, response size, schema
signatures and changed JSON paths instead of response bodies or buyer IDs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_VERSION = "catscan-api-read-only-soak.v1"
EXPECTED_TARGET_SHADOW_HEADER = "read-only"
_STOP_REQUESTED = False


@dataclass(frozen=True)
class Contract:
    name: str
    path: str
    params: tuple[tuple[str, Any], ...] = ()
    buyer_scoped: bool = False


CONTRACTS = (
    Contract("health", "/health"),
    Contract("stats", "/stats"),
    Contract("sizes", "/sizes"),
    Contract("seats", "/seats"),
    Contract(
        "spend_90d",
        "/analytics/spend-stats",
        (("days", 90),),
        buyer_scoped=True,
    ),
    Contract(
        "rtb_funnel_90d",
        "/analytics/rtb-funnel",
        (("days", 90),),
        buyer_scoped=True,
    ),
    Contract(
        "publishers_90d_limit_100",
        "/analytics/rtb-funnel/publishers",
        (("days", 90), ("limit", 100)),
        buyer_scoped=True,
    ),
    Contract(
        "geos_90d_limit_100",
        "/analytics/rtb-funnel/geos",
        (("days", 90), ("limit", 100)),
        buyer_scoped=True,
    ),
    Contract(
        "configs_30d",
        "/analytics/rtb-funnel/configs",
        (("days", 30),),
        buyer_scoped=True,
    ),
    Contract(
        "home_funnel_90d_limit_200",
        "/analytics/home/funnel",
        (("days", 90), ("limit", 200)),
        buyer_scoped=True,
    ),
    Contract(
        "home_configs_30d",
        "/analytics/home/configs",
        (("days", 30),),
        buyer_scoped=True,
    ),
    Contract(
        "endpoint_efficiency_90d",
        "/analytics/home/endpoint-efficiency",
        (("days", 90),),
        buyer_scoped=True,
    ),
    Contract(
        "data_health_90d_limit_1000",
        "/system/data-health",
        (("days", 90), ("limit", 1000)),
        buyer_scoped=True,
    ),
    Contract(
        "qps_summary_90d",
        "/analytics/qps-summary",
        (("days", 90),),
        buyer_scoped=True,
    ),
    Contract(
        "creatives_v2_limit_200",
        "/creatives/v2",
        (("days", 90), ("limit", 200), ("slim", "true")),
        buyer_scoped=True,
    ),
)


@dataclass
class Observation:
    status: int | None
    duration_ms: float
    response_bytes: int
    body_sha256: str | None
    schema_sha256: str | None
    json_valid: bool
    shadow_header: str | None
    error_type: str | None

    @property
    def succeeded(self) -> bool:
        return self.status == 200 and self.json_valid and self.error_type is None


class SoakError(RuntimeError):
    """Raised when the soak cannot start or write its evidence."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime | None = None) -> str:
    return (value or utc_now()).isoformat(timespec="seconds").replace("+00:00", "Z")


def _signal_stop(_signum: int, _frame: Any) -> None:
    global _STOP_REQUESTED
    _STOP_REQUESTED = True


def build_auth_headers(token: str, auth_header: str) -> dict[str, str]:
    value = token.strip()
    if not value:
        raise SoakError("The authentication token is empty.")
    selected = auth_header
    if selected == "auto":
        selected = "x-email" if "@" in value else "authorization"
    if selected == "x-email":
        return {"X-Email": value}
    if selected == "authorization":
        return {"Authorization": f"Bearer {value}"}
    raise SoakError("auth header must be auto, authorization, or x-email")


def load_token(token_file: Path, *, delete_after_read: bool) -> str:
    try:
        token = token_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise SoakError(f"Could not read token file: {type(exc).__name__}") from exc
    if delete_after_read:
        try:
            token_file.unlink()
        except OSError as exc:
            raise SoakError(
                f"Could not delete the one-use token file: {type(exc).__name__}"
            ) from exc
    if not token:
        raise SoakError("The authentication token file is empty.")
    return token


def join_url(base_url: str, path: str, params: dict[str, Any]) -> str:
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    return url


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _scalar_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    return type(value).__name__


def schema_paths(payload: Any, path: str = "$") -> list[str]:
    """Return a value-free JSON schema fingerprint with wildcarded list indexes."""

    if isinstance(payload, dict):
        rows = [f"{path}:object"]
        for key in sorted(payload):
            rows.extend(schema_paths(payload[key], f"{path}.{key}"))
        return rows
    if isinstance(payload, list):
        rows = [f"{path}:array"]
        child_rows: set[str] = set()
        for value in payload:
            child_rows.update(schema_paths(value, f"{path}[]"))
        rows.extend(sorted(child_rows))
        return rows
    return [f"{path}:{_scalar_type(payload)}"]


def schema_sha256(payload: Any) -> str:
    serialized = "\n".join(schema_paths(payload)).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def changed_json_paths(source: Any, target: Any, *, limit: int = 30) -> list[str]:
    """Return value-free paths that differ, capped to keep evidence compact."""

    changed: list[str] = []

    def add(path: str) -> None:
        if len(changed) < limit and path not in changed:
            changed.append(path)

    def visit(left: Any, right: Any, path: str) -> None:
        if len(changed) >= limit:
            return
        if type(left) is not type(right):
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                if left != right:
                    add(path)
                return
            add(path)
            return
        if isinstance(left, dict):
            for key in sorted(set(left) | set(right)):
                child_path = f"{path}.{key}"
                if key not in left or key not in right:
                    add(child_path)
                else:
                    visit(left[key], right[key], child_path)
            return
        if isinstance(left, list):
            if len(left) != len(right):
                add(f"{path}.length")
            for index, (left_value, right_value) in enumerate(zip(left, right)):
                visit(left_value, right_value, f"{path}[{index}]")
            return
        if left != right:
            add(path)

    visit(source, target, "$")
    return changed


def runtime_identity(payload: Any) -> dict[str, str]:
    """Extract only non-sensitive deployment identifiers from a health body."""

    if not isinstance(payload, dict):
        return {}
    result: dict[str, str] = {}
    for key in ("release_version", "version", "git_sha"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            result[key] = value.strip()
    return result


class ReadOnlyClient:
    def __init__(
        self,
        *,
        base_url: str,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> None:
        self.base_url = base_url
        self.headers = headers
        self.timeout_seconds = timeout_seconds

    def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> tuple[Observation, Any | None]:
        request = urllib.request.Request(
            join_url(self.base_url, path, params or {}),
            headers={
                **self.headers,
                "Accept": "application/json",
                "User-Agent": "catscan-read-only-soak/1",
            },
            method="GET",
        )
        started = time.monotonic()
        status: int | None = None
        response_headers: dict[str, str] = {}
        body = b""
        error_type: str | None = None
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                status = int(response.getcode())
                response_headers = {
                    key.lower(): value for key, value in response.headers.items()
                }
                body = response.read()
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            response_headers = {
                key.lower(): value for key, value in exc.headers.items()
            }
            body = exc.read()
            error_type = "http_error"
        except urllib.error.URLError:
            error_type = "url_error"
        except TimeoutError:
            error_type = "timeout"
        except OSError:
            error_type = "os_error"
        duration_ms = round((time.monotonic() - started) * 1000, 3)

        payload: Any | None = None
        json_valid = False
        if body:
            try:
                payload = json.loads(body.decode("utf-8"))
                json_valid = True
            except (UnicodeDecodeError, json.JSONDecodeError):
                error_type = error_type or "invalid_json"

        body_hash = (
            hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
            if json_valid
            else hashlib.sha256(body).hexdigest() if body else None
        )
        schema_hash = schema_sha256(payload) if json_valid else None
        return (
            Observation(
                status=status,
                duration_ms=duration_ms,
                response_bytes=len(body),
                body_sha256=body_hash,
                schema_sha256=schema_hash,
                json_valid=json_valid,
                shadow_header=response_headers.get("x-catscan-shadow"),
                error_type=error_type,
            ),
            payload,
        )


def _seat_ids(payload: Any) -> set[str]:
    if not isinstance(payload, list):
        return set()
    result: set[str] = set()
    for row in payload:
        if not isinstance(row, dict):
            continue
        for key in ("buyer_id", "buyer_account_id", "id"):
            value = row.get(key)
            if value is not None and str(value).strip():
                result.add(str(value).strip())
                break
    return result


def discover_shared_buyer(
    source: ReadOnlyClient,
    target: ReadOnlyClient,
) -> str:
    source_observation, source_payload = source.get("/seats")
    target_observation, target_payload = target.get("/seats")
    if not source_observation.succeeded:
        raise SoakError("Could not discover buyer access from the source /seats endpoint.")
    if not target_observation.succeeded:
        raise SoakError("Could not discover buyer access from the target /seats endpoint.")
    shared = sorted(_seat_ids(source_payload) & _seat_ids(target_payload))
    if not shared:
        raise SoakError("No shared buyer was returned by both /seats endpoints.")
    return shared[0]


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * fraction + 0.5)))
    return round(ordered[index], 3)


def summarize(runs: list[dict[str, Any]], *, started_at: str) -> dict[str, Any]:
    contract_summary: dict[str, dict[str, Any]] = {}
    total_pairs = 0
    source_failures = 0
    target_failures = 0
    shadow_header_failures = 0
    exact_matches = 0
    schema_matches = 0

    for run in runs:
        for pair in run["contracts"]:
            total_pairs += 1
            source = pair["source"]
            target = pair["target"]
            source_ok = (
                source["status"] == 200
                and source["json_valid"]
                and source["error_type"] is None
            )
            target_ok = (
                target["status"] == 200
                and target["json_valid"]
                and target["error_type"] is None
            )
            source_failures += int(not source_ok)
            target_failures += int(not target_ok)
            shadow_header_failures += int(
                target["shadow_header"] != EXPECTED_TARGET_SHADOW_HEADER
            )
            exact_matches += int(pair["result_match"])
            schema_matches += int(pair["schema_match"])

            stats = contract_summary.setdefault(
                pair["name"],
                {
                    "attempts": 0,
                    "source_successes": 0,
                    "target_successes": 0,
                    "result_matches": 0,
                    "schema_matches": 0,
                    "_source_ms": [],
                    "_target_ms": [],
                },
            )
            stats["attempts"] += 1
            stats["source_successes"] += int(source_ok)
            stats["target_successes"] += int(target_ok)
            stats["result_matches"] += int(pair["result_match"])
            stats["schema_matches"] += int(pair["schema_match"])
            stats["_source_ms"].append(source["duration_ms"])
            stats["_target_ms"].append(target["duration_ms"])

    for stats in contract_summary.values():
        source_ms = stats.pop("_source_ms")
        target_ms = stats.pop("_target_ms")
        stats["source_latency_ms"] = {
            "p50": percentile(source_ms, 0.50),
            "p95": percentile(source_ms, 0.95),
            "max": round(max(source_ms), 3) if source_ms else None,
        }
        stats["target_latency_ms"] = {
            "p50": percentile(target_ms, 0.50),
            "p95": percentile(target_ms, 0.95),
            "max": round(max(target_ms), 3) if target_ms else None,
        }

    return {
        "report_version": REPORT_VERSION,
        "started_at": started_at,
        "updated_at": iso_utc(),
        "runs_completed": len(runs),
        "endpoint_pairs": total_pairs,
        "source_request_failures": source_failures,
        "target_request_failures": target_failures,
        "target_shadow_header_failures": shadow_header_failures,
        "exact_result_matches": exact_matches,
        "exact_result_mismatches": total_pairs - exact_matches,
        "schema_matches": schema_matches,
        "schema_mismatches": total_pairs - schema_matches,
        "contracts": contract_summary,
        "timing_caveat": (
            "Source and target use different network paths; latency is directional "
            "soak evidence, not a controlled same-network benchmark."
        ),
        "result_caveat": (
            "The rehearsal target is an older database snapshot. Exact result drift "
            "can be expected while GCP remains writable; request and schema failures "
            "are counted separately."
        ),
    }


def write_json_atomic(path: Path, payload: Any) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def run_iteration(
    *,
    run_number: int,
    source: ReadOnlyClient,
    target: ReadOnlyClient,
    buyer_id: str,
) -> dict[str, Any]:
    started_at = iso_utc()
    pairs: list[dict[str, Any]] = []
    source_first = run_number % 2 == 1
    for contract in CONTRACTS:
        params = dict(contract.params)
        if contract.buyer_scoped:
            params["buyer_id"] = buyer_id

        if source_first:
            source_observation, source_payload = source.get(contract.path, params)
            target_observation, target_payload = target.get(contract.path, params)
        else:
            target_observation, target_payload = target.get(contract.path, params)
            source_observation, source_payload = source.get(contract.path, params)

        both_json = source_observation.json_valid and target_observation.json_valid
        result_match = bool(
            both_json
            and source_observation.succeeded
            and target_observation.succeeded
            and source_observation.body_sha256 == target_observation.body_sha256
        )
        schema_match = bool(
            both_json
            and source_observation.schema_sha256 == target_observation.schema_sha256
        )
        paths = (
            changed_json_paths(source_payload, target_payload)
            if both_json and not result_match
            else []
        )
        pairs.append(
            {
                "name": contract.name,
                "source": asdict(source_observation),
                "target": asdict(target_observation),
                "result_match": result_match,
                "schema_match": schema_match,
                "changed_paths": paths,
                "changed_paths_truncated": len(paths) >= 30,
                **(
                    {
                        "runtime_identity": {
                            "source": runtime_identity(source_payload),
                            "target": runtime_identity(target_payload),
                        }
                    }
                    if contract.name == "health" and both_json
                    else {}
                ),
            }
        )

    return {
        "run_number": run_number,
        "started_at": started_at,
        "completed_at": iso_utc(),
        "request_order": "source-first" if source_first else "target-first",
        "contracts": pairs,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Repeatedly compare read-only CatScan API contracts."
    )
    parser.add_argument("--source-base-url", required=True)
    parser.add_argument("--target-base-url", required=True)
    parser.add_argument("--source-label", default="gcp")
    parser.add_argument("--target-label", default="hetzner-shadow")
    parser.add_argument("--token-file", type=Path, required=True)
    parser.add_argument(
        "--delete-token-file",
        action="store_true",
        help="Delete the exact one-use token file immediately after reading it.",
    )
    parser.add_argument(
        "--auth-header",
        choices=("auto", "authorization", "x-email"),
        default="auto",
    )
    parser.add_argument(
        "--buyer-id-env",
        default="CATSCAN_SOAK_BUYER_ID",
        help="Optional environment variable containing the buyer ID; otherwise discover a shared seat.",
    )
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--interval-seconds", type=float, default=900.0)
    parser.add_argument("--duration-seconds", type=float, default=0.0)
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit nonzero after completion if a request or target shadow-header check failed.",
    )
    args = parser.parse_args(argv)
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")
    if args.interval_seconds < 0:
        parser.error("--interval-seconds cannot be negative")
    if args.duration_seconds < 0:
        parser.error("--duration-seconds cannot be negative")
    if args.iterations < 1:
        parser.error("--iterations must be at least 1")
    if args.duration_seconds > 0 and args.iterations != 1:
        parser.error("Use either --duration-seconds or --iterations, not both.")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    started_at = iso_utc()
    try:
        token = load_token(args.token_file, delete_after_read=args.delete_token_file)
        headers = build_auth_headers(token, args.auth_header)
        source = ReadOnlyClient(
            base_url=args.source_base_url,
            headers=headers,
            timeout_seconds=args.timeout_seconds,
        )
        target = ReadOnlyClient(
            base_url=args.target_base_url,
            headers=headers,
            timeout_seconds=args.timeout_seconds,
        )
        buyer_id = os.getenv(args.buyer_id_env, "").strip()
        if not buyer_id:
            buyer_id = discover_shared_buyer(source, target)
        args.report_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, SoakError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2

    metadata = {
        "report_version": REPORT_VERSION,
        "started_at": started_at,
        "source_label": args.source_label,
        "target_label": args.target_label,
        "contracts": [contract.name for contract in CONTRACTS],
        "buyer_selection": (
            f"environment:{args.buyer_id_env}"
            if os.getenv(args.buyer_id_env, "").strip()
            else "first shared seat from both deployments"
        ),
        "buyer_id_recorded": False,
        "methods": ["GET"],
        "target_shadow_header_required": EXPECTED_TARGET_SHADOW_HEADER,
        "timeout_seconds": args.timeout_seconds,
        "interval_seconds": args.interval_seconds,
        "duration_seconds": args.duration_seconds,
        "iterations": None if args.duration_seconds > 0 else args.iterations,
    }
    write_json_atomic(args.report_dir / "metadata.json", metadata)

    runs: list[dict[str, Any]] = []
    deadline = (
        time.monotonic() + args.duration_seconds
        if args.duration_seconds > 0
        else None
    )
    run_limit = None if deadline is not None else args.iterations
    run_number = 0

    while not _STOP_REQUESTED:
        if run_limit is not None and run_number >= run_limit:
            break
        run_number += 1
        run = run_iteration(
            run_number=run_number,
            source=source,
            target=target,
            buyer_id=buyer_id,
        )
        runs.append(run)
        write_json_atomic(args.report_dir / f"run-{run_number:04d}.json", run)
        summary = summarize(runs, started_at=started_at)
        write_json_atomic(args.report_dir / "summary.json", summary)
        print(
            json.dumps(
                {
                    "run": run_number,
                    "completed_at": run["completed_at"],
                    "source_failures": summary["source_request_failures"],
                    "target_failures": summary["target_request_failures"],
                    "shadow_header_failures": summary[
                        "target_shadow_header_failures"
                    ],
                    "exact_mismatches": summary["exact_result_mismatches"],
                    "schema_mismatches": summary["schema_mismatches"],
                },
                sort_keys=True,
            ),
            flush=True,
        )

        if deadline is not None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            sleep_seconds = min(args.interval_seconds, remaining)
        else:
            if run_number >= (run_limit or 0):
                break
            sleep_seconds = args.interval_seconds

        sleep_until = time.monotonic() + sleep_seconds
        while not _STOP_REQUESTED and time.monotonic() < sleep_until:
            time.sleep(min(1.0, sleep_until - time.monotonic()))

    summary = summarize(runs, started_at=started_at)
    summary["stopped_by_signal"] = _STOP_REQUESTED
    write_json_atomic(args.report_dir / "summary.json", summary)
    if args.strict and (
        summary["source_request_failures"]
        or summary["target_request_failures"]
        or summary["target_shadow_header_failures"]
    ):
        return 1
    return 0


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _signal_stop)
    signal.signal(signal.SIGTERM, _signal_stop)
    raise SystemExit(main())
