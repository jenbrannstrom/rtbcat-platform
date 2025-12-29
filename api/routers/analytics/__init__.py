"""Analytics Routers Package.

Refactored from the monolithic analytics.py into logical sub-routers:
- waste: Waste signal analysis, problem formats, fraud risk, viewability
- rtb_funnel: RTB funnel analysis, publisher/geo breakdowns, app drilldowns
- qps: QPS optimization, size coverage, geo waste, pretargeting recommendations
- traffic: Traffic import and mock data generation
- spend: Spend statistics
"""

from .waste import router as waste_router
from .rtb_funnel import router as rtb_funnel_router
from .qps import router as qps_router
from .traffic import router as traffic_router
from .spend import router as spend_router

__all__ = [
    "waste_router",
    "rtb_funnel_router",
    "qps_router",
    "traffic_router",
    "spend_router",
]
