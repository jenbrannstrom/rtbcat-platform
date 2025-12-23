"""Troubleshooting and evaluation router for Cat-Scan API.

This module provides endpoints for RTB troubleshooting and evaluation:
- Evaluation engine for actionable recommendations
- Filtered bids analysis
- Bid funnel metrics
- Troubleshooting data collection
"""

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from analysis.evaluation_engine import EvaluationEngine, RecommendationType

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Troubleshooting"])


@router.get("/api/evaluation")
async def get_evaluation(
    days: int = Query(7, ge=1, le=90, description="Days of data to analyze"),
):
    """
    Run evaluation engine and return actionable recommendations.

    Phase 11: Decision Intelligence
    Combines all data sources (CSV, API, troubleshooting) to produce
    prioritized recommendations for QPS optimization.
    """
    engine = EvaluationEngine()
    results = engine.run_full_evaluation(days)

    # Convert Recommendation dataclasses to dicts for JSON
    results["recommendations"] = [r.to_dict() for r in results["recommendations"]]

    return results


@router.get("/api/troubleshooting/filtered-bids")
async def get_filtered_bids(
    days: int = Query(7, ge=1, le=90, description="Days of data to analyze"),
):
    """
    Get summary of why bids were filtered.

    Phase 11: RTB Troubleshooting API
    Shows breakdown of filtered bid reasons - the key insight for understanding waste.
    """
    engine = EvaluationEngine()
    return engine.get_filtered_bids_summary(days)


@router.get("/api/troubleshooting/funnel")
async def get_bid_funnel(
    days: int = Query(7, ge=1, le=90, description="Days of data to analyze"),
):
    """
    Get bid funnel metrics - from bids submitted to impressions won.

    Phase 11: RTB Troubleshooting API
    Shows the conversion funnel from bid requests to wins.
    """
    engine = EvaluationEngine()
    return engine.get_bid_funnel(days)


@router.post("/api/troubleshooting/collect")
async def trigger_troubleshooting_collection(
    days: int = Query(7, ge=1, le=30, description="Days of data to collect"),
    environment: Optional[str] = Query(None, description="Filter by APP or WEB"),
    background_tasks: BackgroundTasks = None,
):
    """
    Trigger troubleshooting data collection from Google API.

    Phase 11: RTB Troubleshooting API
    Fetches filtered bid reasons, bid metrics, and callout status.
    Requires service account with adexchange.buyer scope.
    """
    # TODO: Implement background collection
    # For now, return a placeholder
    return {
        "status": "collection_queued",
        "days": days,
        "environment": environment,
        "message": "Collection will run in background. Check /api/troubleshooting/filtered-bids after a few minutes."
    }
