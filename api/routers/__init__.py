"""Lazy exports for router objects used by ``api.main``.

Importing every router eagerly makes unrelated imports pay for optional
dependencies. Keep submodule imports lazy so tests can import one router
without dragging in the whole package graph.
"""

from __future__ import annotations

from importlib import import_module


_ROUTER_EXPORTS = {
    "system_router": ("api.routers.system", "router"),
    "creatives_router": ("api.routers.creatives", "router"),
    "creatives_live_router": ("api.routers.creatives_live", "router"),
    "creative_cache_router": ("api.routers.creative_cache", "router"),
    "creative_language_router": ("api.routers.creative_language", "router"),
    "creative_geo_linguistic_router": ("api.routers.creative_geo_linguistic", "router"),
    "seats_router": ("api.routers.seats", "router"),
    "settings_router": ("api.routers.settings", "router"),
    "uploads_router": ("api.routers.uploads", "router"),
    "config_router": ("api.routers.config", "router"),
    "gmail_router": ("api.routers.gmail", "router"),
    "recommendations_router": ("api.routers.recommendations", "router"),
    "retention_router": ("api.routers.retention", "router"),
    "precompute_router": ("api.routers.precompute", "router"),
    "performance_router": ("api.routers.performance", "router"),
    "troubleshooting_router": ("api.routers.troubleshooting", "router"),
    "collect_router": ("api.routers.collect", "router"),
    "conversions_router": ("api.routers.conversions", "router"),
    "optimizer_models_router": ("api.routers.optimizer_models", "router"),
    "optimizer_scoring_router": ("api.routers.optimizer_scoring", "router"),
    "optimizer_proposals_router": ("api.routers.optimizer_proposals", "router"),
    "optimizer_economics_router": ("api.routers.optimizer_economics", "router"),
    "optimizer_workflows_router": ("api.routers.optimizer_workflows", "router"),
    "admin_router": ("api.routers.admin", "router"),
    "seat_admin_router": ("api.routers.seat_admin", "router"),
    "waste_router": ("api.routers.analytics.waste", "router"),
    "rtb_bidstream_router": ("api.routers.analytics.rtb_bidstream", "router"),
    "analytics_qps_router": ("api.routers.analytics.qps", "router"),
    "traffic_router": ("api.routers.analytics.traffic", "router"),
    "spend_router": ("api.routers.analytics.spend", "router"),
    "home_router": ("api.routers.analytics.home", "router"),
}

__all__ = list(_ROUTER_EXPORTS)


def __getattr__(name: str):
    if name not in _ROUTER_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = _ROUTER_EXPORTS[name]
    module = import_module(module_name)
    value = getattr(module, attribute_name)
    globals()[name] = value
    return value
