#!/usr/bin/env python3
"""v1 canary smoke checks for core Cat-Scan API flows."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any


class SmokeFailure(RuntimeError):
    """Raised when a smoke check fails."""


def _join_url(base_url: str, path: str) -> str:
    base = base_url.rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    return f"{base}{suffix}"


class SmokeClient:
    def __init__(self, *, base_url: str, token: str | None, cookie: str | None, timeout: float):
        self.base_url = base_url
        self.timeout = timeout
        self.default_headers: dict[str, str] = {}
        if token:
            self.default_headers["Authorization"] = f"Bearer {token}"
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
            raise SmokeFailure(f"{method} {path}: {exc}") from exc


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise SmokeFailure(message)


def _run_check(name: str, fn) -> tuple[bool, str]:
    try:
        fn()
        return True, f"PASS  {name}"
    except Exception as exc:  # noqa: BLE001
        return False, f"FAIL  {name} -> {exc}"


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
        payload = build_webhook_postback_payload(
            buyer_id=args.buyer_id,
            source_type=args.webhook_source_type,
            event_name=args.webhook_event_name,
            event_ts=now_ts.isoformat(),
            event_id=f"canary-webhook-{int(now_ts.timestamp())}",
        )
        status_without_secret, _, _ = client.request_status_bytes(
            "POST",
            "/conversions/generic/postback",
            json_body=payload,
        )
        if args.webhook_secret:
            _assert(
                status_without_secret == 401,
                (
                    "generic webhook auth check expected HTTP 401 without secret when "
                    f"secret is configured, got HTTP {status_without_secret}"
                ),
            )
            status_with_secret, _, _ = client.request_status_bytes(
                "POST",
                "/conversions/generic/postback",
                json_body=payload,
                extra_headers={"X-Webhook-Secret": args.webhook_secret},
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
            source_type=args.webhook_source_type,
            event_name=args.webhook_event_name,
            event_ts=now_ts.isoformat(),
            event_id=f"canary-webhook-hmac-{unix_ts}",
        )
        valid_signature = build_webhook_hmac_signature(
            secret=str(args.webhook_hmac_secret),
            payload=payload,
            timestamp=unix_ts,
        )
        base_headers = {
            "X-Webhook-Timestamp": str(unix_ts),
            "X-Signature": f"sha256={valid_signature}",
        }
        if args.webhook_secret:
            base_headers["X-Webhook-Secret"] = str(args.webhook_secret)
        valid_status, _, _ = client.request_status_bytes(
            "POST",
            "/conversions/generic/postback",
            json_body=payload,
            extra_headers=base_headers,
        )
        _assert(
            valid_status == 200,
            f"generic webhook HMAC check expected HTTP 200 with valid signature, got HTTP {valid_status}",
        )

        invalid_headers = dict(base_headers)
        invalid_headers["X-Signature"] = "sha256=invalid-signature"
        invalid_status, _, _ = client.request_status_bytes(
            "POST",
            "/conversions/generic/postback",
            json_body=payload,
            extra_headers=invalid_headers,
        )
        _assert(
            invalid_status == 401,
            f"generic webhook HMAC check expected HTTP 401 with invalid signature, got HTTP {invalid_status}",
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
            raise SmokeFailure("no active model found; set one or pass --allow-no-active-model")

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
        _assert(
            bool(selected_proposal_id),
            "--run-lifecycle requires --proposal-id or --run-workflow with generated proposal",
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

    checks = [
        ("API health", check_health),
        ("Data health", check_data_health),
        ("Conversion health", check_conversion_health),
        ("Conversion readiness", check_conversion_readiness),
        ("Conversion ingestion stats", check_conversion_stats),
        ("Conversion pixel (optional)", check_conversion_pixel),
        ("Conversion webhook auth (optional)", check_conversion_webhook_auth),
        ("Conversion webhook HMAC (optional)", check_conversion_webhook_hmac),
        ("Optimizer economics", check_optimizer_economics),
        ("Optimizer models", check_models_and_resolve),
        ("Model endpoint validation", check_model_validation),
        ("Score+propose workflow (optional)", check_workflow),
        ("Proposal lifecycle (optional)", check_proposal_lifecycle),
        ("Rollback dry-run (optional)", check_rollback_dry_run),
    ]

    for name, fn in checks:
        ok, line = _run_check(name, fn)
        print(line)
        results.append((ok, line))

    failures = [line for ok, line in results if not ok]
    if failures:
        print(f"\nSmoke checks failed: {len(failures)}")
        return 1

    print("\nAll smoke checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
