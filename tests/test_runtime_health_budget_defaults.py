"""Regression guard for runtime-health endpoint-efficiency latency budgets."""

from __future__ import annotations

from pathlib import Path


def test_runtime_health_local_default_budget_is_12000() -> None:
    content = Path("scripts/run_v1_runtime_health_local.sh").read_text(encoding="utf-8")
    expected = (
        "CATSCAN_CANARY_MAX_HOME_ENDPOINT_EFFICIENCY_LATENCY_MS="
        "\\${CATSCAN_CANARY_MAX_HOME_ENDPOINT_EFFICIENCY_LATENCY_MS:-12000}"
    )
    assert content.count(expected) >= 2
    assert ":-30000" not in content


def test_runtime_health_workflow_sets_explicit_12000_budget_default() -> None:
    content = Path(".github/workflows/v1-runtime-health-strict.yml").read_text(
        encoding="utf-8"
    )
    assert "CATSCAN_CANARY_MAX_HOME_ENDPOINT_EFFICIENCY_LATENCY_MS" in content
    assert "CATSCAN_RUNTIME_HEALTH_MAX_HOME_ENDPOINT_EFFICIENCY_LATENCY_MS || '12000'" in content
