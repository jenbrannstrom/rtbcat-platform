"""RBAC closure audit tests.

Verifies that endpoints patched in the security/rbac-closure branch
correctly enforce authentication and authorization dependencies.
"""

from __future__ import annotations

import inspect
from typing import get_type_hints

import pytest

pytest.importorskip("fastapi")
from fastapi import Depends

from api.dependencies import get_current_user, require_admin, require_seat_admin_or_sudo
from services.auth_service import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_dependency_functions(endpoint_func) -> list:
    """Extract FastAPI Depends() callables from an endpoint's signature."""
    sig = inspect.signature(endpoint_func)
    deps = []
    for param in sig.parameters.values():
        if param.default is not inspect.Parameter.empty and isinstance(param.default, type(Depends())):
            deps.append(param.default.dependency)
    return deps


def _assert_has_dependency(endpoint_func, expected_dep, endpoint_name: str):
    """Assert that an endpoint has the expected dependency."""
    deps = _get_dependency_functions(endpoint_func)
    assert expected_dep in deps, (
        f"{endpoint_name} missing Depends({expected_dep.__name__}); "
        f"found: {[d.__name__ for d in deps if hasattr(d, '__name__')]}"
    )


# ---------------------------------------------------------------------------
# conversions.py – mutation endpoints require require_seat_admin_or_sudo
# ---------------------------------------------------------------------------

class TestConversionsRBACClosure:
    """Verify mutation endpoints in conversions.py require admin access."""

    @pytest.fixture(autouse=True)
    def _import_router(self):
        from api.routers.conversions import (
            replay_conversion_ingestion_failure,
            discard_conversion_ingestion_failure,
            refresh_conversion_aggregates,
            refresh_conversion_attribution_joins,
        )
        self.replay = replay_conversion_ingestion_failure
        self.discard = discard_conversion_ingestion_failure
        self.refresh_agg = refresh_conversion_aggregates
        self.refresh_attr = refresh_conversion_attribution_joins

    def test_replay_failure_requires_seat_admin(self):
        _assert_has_dependency(
            self.replay, require_seat_admin_or_sudo,
            "POST /conversions/ingestion/failures/{id}/replay",
        )

    def test_discard_failure_requires_seat_admin(self):
        _assert_has_dependency(
            self.discard, require_seat_admin_or_sudo,
            "POST /conversions/ingestion/failures/{id}/discard",
        )

    def test_refresh_aggregates_requires_seat_admin(self):
        _assert_has_dependency(
            self.refresh_agg, require_seat_admin_or_sudo,
            "POST /conversions/aggregates/refresh",
        )

    def test_refresh_attribution_requires_seat_admin(self):
        _assert_has_dependency(
            self.refresh_attr, require_seat_admin_or_sudo,
            "POST /conversions/attribution/refresh",
        )


# ---------------------------------------------------------------------------
# troubleshooting.py – read endpoints require get_current_user
# ---------------------------------------------------------------------------

class TestTroubleshootingRBACClosure:
    """Verify troubleshooting read endpoints require authentication."""

    @pytest.fixture(autouse=True)
    def _import_router(self):
        from api.routers.troubleshooting import (
            get_evaluation,
            get_filtered_bids,
            get_bid_funnel,
        )
        self.get_evaluation = get_evaluation
        self.get_filtered_bids = get_filtered_bids
        self.get_bid_funnel = get_bid_funnel

    def test_evaluation_requires_auth(self):
        _assert_has_dependency(
            self.get_evaluation, get_current_user,
            "GET /api/evaluation",
        )

    def test_filtered_bids_requires_auth(self):
        _assert_has_dependency(
            self.get_filtered_bids, get_current_user,
            "GET /api/troubleshooting/filtered-bids",
        )

    def test_bid_funnel_requires_auth(self):
        _assert_has_dependency(
            self.get_bid_funnel, get_current_user,
            "GET /api/troubleshooting/funnel",
        )


# ---------------------------------------------------------------------------
# qps.py – all endpoints require get_current_user
# ---------------------------------------------------------------------------

class TestQpsRBACClosure:
    """Verify QPS endpoints require authentication."""

    @pytest.fixture(autouse=True)
    def _import_router(self):
        from api.routers.qps import (
            get_qps_summary,
            get_size_coverage_report,
            get_config_performance_report,
            get_fraud_signals_report,
            get_full_qps_report,
            get_include_list,
        )
        self.endpoints = {
            "GET /qps/summary": get_qps_summary,
            "GET /qps/size-coverage": get_size_coverage_report,
            "GET /qps/config-performance": get_config_performance_report,
            "GET /qps/fraud-signals": get_fraud_signals_report,
            "GET /qps/report": get_full_qps_report,
            "GET /qps/include-list": get_include_list,
        }

    @pytest.mark.parametrize("endpoint_name", [
        "GET /qps/summary",
        "GET /qps/size-coverage",
        "GET /qps/config-performance",
        "GET /qps/fraud-signals",
        "GET /qps/report",
        "GET /qps/include-list",
    ])
    def test_qps_endpoint_requires_auth(self, endpoint_name):
        _assert_has_dependency(
            self.endpoints[endpoint_name], get_current_user, endpoint_name,
        )


# ---------------------------------------------------------------------------
# system.py – sensitive endpoints require auth
# ---------------------------------------------------------------------------

class TestSystemRBACClosure:
    """Verify system endpoints require authentication."""

    @pytest.fixture(autouse=True)
    def _import_router(self):
        from api.routers.system import (
            get_thumbnail_failure_metrics,
            get_system_status,
            get_system_secrets_health,
            search_geo_targets,
            lookup_geo_names,
            get_stats,
            get_sizes,
        )
        self.failure_metrics = get_thumbnail_failure_metrics
        self.system_status = get_system_status
        self.secrets_health = get_system_secrets_health
        self.geo_search = search_geo_targets
        self.geo_lookup = lookup_geo_names
        self.stats = get_stats
        self.sizes = get_sizes

    def test_thumbnail_failure_metrics_requires_auth(self):
        _assert_has_dependency(
            self.failure_metrics, get_current_user,
            "GET /thumbnails/failure-metrics",
        )

    def test_system_status_requires_auth(self):
        _assert_has_dependency(
            self.system_status, get_current_user,
            "GET /system/status",
        )

    def test_secrets_health_requires_admin(self):
        _assert_has_dependency(
            self.secrets_health, require_admin,
            "GET /system/secrets-health",
        )

    def test_geo_search_requires_auth(self):
        _assert_has_dependency(
            self.geo_search, get_current_user,
            "GET /geos/search",
        )

    def test_geo_lookup_requires_auth(self):
        _assert_has_dependency(
            self.geo_lookup, get_current_user,
            "GET /geos/lookup",
        )

    def test_stats_requires_auth(self):
        _assert_has_dependency(
            self.stats, get_current_user,
            "GET /stats",
        )

    def test_sizes_requires_auth(self):
        _assert_has_dependency(
            self.sizes, get_current_user,
            "GET /sizes",
        )


# ---------------------------------------------------------------------------
# gmail.py – status endpoint requires auth
# ---------------------------------------------------------------------------

class TestGmailRBACClosure:

    def test_gmail_status_requires_auth(self):
        from api.routers.gmail import get_gmail_status
        _assert_has_dependency(
            get_gmail_status, get_current_user,
            "GET /gmail/status",
        )


# ---------------------------------------------------------------------------
# retention.py – config endpoint requires auth
# ---------------------------------------------------------------------------

class TestRetentionRBACClosure:

    def test_retention_config_requires_auth(self):
        from api.routers.retention import get_retention_config
        _assert_has_dependency(
            get_retention_config, get_current_user,
            "GET /retention/config",
        )


# ---------------------------------------------------------------------------
# settings/ – read endpoints require auth
# ---------------------------------------------------------------------------

class TestSettingsRBACClosure:
    """Verify settings read endpoints require authentication."""

    def test_pending_changes_requires_auth(self):
        from api.routers.settings.changes import list_pending_changes
        _assert_has_dependency(
            list_pending_changes, get_current_user,
            "GET /settings/pretargeting/pending-changes",
        )

    def test_snapshots_list_requires_auth(self):
        from api.routers.settings.snapshots import list_pretargeting_snapshots
        _assert_has_dependency(
            list_pretargeting_snapshots, get_current_user,
            "GET /settings/pretargeting/snapshots",
        )

    def test_comparisons_list_requires_auth(self):
        from api.routers.settings.snapshots import list_comparisons
        _assert_has_dependency(
            list_comparisons, get_current_user,
            "GET /settings/pretargeting/comparisons",
        )

    def test_endpoints_list_requires_auth(self):
        from api.routers.settings.endpoints import get_rtb_endpoints
        _assert_has_dependency(
            get_rtb_endpoints, get_current_user,
            "GET /settings/endpoints",
        )

    def test_pretargeting_configs_requires_auth(self):
        from api.routers.settings.pretargeting import get_pretargeting_configs
        _assert_has_dependency(
            get_pretargeting_configs, get_current_user,
            "GET /settings/pretargeting",
        )

    def test_pretargeting_history_requires_auth(self):
        from api.routers.settings.pretargeting import get_pretargeting_history
        _assert_has_dependency(
            get_pretargeting_history, get_current_user,
            "GET /settings/pretargeting/history",
        )

    def test_pretargeting_publishers_requires_auth(self):
        from api.routers.settings.pretargeting import get_pretargeting_publishers
        _assert_has_dependency(
            get_pretargeting_publishers, get_current_user,
            "GET /settings/pretargeting/{billing_id}/publishers",
        )

    def test_pending_publisher_changes_requires_auth(self):
        from api.routers.settings.pretargeting import get_pending_publisher_changes
        _assert_has_dependency(
            get_pending_publisher_changes, get_current_user,
            "GET /settings/pretargeting/{billing_id}/publishers/pending",
        )

    def test_optimizer_setup_requires_auth(self):
        from api.routers.settings.optimizer import get_optimizer_setup
        _assert_has_dependency(
            get_optimizer_setup, get_current_user,
            "GET /settings/optimizer/setup",
        )
