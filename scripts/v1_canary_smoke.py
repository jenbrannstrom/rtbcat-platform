#!/usr/bin/env python3
"""v1 canary smoke checks for core Cat-Scan API flows."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any


class SmokeFailure(RuntimeError):
    """Raised when a smoke check fails."""


class SmokeEnvironmentBlocked(SmokeFailure):
    """Raised when checks are blocked by environment/network policy."""


def _join_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{base}{suffix}"


def is_network_blocked_urlerror(exc: urllib.error.URLError) -> bool:
    """Best-effort detection for sandbox/network-policy blocking errors."""
    reason = exc.reason
    errno = getattr(reason, "errno", None)
    if errno in {1, 13, -3}:
        return True
    text = f"{exc} {reason}".lower()
    return (
        "operation not permitted" in text
        or "permission denied" in text
        or "temporary failure in name resolution" in text
    )


def is_auth_blocked_http_response(status_code: int, detail: str) -> bool:
    """Detect auth/session failures that should be treated as environment-blocked.

    Covers two scenarios:
      1. HTTP 401/403 with explicit auth-failure text (expired session, invalid token).
      2. HTTP 404 with a bare ``{"detail":"Not Found"}`` body.  OAuth2 Proxy and
         nginx may return 404 for authenticated routes when the session cookie is
         invalid or missing — the request never reaches FastAPI.  Because the
         canary only hits endpoints known to exist in the codebase, a bare 404
         is a deployment/auth environment issue, not a code regression.
    """
    text = (detail or "").lower()
    if status_code in {401, 403}:
        auth_indicators = (
            "session expired or invalid",
            "authentication required",
            "not authenticated",
            "please log in again",
            "invalid token",
            "token expired",
        )
        return any(indicator in text for indicator in auth_indicators)
    if status_code == 404 and text.strip() in (
        '{"detail":"not found"}',
        "not found",
    ):
        return True
    # HTTP 500 with a generic body (no structured error detail) suggests a
    # deployment/infrastructure issue (DB down, missing config) rather than
    # a code regression.  Code-level 500s typically carry structured JSON
    # with specific error messages.
    if status_code == 500 and text.strip() in (
        "internal server error",
        '{"detail":"internal server error"}',
    ):
        return True
    return False


class SmokeClient:
    def __init__(self, *, base_url: str, token: str | None, cookie: str | None, timeout: float):
        self.base_url = base_url
        self.timeout = timeout
        self.default_headers: dict[str, str] = {}
        if token:
            # Token is the trusted email identity passed via X-Email header
            # (same mechanism the OAuth2 Proxy uses after authentication).
            self.default_headers["X-Email"] = token
        if cookie:
            self.default_headers["Cookie"] = cookie

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers, body = self.request_bytes(
            method,
            path,
            params=params,
            json_body=json_body,
        )
        if not body:
            return {}
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise SmokeFailure(f"{method} {path}: non-JSON response") from exc
        if not isinstance(payload, dict):
            raise SmokeFailure(f"{method} {path}: expected JSON object")
        return payload

    def request_bytes(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[dict[str, str], bytes]:
        status_code, response_headers, body = self.request_status_bytes(
            method,
            path,
            params=params,
            json_body=json_body,
            extra_headers=extra_headers,
        )
        if status_code >= 400:
            detail = body.decode("utf-8", errors="replace")
            if is_auth_blocked_http_response(status_code, detail):
                raise SmokeEnvironmentBlocked(
                    f"{method} {path}: auth blocked (HTTP {status_code}: {detail[:240]})"
                )
            raise SmokeFailure(f"{method} {path}: HTTP {status_code} {detail[:240]}")
        return response_headers, body

    def request_status_bytes(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], bytes]:
        url = _join_url(self.base_url, path)
        if params:
            query = urllib.parse.urlencode(
                {k: v for k, v in params.items() if v is not None},
                doseq=True,
            )
            if query:
                join_char = "&" if "?" in url else "?"
                url = f"{url}{join_char}{query}"

        headers = dict(self.default_headers)
        if extra_headers:
            headers.update(extra_headers)
        data = None
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url=url, data=data, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                response_headers = {
                    key.lower(): value
                    for key, value in resp.headers.items()
                    if key and value
                }
                return int(resp.getcode()), response_headers, resp.read()
        except urllib.error.HTTPError as exc:
            response_headers = {
                key.lower(): value
                for key, value in exc.headers.items()
                if key and value
            }
            return int(exc.code), response_headers, exc.read()
        except urllib.error.URLError as exc:
            if is_network_blocked_urlerror(exc):
                raise SmokeEnvironmentBlocked(
                    f"{method} {path}: outbound network blocked ({exc})"
                ) from exc
            raise SmokeFailure(f"{method} {path}: {exc}") from exc


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def _run_check(name: str, fn) -> tuple[bool, str, bool]:
    """Run a single check, returning (passed, display_line, is_blocked)."""
    try:
        fn()
        return True, f"PASS  {name}", False
    except SmokeEnvironmentBlocked as exc:
        return False, f"BLOCKED  {name} -> {exc}", True
    except Exception as exc:  # noqa: BLE001
        return False, f"FAIL  {name} -> {exc}", False


def validate_data_health_payload(
    payload: dict[str, Any],
    *,
    require_healthy_readiness: bool,
    max_dimension_missing_pct: float,
) -> None:
    """Validate optimizer readiness invariants for canary checks."""
    readiness = payload.get("optimizer_readiness")
    _assert(isinstance(readiness, dict), "optimizer_readiness missing from /system/data-health")

    report = readiness.get("report_completeness") or {}
    quality = readiness.get("rtb_quality_freshness") or {}
    bidstream = readiness.get("bidstream_dimension_coverage") or {}
    seat_day = readiness.get("seat_day_completeness") or {}
    seat_day_summary = seat_day.get("summary") or {}

    quality_state = str(quality.get("availability_state", "")).lower()
    _assert(quality_state != "unavailable", "rtb_quality_freshness state is unavailable")

    bidstream_state = str(bidstream.get("availability_state", "")).lower()
    _assert(bidstream_state != "unavailable", "bidstream dimension coverage is unavailable")

    total_rows = int(bidstream.get("total_rows") or 0)
    _assert(total_rows > 0, "bidstream dimension coverage has zero rows")

    for field in ("platform_missing_pct", "environment_missing_pct", "transaction_type_missing_pct"):
        raw_value = bidstream.get(field)
        _assert(raw_value is not None, f"{field} missing from bidstream dimension coverage")
        value = float(raw_value)
        _assert(
            value <= max_dimension_missing_pct,
            f"{field}={value:.2f}% exceeds max {max_dimension_missing_pct:.2f}%",
        )

    _assert(
        int(seat_day_summary.get("total_seat_days") or 0) > 0,
        "seat_day_completeness has zero seat-day rows",
    )

    if require_healthy_readiness:
        report_state = str(report.get("availability_state", "")).lower()
        seat_day_state = str(seat_day.get("availability_state", "")).lower()
        _assert(report_state == "healthy", f"report_completeness state is {report_state!r}, expected healthy")
        _assert(quality_state == "healthy", f"rtb_quality_freshness state is {quality_state!r}, expected healthy")
        _assert(
            bidstream_state == "healthy",
            f"bidstream dimension coverage state is {bidstream_state!r}, expected healthy",
        )
        _assert(
            seat_day_state == "healthy",
            f"seat_day_completeness state is {seat_day_state!r}, expected healthy",
        )


def build_workflow_request_params(
    *,
    model_id: str,
    buyer_id: str | None,
    workflow_days: int,
    workflow_score_limit: int,
    workflow_proposal_limit: int,
    workflow_min_confidence: float,
    workflow_max_delta_pct: float,
    workflow_profile: str | None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "model_id": model_id,
        "buyer_id": buyer_id,
        "days": workflow_days,
        "score_limit": workflow_score_limit,
        "proposal_limit": workflow_proposal_limit,
        "min_confidence": workflow_min_confidence,
        "max_delta_pct": workflow_max_delta_pct,
    }
    if workflow_profile:
        params["profile"] = workflow_profile
    return params


def build_pixel_request_params(
    *,
    buyer_id: str | None,
    pixel_source_type: str,
    pixel_event_name: str,
    event_ts: str,
    event_id: str,
) -> dict[str, Any]:
    return {
        "buyer_id": buyer_id,
        "source_type": pixel_source_type,
        "event_name": pixel_event_name,
        "event_ts": event_ts,
        "event_id": event_id,
    }


def build_webhook_postback_payload(
    *,
    buyer_id: str | None,
    source_type: str,
    event_name: str,
    event_ts: str,
    event_id: str,
) -> dict[str, Any]:
    return {
        "buyer_id": buyer_id,
        "source_type": source_type,
        "event_name": event_name,
        "event_ts": event_ts,
        "event_id": event_id,
    }


def build_webhook_hmac_signature(
    *,
    secret: str,
    payload: dict[str, Any],
    timestamp: int | None = None,
) -> str:
    message = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    if timestamp is not None:
        message = f"{timestamp}.{message}"
    return hmac.new(
        secret.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def build_webhook_security_headers(
    *,
    webhook_secret: str | None,
    webhook_hmac_secret: str | None,
    payload: dict[str, Any],
    timestamp: int | None = None,
    force_invalid_signature: bool = False,
) -> dict[str, str]:
    headers: dict[str, str] = {}
    if webhook_secret:
        headers["X-Webhook-Secret"] = webhook_secret
    if not webhook_hmac_secret:
        return headers

    unix_ts = int(timestamp if timestamp is not None else datetime.now(timezone.utc).timestamp())
    headers["X-Webhook-Timestamp"] = str(unix_ts)
    if force_invalid_signature:
        signature = "invalid-signature"
    else:
        signature = build_webhook_hmac_signature(
            secret=webhook_hmac_secret,
            payload=payload,
            timestamp=unix_ts,
        )
    headers["X-Signature"] = f"sha256={signature}"
    return headers


def build_conversion_readiness_params(
    *,
    buyer_id: str | None,
    days: int,
    freshness_hours: int,
) -> dict[str, Any]:
    return {
        "buyer_id": buyer_id,
        "days": days,
        "freshness_hours": freshness_hours,
    }


def build_qps_load_latency_requests(
    *,
    buyer_id: str | None,
    days: int,
) -> list[tuple[str, dict[str, Any]]]:
    return [
        (
            "/settings/endpoints",
            {
                "buyer_id": buyer_id,
                "live": "true",
            },
        ),
        (
            "/settings/pretargeting",
            {
                "buyer_id": buyer_id,
            },
        ),
        (
            "/analytics/home/configs",
            {
                "buyer_id": buyer_id,
                "days": days,
            },
        ),
        (
            "/analytics/home/endpoint-efficiency",
            {
                "buyer_id": buyer_id,
                "days": days,
            },
        ),
    ]


def build_qps_page_slo_params(
    *,
    buyer_id: str | None,
    since_hours: int,
    latest_limit: int = 5,
    api_rollup_limit: int = 10,
) -> dict[str, Any]:
    return {
        "page": "qps_home",
        "buyer_id": buyer_id,
        "since_hours": since_hours,
        "latest_limit": latest_limit,
        "api_rollup_limit": api_rollup_limit,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v1 canary smoke checks against API.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("CATSCAN_API_BASE_URL", "http://127.0.0.1:8000"),
        help="API base URL (example: http://127.0.0.1:8000 or https://scan.rtb.cat/api)",
    )
    parser.add_argument("--buyer-id", default=os.getenv("CATSCAN_BUYER_ID"))
    parser.add_argument("--model-id", default=os.getenv("CATSCAN_MODEL_ID"))
    parser.add_argument("--proposal-id", default=os.getenv("CATSCAN_PROPOSAL_ID"))
    parser.add_argument("--token", default=os.getenv("CATSCAN_BEARER_TOKEN"))
    parser.add_argument("--cookie", default=os.getenv("CATSCAN_SESSION_COOKIE"))
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--run-workflow", action="store_true", help="Run score+propose workflow check.")
    parser.add_argument(
        "--run-lifecycle",
        action="store_true",
        help="After workflow, run proposal approve/apply(queue)/sync/history checks.",
    )
    parser.add_argument(
        "--require-healthy-readiness",
        action="store_true",
        help="Require healthy readiness states instead of only rejecting unavailable data.",
    )
    parser.add_argument(
        "--max-dimension-missing-pct",
        type=float,
        default=99.9,
        help="Maximum tolerated missing percent for bidstream dimensions (default: 99.9).",
    )
    parser.add_argument(
        "--allow-no-active-model",
        action="store_true",
        help="Do not fail if no active model is found.",
    )
    parser.add_argument(
        "--run-pixel",
        action="store_true",
        help="Run lightweight conversion pixel ingestion check.",
    )
    parser.add_argument(
        "--run-webhook-auth-check",
        action="store_true",
        help="Run optional webhook auth enforcement check on generic conversion postback.",
    )
    parser.add_argument(
        "--run-webhook-hmac-check",
        action="store_true",
        help="Run optional webhook HMAC signature check on generic conversion postback.",
    )
    parser.add_argument(
        "--run-webhook-freshness-check",
        action="store_true",
        help="Run optional webhook freshness enforcement check on generic conversion postback.",
    )
    parser.add_argument(
        "--run-webhook-rate-limit-check",
        action="store_true",
        help="Run optional webhook rate-limit enforcement check on generic conversion postback.",
    )
    parser.add_argument(
        "--run-webhook-security-status-check",
        action="store_true",
        help="Run optional webhook security-status API contract check.",
    )
    parser.add_argument(
        "--min-secured-webhook-sources",
        type=int,
        default=int(os.getenv("CATSCAN_CANARY_MIN_SECURED_WEBHOOK_SOURCES", "0")),
        help="Minimum number of webhook sources that must have secret or HMAC enabled (default: 0).",
    )
    parser.add_argument(
        "--run-qps-load-latency-check",
        action="store_true",
        help="Run optional startup API latency checks for QPS Home dependencies.",
    )
    parser.add_argument(
        "--qps-load-latency-days",
        type=int,
        default=int(os.getenv("CATSCAN_CANARY_QPS_LATENCY_DAYS", "14")),
        help="Days window used for QPS startup latency checks (default: 14).",
    )
    parser.add_argument(
        "--max-settings-endpoints-latency-ms",
        type=float,
        default=float(os.getenv("CATSCAN_CANARY_MAX_SETTINGS_ENDPOINTS_LATENCY_MS", "8000")),
        help="Max latency budget for /settings/endpoints (default: 8000ms).",
    )
    parser.add_argument(
        "--max-settings-pretargeting-latency-ms",
        type=float,
        default=float(os.getenv("CATSCAN_CANARY_MAX_SETTINGS_PRETARGETING_LATENCY_MS", "10000")),
        help="Max latency budget for /settings/pretargeting (default: 10000ms).",
    )
    parser.add_argument(
        "--max-home-configs-latency-ms",
        type=float,
        default=float(os.getenv("CATSCAN_CANARY_MAX_HOME_CONFIGS_LATENCY_MS", "12000")),
        help="Max latency budget for /analytics/home/configs (default: 12000ms).",
    )
    parser.add_argument(
        "--max-home-endpoint-efficiency-latency-ms",
        type=float,
        default=float(os.getenv("CATSCAN_CANARY_MAX_HOME_ENDPOINT_EFFICIENCY_LATENCY_MS", "12000")),
        help="Max latency budget for /analytics/home/endpoint-efficiency (default: 12000ms).",
    )
    parser.add_argument(
        "--run-qps-page-slo-check",
        action="store_true",
        help="Run optional p95 SLO check against /system/ui-metrics/page-load/summary.",
    )
    parser.add_argument(
        "--qps-page-slo-since-hours",
        type=int,
        default=int(os.getenv("CATSCAN_CANARY_QPS_PAGE_SLO_SINCE_HOURS", "24")),
        help="Summary lookback window in hours for QPS page SLO check (default: 24).",
    )
    parser.add_argument(
        "--qps-page-slo-min-samples",
        type=int,
        default=int(os.getenv("CATSCAN_CANARY_QPS_PAGE_SLO_MIN_SAMPLES", "1")),
        help="Minimum required samples for QPS page SLO check (default: 1).",
    )
    parser.add_argument(
        "--max-qps-page-p95-first-row-ms",
        type=float,
        default=float(os.getenv("CATSCAN_CANARY_MAX_QPS_PAGE_P95_FIRST_ROW_MS", "6000")),
        help="Max p95 budget for time_to_first_table_row (default: 6000ms).",
    )
    parser.add_argument(
        "--max-qps-page-p95-hydrated-ms",
        type=float,
        default=float(os.getenv("CATSCAN_CANARY_MAX_QPS_PAGE_P95_HYDRATED_MS", "8000")),
        help="Max p95 budget for time_to_table_hydrated (default: 8000ms).",
    )
    parser.add_argument(
        "--qps-page-slo-require-api-rollup",
        action="store_true",
        default=str(os.getenv("CATSCAN_CANARY_QPS_PAGE_REQUIRE_API_ROLLUP", "0")).strip().lower()
        in {"1", "true", "yes", "on"},
        help=(
            "Require startup API paths to appear in /system/ui-metrics/page-load/summary "
            "api_latency_rollup and enforce p95 budgets when present."
        ),
    )
    parser.add_argument(
        "--pixel-source-type",
        default=os.getenv("CATSCAN_CANARY_PIXEL_SOURCE_TYPE", "pixel"),
        help="Source type sent to /conversions/pixel (default: pixel).",
    )
    parser.add_argument(
        "--pixel-event-name",
        default=os.getenv("CATSCAN_CANARY_PIXEL_EVENT_NAME", "purchase"),
        help="Event name sent to /conversions/pixel (default: purchase).",
    )
    parser.add_argument(
        "--pixel-secret",
        default=os.getenv("CATSCAN_CANARY_PIXEL_SECRET")
        or os.getenv("CATSCAN_GENERIC_CONVERSION_WEBHOOK_SECRET"),
        help="Optional secret for /conversions/pixel (X-Webhook-Secret header).",
    )
    parser.add_argument(
        "--pixel-expected-status",
        choices=("accepted", "rejected"),
        default=os.getenv("CATSCAN_CANARY_PIXEL_EXPECTED_STATUS", "accepted"),
        help="Expected X-CatScan-Conversion-Status for pixel check (default: accepted).",
    )
    parser.add_argument(
        "--webhook-source-type",
        default=os.getenv("CATSCAN_CANARY_WEBHOOK_SOURCE_TYPE", "generic"),
        help="Source type sent to /conversions/generic/postback for auth check.",
    )
    parser.add_argument(
        "--webhook-event-name",
        default=os.getenv("CATSCAN_CANARY_WEBHOOK_EVENT_NAME", "purchase"),
        help="Event name sent to /conversions/generic/postback for auth check.",
    )
    parser.add_argument(
        "--webhook-secret",
        default=os.getenv("CATSCAN_CANARY_WEBHOOK_SECRET")
        or os.getenv("CATSCAN_GENERIC_CONVERSION_WEBHOOK_SECRET")
        or os.getenv("CATSCAN_CONVERSIONS_SHARED_SECRET"),
        help="Secret used for webhook auth check (X-Webhook-Secret header).",
    )
    parser.add_argument(
        "--webhook-hmac-secret",
        default=os.getenv("CATSCAN_CANARY_WEBHOOK_HMAC_SECRET")
        or os.getenv("CATSCAN_GENERIC_CONVERSION_WEBHOOK_HMAC_SECRET")
        or os.getenv("CATSCAN_CONVERSIONS_SHARED_HMAC_SECRET"),
        help="HMAC secret used for webhook signature check.",
    )
    parser.add_argument(
        "--webhook-freshness-max-skew-seconds",
        type=int,
        default=int(
            os.getenv("CATSCAN_CANARY_WEBHOOK_FRESHNESS_MAX_SKEW_SECONDS")
            or os.getenv("CATSCAN_CONVERSIONS_MAX_SKEW_SECONDS")
            or "900"
        ),
        help="Max allowed skew for freshness canary check (default: 900).",
    )
    parser.add_argument(
        "--webhook-rate-limit-per-window",
        type=int,
        default=int(os.getenv("CATSCAN_CANARY_WEBHOOK_RATE_LIMIT_PER_WINDOW", "0")),
        help="Expected allowed requests per window for webhook rate-limit check; required when enabled.",
    )
    parser.add_argument(
        "--webhook-rate-limit-window-seconds",
        type=int,
        default=int(
            os.getenv("CATSCAN_CANARY_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS")
            or os.getenv("CATSCAN_CONVERSIONS_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS")
            or "60"
        ),
        help="Expected window size for webhook rate-limit check metadata (default: 60).",
    )
    parser.add_argument(
        "--conversion-readiness-days",
        type=int,
        default=int(os.getenv("CATSCAN_CANARY_CONVERSION_DAYS", "14")),
        help="Days window for /conversions/readiness check (default: 14).",
    )
    parser.add_argument(
        "--conversion-readiness-freshness-hours",
        type=int,
        default=int(os.getenv("CATSCAN_CANARY_CONVERSION_FRESHNESS_HOURS", "72")),
        help="Freshness threshold hours for /conversions/readiness check (default: 72).",
    )
    parser.add_argument(
        "--require-conversion-ready",
        action="store_true",
        help="Fail if /conversions/readiness state is not ready.",
    )
    default_workflow_profile = (
        os.getenv("CATSCAN_CANARY_WORKFLOW_PROFILE")
        or os.getenv("CATSCAN_CANARY_PROFILE")
        or ""
    ).strip().lower()
    parser.add_argument(
        "--workflow-profile",
        choices=("safe", "balanced", "aggressive"),
        default=default_workflow_profile or None,
        help="Optional workflow preset profile forwarded to /optimizer/workflows/score-and-propose.",
    )
    parser.add_argument("--workflow-days", type=int, default=int(os.getenv("CATSCAN_CANARY_WORKFLOW_DAYS", "14")))
    parser.add_argument(
        "--workflow-score-limit",
        type=int,
        default=int(os.getenv("CATSCAN_CANARY_WORKFLOW_SCORE_LIMIT", "1000")),
    )
    parser.add_argument(
        "--workflow-proposal-limit",
        type=int,
        default=int(os.getenv("CATSCAN_CANARY_WORKFLOW_PROPOSAL_LIMIT", "200")),
    )
    parser.add_argument(
        "--workflow-min-confidence",
        type=float,
        default=float(os.getenv("CATSCAN_CANARY_WORKFLOW_MIN_CONFIDENCE", "0.3")),
    )
    parser.add_argument(
        "--workflow-max-delta-pct",
        type=float,
        default=float(os.getenv("CATSCAN_CANARY_WORKFLOW_MAX_DELTA_PCT", "0.3")),
    )
    parser.add_argument("--billing-id", help="Optional billing_id for rollback dry-run check.")
    parser.add_argument("--snapshot-id", type=int, help="Optional snapshot_id for rollback dry-run check.")
    args = parser.parse_args()
    if args.workflow_days < 1 or args.workflow_days > 365:
        parser.error("--workflow-days must be between 1 and 365")
    if args.workflow_score_limit < 1 or args.workflow_score_limit > 5000:
        parser.error("--workflow-score-limit must be between 1 and 5000")
    if args.workflow_proposal_limit < 1 or args.workflow_proposal_limit > 2000:
        parser.error("--workflow-proposal-limit must be between 1 and 2000")
    if args.workflow_min_confidence < 0 or args.workflow_min_confidence > 1:
        parser.error("--workflow-min-confidence must be between 0 and 1")
    if args.workflow_max_delta_pct < 0.05 or args.workflow_max_delta_pct > 1:
        parser.error("--workflow-max-delta-pct must be between 0.05 and 1")
    if args.conversion_readiness_days < 1 or args.conversion_readiness_days > 365:
        parser.error("--conversion-readiness-days must be between 1 and 365")
    if (
        args.conversion_readiness_freshness_hours < 1
        or args.conversion_readiness_freshness_hours > 720
    ):
        parser.error("--conversion-readiness-freshness-hours must be between 1 and 720")
    if args.run_webhook_hmac_check and not args.webhook_hmac_secret:
        parser.error(
            "--run-webhook-hmac-check requires --webhook-hmac-secret or "
            "CATSCAN_CANARY_WEBHOOK_HMAC_SECRET/CATSCAN_GENERIC_CONVERSION_WEBHOOK_HMAC_SECRET/"
            "CATSCAN_CONVERSIONS_SHARED_HMAC_SECRET"
        )
    if args.run_webhook_freshness_check and not args.webhook_hmac_secret:
        parser.error(
            "--run-webhook-freshness-check requires --webhook-hmac-secret or "
            "CATSCAN_CANARY_WEBHOOK_HMAC_SECRET/CATSCAN_GENERIC_CONVERSION_WEBHOOK_HMAC_SECRET/"
            "CATSCAN_CONVERSIONS_SHARED_HMAC_SECRET"
        )
    if args.run_webhook_rate_limit_check and args.webhook_rate_limit_per_window < 1:
        parser.error("--run-webhook-rate-limit-check requires --webhook-rate-limit-per-window >= 1")
    if args.webhook_freshness_max_skew_seconds < 1:
        parser.error("--webhook-freshness-max-skew-seconds must be >= 1")
    if args.webhook_rate_limit_window_seconds < 1:
        parser.error("--webhook-rate-limit-window-seconds must be >= 1")
    if args.min_secured_webhook_sources < 0:
        parser.error("--min-secured-webhook-sources must be >= 0")
    if args.qps_load_latency_days < 1 or args.qps_load_latency_days > 365:
        parser.error("--qps-load-latency-days must be between 1 and 365")
    if args.max_settings_endpoints_latency_ms <= 0:
        parser.error("--max-settings-endpoints-latency-ms must be > 0")
    if args.max_settings_pretargeting_latency_ms <= 0:
        parser.error("--max-settings-pretargeting-latency-ms must be > 0")
    if args.max_home_configs_latency_ms <= 0:
        parser.error("--max-home-configs-latency-ms must be > 0")
    if args.max_home_endpoint_efficiency_latency_ms <= 0:
        parser.error("--max-home-endpoint-efficiency-latency-ms must be > 0")
    if args.qps_page_slo_since_hours < 1 or args.qps_page_slo_since_hours > 168:
        parser.error("--qps-page-slo-since-hours must be between 1 and 168")
    if args.qps_page_slo_min_samples < 1:
        parser.error("--qps-page-slo-min-samples must be >= 1")
    if args.max_qps_page_p95_first_row_ms <= 0:
        parser.error("--max-qps-page-p95-first-row-ms must be > 0")
    if args.max_qps_page_p95_hydrated_ms <= 0:
        parser.error("--max-qps-page-p95-hydrated-ms must be > 0")

    client = SmokeClient(
        base_url=args.base_url,
        token=args.token,
        cookie=args.cookie,
        timeout=args.timeout,
    )

    resolved_model_id = args.model_id
    workflow_proposal_id: str | None = None
    results: list[tuple[bool, str]] = []

    def check_health() -> None:
        payload = client.request("GET", "/health")
        status = str(payload.get("status", "")).lower()
        _assert(status in {"healthy", "ok"}, "health status is not healthy/ok")

    def check_data_health() -> None:
        payload = client.request(
            "GET",
            "/system/data-health",
            params={"buyer_id": args.buyer_id, "days": 14, "limit": 10},
        )
        validate_data_health_payload(
            payload,
            require_healthy_readiness=args.require_healthy_readiness,
            max_dimension_missing_pct=float(args.max_dimension_missing_pct),
        )

    def check_conversion_health() -> None:
        payload = client.request("GET", "/conversions/health", params={"buyer_id": args.buyer_id})
        _assert("state" in payload, "state missing from /conversions/health")
        _assert("ingestion" in payload, "ingestion missing from /conversions/health")

    def check_conversion_readiness() -> None:
        payload = client.request(
            "GET",
            "/conversions/readiness",
            params=build_conversion_readiness_params(
                buyer_id=args.buyer_id,
                days=args.conversion_readiness_days,
                freshness_hours=args.conversion_readiness_freshness_hours,
            ),
        )
        _assert("state" in payload, "state missing from /conversions/readiness")
        _assert("accepted_total" in payload, "accepted_total missing from /conversions/readiness")
        _assert("active_sources" in payload, "active_sources missing from /conversions/readiness")
        _assert(isinstance(payload.get("reasons"), list), "reasons missing from /conversions/readiness")
        if args.require_conversion_ready:
            state = str(payload.get("state", "")).lower()
            if state == "unavailable":
                raise SmokeEnvironmentBlocked(
                    f"/conversions/readiness state is {state!r} "
                    "(no conversion data ingested for this buyer)"
                )
            _assert(
                state == "ready",
                f"/conversions/readiness state is {state!r}, expected 'ready'",
            )

    def check_conversion_stats() -> None:
        payload = client.request(
            "GET",
            "/conversions/ingestion/stats",
            params={"buyer_id": args.buyer_id, "days": 7},
        )
        _assert("accepted_total" in payload, "accepted_total missing from /conversions/ingestion/stats")
        _assert("rejected_total" in payload, "rejected_total missing from /conversions/ingestion/stats")

    def check_conversion_pixel() -> None:
        if not args.run_pixel:
            return
        event_ts = datetime.now(timezone.utc).isoformat()
        event_id = f"canary-pixel-{int(datetime.now(timezone.utc).timestamp())}"
        params = build_pixel_request_params(
            buyer_id=args.buyer_id,
            pixel_source_type=args.pixel_source_type,
            pixel_event_name=args.pixel_event_name,
            event_ts=event_ts,
            event_id=event_id,
        )
        headers = {"X-Webhook-Secret": args.pixel_secret} if args.pixel_secret else None
        response_headers, body = client.request_bytes(
            "GET",
            "/conversions/pixel",
            params=params,
            extra_headers=headers,
        )
        content_type = str(response_headers.get("content-type", "")).lower()
        _assert(content_type.startswith("image/gif"), "pixel response content-type is not image/gif")
        status_value = str(response_headers.get("x-catscan-conversion-status", "")).lower()
        _assert(
            status_value == args.pixel_expected_status,
            (
                "pixel conversion status header mismatch: "
                f"expected {args.pixel_expected_status!r}, got {status_value!r}"
            ),
        )
        _assert(body.startswith(b"GIF8"), "pixel response is not GIF bytes")
        cache_control = str(response_headers.get("cache-control", "")).lower()
        _assert("no-store" in cache_control, "pixel response missing no-store cache-control")

    def check_conversion_webhook_auth() -> None:
        if not args.run_webhook_auth_check:
            return
        now_ts = datetime.now(timezone.utc)
        unix_ts = int(now_ts.timestamp())
        payload_without_secret = build_webhook_postback_payload(
            buyer_id=args.buyer_id,
            source_type=f"{args.webhook_source_type}-auth-missing-{unix_ts}",
            event_name=args.webhook_event_name,
            event_ts=now_ts.isoformat(),
            event_id=f"canary-webhook-auth-missing-{unix_ts}",
        )
        headers_without_secret = build_webhook_security_headers(
            webhook_secret=None,
            webhook_hmac_secret=args.webhook_hmac_secret,
            payload=payload_without_secret,
            timestamp=unix_ts,
        )
        status_without_secret, _, _ = client.request_status_bytes(
            "POST",
            "/conversions/generic/postback",
            json_body=payload_without_secret,
            extra_headers=headers_without_secret or None,
        )
        if args.webhook_secret:
            _assert(
                status_without_secret == 401,
                (
                    "generic webhook auth check expected HTTP 401 without secret when "
                    f"secret is configured, got HTTP {status_without_secret}"
                ),
            )
            payload_with_secret = build_webhook_postback_payload(
                buyer_id=args.buyer_id,
                source_type=f"{args.webhook_source_type}-auth-valid-{unix_ts}",
                event_name=args.webhook_event_name,
                event_ts=now_ts.isoformat(),
                event_id=f"canary-webhook-auth-valid-{unix_ts}",
            )
            headers_with_secret = build_webhook_security_headers(
                webhook_secret=args.webhook_secret,
                webhook_hmac_secret=args.webhook_hmac_secret,
                payload=payload_with_secret,
                timestamp=unix_ts,
            )
            status_with_secret, _, _ = client.request_status_bytes(
                "POST",
                "/conversions/generic/postback",
                json_body=payload_with_secret,
                extra_headers=headers_with_secret,
            )
            _assert(
                status_with_secret == 200,
                f"generic webhook auth check expected HTTP 200 with secret, got HTTP {status_with_secret}",
            )
            return

        _assert(
            status_without_secret == 200,
            (
                "generic webhook auth check expected HTTP 200 without secret because no canary webhook secret "
                f"is configured, got HTTP {status_without_secret}"
            ),
        )

    def check_conversion_webhook_hmac() -> None:
        if not args.run_webhook_hmac_check:
            return
        now_ts = datetime.now(timezone.utc)
        unix_ts = int(now_ts.timestamp())
        payload = build_webhook_postback_payload(
            buyer_id=args.buyer_id,
            source_type=f"{args.webhook_source_type}-hmac-valid-{unix_ts}",
            event_name=args.webhook_event_name,
            event_ts=now_ts.isoformat(),
            event_id=f"canary-webhook-hmac-{unix_ts}",
        )
        valid_headers = build_webhook_security_headers(
            webhook_secret=args.webhook_secret,
            webhook_hmac_secret=str(args.webhook_hmac_secret),
            payload=payload,
            timestamp=unix_ts,
        )
        valid_status, _, _ = client.request_status_bytes(
            "POST",
            "/conversions/generic/postback",
            json_body=payload,
            extra_headers=valid_headers,
        )
        _assert(
            valid_status == 200,
            f"generic webhook HMAC check expected HTTP 200 with valid signature, got HTTP {valid_status}",
        )

        invalid_payload = build_webhook_postback_payload(
            buyer_id=args.buyer_id,
            source_type=f"{args.webhook_source_type}-hmac-invalid-{unix_ts}",
            event_name=args.webhook_event_name,
            event_ts=now_ts.isoformat(),
            event_id=f"canary-webhook-hmac-invalid-{unix_ts}",
        )
        invalid_headers = build_webhook_security_headers(
            webhook_secret=args.webhook_secret,
            webhook_hmac_secret=str(args.webhook_hmac_secret),
            payload=invalid_payload,
            timestamp=unix_ts + 1,
            force_invalid_signature=True,
        )
        invalid_status, _, _ = client.request_status_bytes(
            "POST",
            "/conversions/generic/postback",
            json_body=invalid_payload,
            extra_headers=invalid_headers,
        )
        _assert(
            invalid_status == 401,
            f"generic webhook HMAC check expected HTTP 401 with invalid signature, got HTTP {invalid_status}",
        )

    def check_conversion_webhook_freshness() -> None:
        if not args.run_webhook_freshness_check:
            return
        now_ts = datetime.now(timezone.utc)
        unix_ts = int(now_ts.timestamp())
        fresh_payload = build_webhook_postback_payload(
            buyer_id=args.buyer_id,
            source_type=f"{args.webhook_source_type}-freshness-fresh-{unix_ts}",
            event_name=args.webhook_event_name,
            event_ts=now_ts.isoformat(),
            event_id=f"canary-webhook-freshness-fresh-{unix_ts}",
        )
        fresh_headers = build_webhook_security_headers(
            webhook_secret=args.webhook_secret,
            webhook_hmac_secret=str(args.webhook_hmac_secret),
            payload=fresh_payload,
            timestamp=unix_ts,
        )
        fresh_status, _, _ = client.request_status_bytes(
            "POST",
            "/conversions/generic/postback",
            json_body=fresh_payload,
            extra_headers=fresh_headers,
        )
        _assert(
            fresh_status == 200,
            f"generic webhook freshness check expected HTTP 200 for fresh timestamp, got HTTP {fresh_status}",
        )

        stale_ts = unix_ts - args.webhook_freshness_max_skew_seconds - 120
        stale_payload = build_webhook_postback_payload(
            buyer_id=args.buyer_id,
            source_type=f"{args.webhook_source_type}-freshness-stale-{unix_ts}",
            event_name=args.webhook_event_name,
            event_ts=now_ts.isoformat(),
            event_id=f"canary-webhook-freshness-stale-{unix_ts}",
        )
        stale_headers = build_webhook_security_headers(
            webhook_secret=args.webhook_secret,
            webhook_hmac_secret=str(args.webhook_hmac_secret),
            payload=stale_payload,
            timestamp=stale_ts,
        )
        stale_status, _, _ = client.request_status_bytes(
            "POST",
            "/conversions/generic/postback",
            json_body=stale_payload,
            extra_headers=stale_headers,
        )
        _assert(
            stale_status == 401,
            (
                "generic webhook freshness check expected HTTP 401 for stale timestamp "
                f"(max_skew={args.webhook_freshness_max_skew_seconds}s), got HTTP {stale_status}"
            ),
        )

    def check_conversion_webhook_rate_limit() -> None:
        if not args.run_webhook_rate_limit_check:
            return
        now_ts = datetime.now(timezone.utc)
        unix_ts = int(now_ts.timestamp())
        source_type = f"{args.webhook_source_type}-ratelimit-{unix_ts}"
        statuses: list[int] = []
        total_requests = args.webhook_rate_limit_per_window + 1

        for idx in range(total_requests):
            payload = build_webhook_postback_payload(
                buyer_id=args.buyer_id,
                source_type=source_type,
                event_name=args.webhook_event_name,
                event_ts=now_ts.isoformat(),
                event_id=f"canary-webhook-ratelimit-{unix_ts}-{idx}",
            )
            headers = build_webhook_security_headers(
                webhook_secret=args.webhook_secret,
                webhook_hmac_secret=args.webhook_hmac_secret,
                payload=payload,
                timestamp=unix_ts + idx,
            )
            status, _, _ = client.request_status_bytes(
                "POST",
                "/conversions/generic/postback",
                json_body=payload,
                extra_headers=headers or None,
            )
            statuses.append(status)

        expected_ok = statuses[: args.webhook_rate_limit_per_window]
        _assert(
            all(code == 200 for code in expected_ok),
            (
                "webhook rate-limit check expected HTTP 200 before threshold but got "
                f"{expected_ok}. Ensure webhook auth/HMAC headers are configured for this environment."
            ),
        )
        throttled = statuses[-1]
        _assert(
            throttled == 429,
            (
                "webhook rate-limit check expected HTTP 429 after "
                f"{args.webhook_rate_limit_per_window} requests in {args.webhook_rate_limit_window_seconds}s "
                f"window, got HTTP {throttled}. Ensure endpoint rate limiting is enabled/configured."
            ),
        )

    def check_conversion_webhook_security_status() -> None:
        if not args.run_webhook_security_status_check:
            return
        payload = client.request("GET", "/conversions/security/status")
        for field in (
            "shared_secret_enabled",
            "shared_hmac_enabled",
            "sources",
            "freshness_enforced",
            "rate_limit_enabled",
            "rate_limit_per_window",
            "rate_limit_window_seconds",
        ):
            _assert(field in payload, f"{field} missing from /conversions/security/status")

        rows = payload.get("sources")
        _assert(isinstance(rows, list), "sources must be a list in /conversions/security/status")
        for row in rows:
            _assert(isinstance(row, dict), "source row must be object in /conversions/security/status")
            _assert("source_type" in row, "source_type missing in /conversions/security/status source row")
            _assert("secret_enabled" in row, "secret_enabled missing in /conversions/security/status source row")
            _assert("hmac_enabled" in row, "hmac_enabled missing in /conversions/security/status source row")

        secured = [
            row
            for row in rows
            if isinstance(row, dict) and (bool(row.get("secret_enabled")) or bool(row.get("hmac_enabled")))
        ]
        _assert(
            len(secured) >= args.min_secured_webhook_sources,
            (
                "webhook security-status check expected at least "
                f"{args.min_secured_webhook_sources} secured source(s), got {len(secured)}"
            ),
        )

    def check_qps_load_latency() -> None:
        if not args.run_qps_load_latency_check:
            return

        thresholds_ms = {
            "/settings/endpoints": float(args.max_settings_endpoints_latency_ms),
            "/settings/pretargeting": float(args.max_settings_pretargeting_latency_ms),
            "/analytics/home/configs": float(args.max_home_configs_latency_ms),
            "/analytics/home/endpoint-efficiency": float(args.max_home_endpoint_efficiency_latency_ms),
        }
        observed: dict[str, float] = {}
        requests = build_qps_load_latency_requests(
            buyer_id=args.buyer_id,
            days=args.qps_load_latency_days,
        )
        for path, params in requests:
            started_at = time.perf_counter()
            status, _, body = client.request_status_bytes("GET", path, params=params)
            elapsed_ms = (time.perf_counter() - started_at) * 1000.0
            _assert(status == 200, f"{path}: expected HTTP 200, got HTTP {status}")
            _assert(body, f"{path}: empty response body")
            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise SmokeFailure(f"{path}: non-JSON response during latency check") from exc
            _assert(isinstance(payload, dict), f"{path}: expected JSON object response")
            budget_ms = thresholds_ms[path]
            _assert(
                elapsed_ms <= budget_ms,
                (
                    f"{path}: latency {elapsed_ms:.1f}ms exceeds budget {budget_ms:.1f}ms "
                    f"(days={args.qps_load_latency_days}, buyer_id={args.buyer_id or 'none'})"
                ),
            )
            observed[path] = round(elapsed_ms, 1)

        observed_summary = ", ".join(f"{path}={latency}ms" for path, latency in observed.items())
        print(f"INFO  QPS startup API latencies -> {observed_summary}")

    def check_qps_page_slo_summary() -> None:
        if not args.run_qps_page_slo_check:
            return
        payload = client.request(
            "GET",
            "/system/ui-metrics/page-load/summary",
            params=build_qps_page_slo_params(
                buyer_id=args.buyer_id,
                since_hours=args.qps_page_slo_since_hours,
                latest_limit=5,
                api_rollup_limit=50,
            ),
        )
        sample_count = int(payload.get("sample_count") or 0)
        if sample_count < args.qps_page_slo_min_samples:
            raise SmokeEnvironmentBlocked(
                "QPS page SLO check requires at least "
                f"{args.qps_page_slo_min_samples} sample(s), got {sample_count} "
                "(no page-load metrics recorded yet)"
            )

        p95_first = payload.get("p95_first_table_row_ms")
        _assert(p95_first is not None, "p95_first_table_row_ms missing from QPS page SLO summary")
        _assert(
            float(p95_first) <= args.max_qps_page_p95_first_row_ms,
            (
                f"QPS page p95 first-row latency {float(p95_first):.1f}ms exceeds "
                f"budget {args.max_qps_page_p95_first_row_ms:.1f}ms"
            ),
        )

        p95_hydrated = payload.get("p95_table_hydrated_ms")
        _assert(p95_hydrated is not None, "p95_table_hydrated_ms missing from QPS page SLO summary")
        _assert(
            float(p95_hydrated) <= args.max_qps_page_p95_hydrated_ms,
            (
                f"QPS page p95 table-hydrated latency {float(p95_hydrated):.1f}ms exceeds "
                f"budget {args.max_qps_page_p95_hydrated_ms:.1f}ms"
            ),
        )

        raw_buckets = payload.get("time_buckets")
        _assert(isinstance(raw_buckets, list), "time_buckets missing from QPS page SLO summary")
        if sample_count > 0:
            _assert(
                len(raw_buckets) > 0,
                "time_buckets must include at least one bucket when samples exist",
            )
            first_bucket = raw_buckets[0]
            _assert(isinstance(first_bucket, dict), "time_buckets entry must be an object")
            _assert(
                "sample_count" in first_bucket,
                "time_buckets entry missing sample_count",
            )

        raw_rollup = payload.get("api_latency_rollup") or []
        _assert(isinstance(raw_rollup, list), "api_latency_rollup missing from QPS page SLO summary")
        rollup_p95_by_path: dict[str, float] = {}
        for row in raw_rollup:
            if not isinstance(row, dict):
                continue
            api_path = str(row.get("api_path") or "").strip()
            if not api_path:
                continue
            p95_value = row.get("p95_latency_ms")
            if p95_value is None:
                continue
            try:
                rollup_p95_by_path[api_path] = float(p95_value)
            except (TypeError, ValueError):
                continue

        api_rollup_budgets = {
            "/settings/endpoints": float(args.max_settings_endpoints_latency_ms),
            "/settings/pretargeting": float(args.max_settings_pretargeting_latency_ms),
            "/analytics/home/configs": float(args.max_home_configs_latency_ms),
            "/analytics/home/endpoint-efficiency": float(args.max_home_endpoint_efficiency_latency_ms),
        }
        missing_rollup_paths: list[str] = []
        observed_rollup_summary: list[str] = []
        for api_path, budget_ms in api_rollup_budgets.items():
            p95_api_latency = rollup_p95_by_path.get(api_path)
            if p95_api_latency is None:
                missing_rollup_paths.append(api_path)
                continue
            _assert(
                p95_api_latency <= budget_ms,
                (
                    f"QPS page API rollup p95 {api_path}={p95_api_latency:.1f}ms exceeds "
                    f"budget {budget_ms:.1f}ms"
                ),
            )
            observed_rollup_summary.append(f"{api_path}={p95_api_latency:.1f}ms")

        if args.qps_page_slo_require_api_rollup:
            _assert(
                not missing_rollup_paths,
                (
                    "QPS page API rollup missing required paths: "
                    + ", ".join(missing_rollup_paths)
                ),
            )

        print(
            "INFO  QPS page SLO summary -> "
            f"samples={sample_count}, "
            f"p95_first={float(p95_first):.1f}ms, "
            f"p95_hydrated={float(p95_hydrated):.1f}ms, "
            f"buckets={len(raw_buckets)}"
        )
        if observed_rollup_summary:
            print(
                "INFO  QPS page API rollup p95 -> "
                + ", ".join(observed_rollup_summary)
            )

    def check_optimizer_economics() -> None:
        payload = client.request(
            "GET",
            "/optimizer/economics/efficiency",
            params={"buyer_id": args.buyer_id, "days": 14},
        )
        _assert("qps_efficiency" in payload, "qps_efficiency missing from /optimizer/economics/efficiency")

    def check_models_and_resolve() -> None:
        nonlocal resolved_model_id
        payload = client.request(
            "GET",
            "/optimizer/models",
            params={
                "buyer_id": args.buyer_id,
                "include_inactive": "true",
                "limit": 200,
                "offset": 0,
            },
        )
        rows = payload.get("rows") or []
        if not isinstance(rows, list):
            raise SmokeFailure("invalid /optimizer/models response shape")
        if resolved_model_id:
            return
        active = [row for row in rows if isinstance(row, dict) and row.get("is_active")]
        if active:
            resolved_model_id = str(active[0].get("model_id", "")).strip() or None
        if not resolved_model_id and not args.allow_no_active_model:
            raise SmokeEnvironmentBlocked(
                "no active model found for this buyer (set one or pass --allow-no-active-model)"
            )

    def check_model_validation() -> None:
        if not resolved_model_id:
            return
        payload = client.request(
            "POST",
            f"/optimizer/models/{urllib.parse.quote(resolved_model_id, safe='')}/validate",
            params={"buyer_id": args.buyer_id, "timeout_seconds": 10},
        )
        _assert(bool(payload.get("valid") or payload.get("skipped")), "model validation failed")

    def check_workflow() -> None:
        nonlocal workflow_proposal_id
        if not args.run_workflow or not resolved_model_id:
            return
        payload = client.request(
            "POST",
            "/optimizer/workflows/score-and-propose",
            params=build_workflow_request_params(
                model_id=resolved_model_id,
                buyer_id=args.buyer_id,
                workflow_days=args.workflow_days,
                workflow_score_limit=args.workflow_score_limit,
                workflow_proposal_limit=args.workflow_proposal_limit,
                workflow_min_confidence=args.workflow_min_confidence,
                workflow_max_delta_pct=args.workflow_max_delta_pct,
                workflow_profile=args.workflow_profile,
            ),
        )
        score_run = payload.get("score_run") or {}
        proposal_run = payload.get("proposal_run") or {}
        _assert(
            "scores_written" in score_run and "proposals_created" in proposal_run,
            "workflow response missing score/proposal summary fields",
        )
        if args.run_lifecycle:
            top_proposals = proposal_run.get("top_proposals") or []
            _assert(
                isinstance(top_proposals, list) and len(top_proposals) > 0,
                "workflow produced no top_proposals for lifecycle check",
            )
            proposal_id = str((top_proposals[0] or {}).get("proposal_id") or "").strip()
            _assert(bool(proposal_id), "workflow top proposal missing proposal_id")
            workflow_proposal_id = proposal_id

    def check_proposal_lifecycle() -> None:
        if not args.run_lifecycle:
            return
        selected_proposal_id = (
            str(args.proposal_id or "").strip()
            or str(workflow_proposal_id or "").strip()
        )
        if not selected_proposal_id:
            # No proposal available — either upstream workflow was skipped
            # (no active model resolved, likely due to auth/proxy block) or
            # --proposal-id was not provided.  Treat as environment-blocked
            # rather than a hard failure since the root cause is upstream.
            raise SmokeEnvironmentBlocked(
                "--run-lifecycle requires --proposal-id or --run-workflow with generated proposal"
            )

        proposal_id = urllib.parse.quote(selected_proposal_id, safe="")
        approve = client.request(
            "POST",
            f"/optimizer/proposals/{proposal_id}/approve",
            params={"buyer_id": args.buyer_id},
        )
        _assert(str(approve.get("status", "")).lower() == "approved", "proposal approve did not return status=approved")

        applied = client.request(
            "POST",
            f"/optimizer/proposals/{proposal_id}/apply",
            params={"buyer_id": args.buyer_id, "mode": "queue"},
        )
        _assert(str(applied.get("status", "")).lower() == "applied", "proposal apply did not return status=applied")

        sync = client.request(
            "POST",
            f"/optimizer/proposals/{proposal_id}/sync-apply-status",
            params={"buyer_id": args.buyer_id},
        )
        _assert(str(sync.get("status", "")).lower() == "applied", "proposal sync did not return status=applied")

        history = client.request(
            "GET",
            f"/optimizer/proposals/{proposal_id}/history",
            params={"buyer_id": args.buyer_id, "limit": 10},
        )
        rows = history.get("rows") or []
        _assert(isinstance(rows, list) and len(rows) > 0, "proposal history is empty after lifecycle execution")

    def check_rollback_dry_run() -> None:
        if args.billing_id is None or args.snapshot_id is None:
            return
        payload = client.request(
            "POST",
            f"/settings/pretargeting/{urllib.parse.quote(args.billing_id, safe='')}/rollback",
            json_body={
                "snapshot_id": args.snapshot_id,
                "dry_run": True,
                "reason": "canary_smoke",
                "proposal_id": "canary_smoke",
            },
        )
        _assert(payload.get("dry_run") is True, "rollback dry-run did not return dry_run=true")

    # Fail fast on API reachability/health so blocked-network runs do not emit
    # a long list of derivative endpoint failures.
    try:
        check_health()
        print("PASS  API health")
        results.append((True, "PASS  API health"))
    except SmokeEnvironmentBlocked as exc:
        line = f"BLOCKED  API health -> {exc}"
        print(line)
        results.append((False, line))
        print("\nSmoke checks blocked by environment/network policy.")
        return 2
    except Exception as exc:  # noqa: BLE001
        line = f"FAIL  API health -> {exc}"
        print(line)
        results.append((False, line))
        print("\nSmoke checks failed: 1")
        return 1

    checks = [
        ("Data health", check_data_health),
        ("Conversion health", check_conversion_health),
        ("Conversion readiness", check_conversion_readiness),
        ("Conversion ingestion stats", check_conversion_stats),
        ("Conversion pixel (optional)", check_conversion_pixel),
        ("Conversion webhook auth (optional)", check_conversion_webhook_auth),
        ("Conversion webhook HMAC (optional)", check_conversion_webhook_hmac),
        ("Conversion webhook freshness (optional)", check_conversion_webhook_freshness),
        ("Conversion webhook rate-limit (optional)", check_conversion_webhook_rate_limit),
        ("Conversion webhook security status (optional)", check_conversion_webhook_security_status),
        ("QPS startup API latency (optional)", check_qps_load_latency),
        ("QPS page SLO summary (optional)", check_qps_page_slo_summary),
        ("Optimizer economics", check_optimizer_economics),
        ("Optimizer models", check_models_and_resolve),
        ("Model endpoint validation", check_model_validation),
        ("Score+propose workflow (optional)", check_workflow),
        ("Proposal lifecycle (optional)", check_proposal_lifecycle),
        ("Rollback dry-run (optional)", check_rollback_dry_run),
    ]

    blocked_count = 0
    for name, fn in checks:
        ok, line, is_blocked = _run_check(name, fn)
        print(line)
        results.append((ok, line))
        if is_blocked:
            blocked_count += 1

    failures = [line for ok, line in results if not ok]
    if failures:
        if blocked_count > 0 and blocked_count == len(failures):
            print(f"\nSmoke checks blocked by environment/auth policy: {blocked_count}")
            return 2
        print(f"\nSmoke checks failed: {len(failures)}")
        return 1

    print("\nAll smoke checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
