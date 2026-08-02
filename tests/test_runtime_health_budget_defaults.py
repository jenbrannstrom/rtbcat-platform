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
    """The 12000ms budget must stay explicit in whichever workflow carries it.

    This guarded v1-runtime-health-strict.yml, deleted in f00dcc27 with the
    other stale v1-* pilot workflows; the budget moved to live-major-smoke.yml
    and the assertion was left pointing at the removed file.
    """
    content = Path(".github/workflows/live-major-smoke.yml").read_text(
        encoding="utf-8"
    )
    assert "CATSCAN_CANARY_MAX_HOME_ENDPOINT_EFFICIENCY_LATENCY_MS" in content
    assert "CATSCAN_RUNTIME_HEALTH_MAX_HOME_ENDPOINT_EFFICIENCY_LATENCY_MS || '12000'" in content
