# Phase 11: RTB Troubleshooting API Integration

**Objective:** Integrate Google's Ad Exchange Buyer II API to capture bid rejection reasons, filtered bid metrics, and callout data - completing the data picture needed for actionable QPS optimization.

---

## Current Schema Reality

Before adding anything, acknowledge what exists:

```
ACTIVE TABLES (in use):
├── performance_data      -- CSV imports, 1M+ rows/day, THE source of truth
├── creatives             -- API sync, ~650 rows
├── fraud_signals         -- Detected patterns
├── import_history        -- Tracking
├── apps, publishers, geographies  -- Dimension lookups
└── thumbnail_status      -- Video thumbnail tracking

LEGACY/UNCLEAR (needs cleanup later):
├── performance_metrics   -- Overlaps with performance_data
├── campaigns vs ai_campaigns  -- Two campaign systems
├── campaign_creatives vs creative_campaigns  -- Two junction tables
├── daily_creative_summary  -- Pre-aggregated, unclear if populated
└── rtb_traffic          -- Size tracking, may be redundant with performance_data
```

**Principle:** Don't add complexity. Troubleshooting API data is LOW VOLUME (~100-200 rows/day aggregate data). Store raw, parse at query time, optimize later when we know patterns.

---

## Why This Matters

**Current State (CSV Performance Data):**
```
You sent 1M bid requests → Won 50K impressions → Spent $500
```

**Missing Insight (Troubleshooting API):**
```
You sent 1M bid requests:
├── 400K filtered: "Creative not approved for this inventory"
├── 200K filtered: "Bid below floor price"
├── 150K filtered: "Size mismatch"
├── 100K filtered: "Publisher blocked your buyer"
├── 50K won
└── 100K lost in auction (outbid)
```

**With both data sources combined:** Cat-Scan can tell you EXACTLY what pretargeting changes will reduce waste.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA SOURCES                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  [CSV Performance Data]      [RTB Troubleshooting API]     [Creatives API]  │
│  ├─ reached_queries          ├─ filtered_bids              ├─ approval status│
│  ├─ impressions              ├─ filter_reasons             ├─ format/size    │
│  ├─ clicks/spend             ├─ callout_metrics            ├─ destination    │
│  └─ country/publisher/app    └─ bid_metrics                └─ buyer_id       │
│                                                                              │
│                              ↓                                               │
│                    ┌─────────────────────┐                                   │
│                    │  EVALUATION ENGINE  │                                   │
│                    │  (New Component)    │                                   │
│                    └─────────────────────┘                                   │
│                              ↓                                               │
│         ┌────────────────────┴────────────────────┐                          │
│         ↓                                         ↓                          │
│  ┌──────────────────┐                   ┌──────────────────┐                 │
│  │ PRETARGETING     │                   │ ADOPS ADVICE     │                 │
│  │ RECOMMENDATIONS  │                   │ (Human Review)   │                 │
│  │                  │                   │                  │                 │
│  │ • Add size X     │                   │ • Creative 123   │                 │
│  │ • Exclude geo Y  │                   │   size 251x300   │                 │
│  │ • Block pub Z    │                   │   never bid on   │                 │
│  └──────────────────┘                   └──────────────────┘                 │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Part 1: Troubleshooting API Client

**New File:** `creative-intelligence/collectors/troubleshooting/client.py`

### 1.1 API Overview

The Ad Exchange Buyer II API provides three key metric types:

| Metric Type | What It Tells You | Key Fields |
|-------------|-------------------|------------|
| **Bid Metrics** | Volume and success rates | impressions, bids, wins |
| **Filtered Bid Reasons** | WHY bids were rejected | creative disapproval, floor price, blocked, etc. |
| **Callout Status** | How requests reached bidder | sent, received, successful |

### 1.2 Required Scope

```python
# Additional scope needed (add to existing auth)
TROUBLESHOOTING_SCOPE = 'https://www.googleapis.com/auth/adexchange.buyer'

# Existing scope
RTB_SCOPE = 'https://www.googleapis.com/auth/realtime-bidding'

# Combined scopes for credentials
ALL_SCOPES = [RTB_SCOPE, TROUBLESHOOTING_SCOPE]
```

### 1.3 Client Implementation

```python
"""
RTB Troubleshooting API Client

Uses Ad Exchange Buyer II API (v2beta1) to fetch:
- Filtered bid reasons
- Bid metrics
- Callout status metrics
"""

from googleapiclient.discovery import build
from google.oauth2 import service_account
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class TroubleshootingClient:
    """
    Client for Google Ad Exchange Buyer II API troubleshooting endpoints.
    
    Filter Sets are required containers for querying metrics.
    We create one filter set per query configuration.
    """
    
    def __init__(self, credentials_path: str, bidder_id: str):
        """
        Initialize the troubleshooting client.
        
        Args:
            credentials_path: Path to service account JSON
            bidder_id: Your bidder account ID (e.g., "299038253")
        """
        self.bidder_id = bidder_id
        
        # Load credentials with required scope
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/adexchange.buyer']
        )
        
        # Build the service client
        self.service = build(
            'adexchangebuyer2',
            'v2beta1',
            credentials=credentials,
            cache_discovery=False
        )
        
        # Parent path for API calls
        self.parent = f"bidders/{self.bidder_id}"
    
    def create_filter_set(
        self,
        name: str,
        environment: str = None,       # "APP" or "WEB"
        platforms: List[str] = None,   # ["DESKTOP", "MOBILE", "TABLET"]
        formats: List[str] = None,     # ["NATIVE_DISPLAY", "NATIVE_VIDEO", "NON_NATIVE_DISPLAY", "NON_NATIVE_VIDEO"]
        time_series_granularity: str = "DAILY",
        relative_date_range: Dict = None,  # {"offsetDays": 1, "durationDays": 7}
        absolute_date_range: Dict = None,  # {"startDate": {...}, "endDate": {...}}
        is_transient: bool = True
    ) -> Dict:
        """
        Create a filter set for querying troubleshooting metrics.
        
        Filter sets define the dimensions for metric queries.
        Transient filter sets are not persisted (use for ad-hoc queries).
        
        Args:
            name: Unique identifier for this filter set
            environment: Filter by APP or WEB
            platforms: Filter by device types
            formats: Filter by creative formats
            time_series_granularity: HOURLY or DAILY
            relative_date_range: Relative date range (preferred)
            absolute_date_range: Absolute date range
            is_transient: If True, filter set is not saved server-side
            
        Returns:
            Created filter set object
        """
        filter_set = {
            "name": f"{self.parent}/filterSets/{name}",
            "timeSeriesGranularity": time_series_granularity,
        }
        
        # Add optional filters
        if environment:
            filter_set["environment"] = environment
        if platforms:
            filter_set["platforms"] = platforms
        if formats:
            filter_set["formats"] = formats
            
        # Date range (one of these required)
        if relative_date_range:
            filter_set["relativeDateRange"] = relative_date_range
        elif absolute_date_range:
            filter_set["absoluteDateRange"] = absolute_date_range
        else:
            # Default: last 7 days
            filter_set["relativeDateRange"] = {
                "offsetDays": 1,  # Start from yesterday (today incomplete)
                "durationDays": 7
            }
        
        try:
            result = self.service.bidders().filterSets().create(
                ownerName=self.parent,
                isTransient=is_transient,
                body=filter_set
            ).execute()
            
            logger.info(f"Created filter set: {result.get('name')}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to create filter set: {e}")
            raise
    
    def get_filtered_bid_requests(self, filter_set_name: str) -> List[Dict]:
        """
        Get filtered bid request metrics - shows WHY bids were filtered.
        
        This is the GOLD for understanding QPS waste.
        
        Returns list of:
        {
            "calloutStatusId": 1,  # Lookup in callout-status-codes
            "impressions": {"value": "12345"},
            "bids": {"value": "10000"},
            ...
        }
        
        Key status codes to watch:
        - 1: Successful response
        - 2: No bid
        - 6: Timeout
        - 7: Bad request
        """
        try:
            results = []
            request = self.service.bidders().filterSets().filteredBidRequests().list(
                filterSetName=filter_set_name
            )
            
            while request is not None:
                response = request.execute()
                results.extend(response.get('calloutStatusRows', []))
                request = self.service.bidders().filterSets().filteredBidRequests().list_next(
                    request, response
                )
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get filtered bid requests: {e}")
            raise
    
    def get_filtered_bids(self, filter_set_name: str) -> List[Dict]:
        """
        Get filtered bids - bids that were submitted but rejected.
        
        Returns breakdown by creative status:
        - CREATIVE_NOT_APPROVED
        - CREATIVE_NOT_SUBMITTED
        - BID_BELOW_FLOOR
        - CREATIVE_DISAPPROVED
        - etc.
        """
        try:
            results = []
            request = self.service.bidders().filterSets().filteredBids().list(
                filterSetName=filter_set_name
            )
            
            while request is not None:
                response = request.execute()
                results.extend(response.get('creativeStatusRows', []))
                request = self.service.bidders().filterSets().filteredBids().list_next(
                    request, response
                )
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get filtered bids: {e}")
            raise
    
    def get_bid_metrics(self, filter_set_name: str) -> List[Dict]:
        """
        Get overall bid metrics - the funnel from requests to wins.
        
        Returns:
        {
            "bids": {"value": "1000000"},
            "bidsInAuction": {"value": "500000"},
            "impressionsWon": {"value": "50000"},
            "billedImpressions": {"value": "48000"},
            "measurableImpressions": {"value": "45000"},
            "viewableImpressions": {"value": "30000"}
        }
        """
        try:
            results = []
            request = self.service.bidders().filterSets().bidMetrics().list(
                filterSetName=filter_set_name
            )
            
            while request is not None:
                response = request.execute()
                results.extend(response.get('bidMetricsRows', []))
                request = self.service.bidders().filterSets().bidMetrics().list_next(
                    request, response
                )
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get bid metrics: {e}")
            raise
    
    def get_impression_metrics(self, filter_set_name: str) -> List[Dict]:
        """
        Get impression-level metrics.
        
        Returns breakdown by inventory type, ad position, etc.
        """
        try:
            results = []
            request = self.service.bidders().filterSets().impressionMetrics().list(
                filterSetName=filter_set_name
            )
            
            while request is not None:
                response = request.execute()
                results.extend(response.get('impressionMetricsRows', []))
                request = self.service.bidders().filterSets().impressionMetrics().list_next(
                    request, response
                )
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get impression metrics: {e}")
            raise
    
    def get_loser_bids(self, filter_set_name: str) -> List[Dict]:
        """
        Get details on bids that lost in auction.
        
        Useful for understanding if you're being outbid.
        """
        try:
            results = []
            request = self.service.bidders().filterSets().losingBids().list(
                filterSetName=filter_set_name
            )
            
            while request is not None:
                response = request.execute()
                results.extend(response.get('creativeStatusRows', []))
                request = self.service.bidders().filterSets().losingBids().list_next(
                    request, response
                )
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to get loser bids: {e}")
            raise
    
    def collect_all_metrics(
        self,
        days: int = 7,
        environment: str = None,
        granularity: str = "DAILY"
    ) -> Dict[str, Any]:
        """
        Convenience method to collect all troubleshooting metrics.
        
        Args:
            days: Number of days to look back
            environment: Optional filter for APP or WEB
            granularity: DAILY or HOURLY
            
        Returns:
            Dictionary with all metric types
        """
        # Create a transient filter set
        filter_set_name = f"catscan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        filter_set = self.create_filter_set(
            name=filter_set_name,
            environment=environment,
            time_series_granularity=granularity,
            relative_date_range={
                "offsetDays": 1,
                "durationDays": days
            },
            is_transient=True
        )
        
        full_name = filter_set["name"]
        
        return {
            "filter_set": filter_set,
            "filtered_bid_requests": self.get_filtered_bid_requests(full_name),
            "filtered_bids": self.get_filtered_bids(full_name),
            "bid_metrics": self.get_bid_metrics(full_name),
            "impression_metrics": self.get_impression_metrics(full_name),
            "loser_bids": self.get_loser_bids(full_name),
            "collected_at": datetime.utcnow().isoformat()
        }


# Reference: Creative Status Codes
CREATIVE_STATUS_CODES = {
    1: "CREATIVE_NOT_SUBMITTED",
    2: "CREATIVE_PENDING_REVIEW",
    3: "CREATIVE_APPROVED",
    4: "CREATIVE_DISAPPROVED",
    5: "CREATIVE_NOT_APPROVED",  # Different from disapproved - just not yet approved
    79: "CREATIVE_BLOCKED",
    80: "CREATIVE_PENDING_SUBMISSION",
}

# Reference: Callout Status Codes
CALLOUT_STATUS_CODES = {
    1: "SUCCESS",
    2: "NO_BID",
    3: "EMPTY_RESPONSE",
    4: "HTTP_ERROR",
    5: "RESPONSE_TOO_LARGE",
    6: "TIMEOUT",
    7: "BAD_REQUEST",
    8: "CONNECTION_ERROR",
    9: "NO_COOKIE_MATCH",
}
```

---

## Part 2: Database Schema - MINIMAL Approach

**File:** `creative-intelligence/storage/sqlite_store.py`

**Philosophy:** Troubleshooting data is low-volume aggregate data (~100-200 rows per collection). Store raw JSON, extract only what's needed for indexing. Optimize later when query patterns emerge.

```sql
-- ONE table for all troubleshooting data
-- Raw JSON storage with extracted keys for filtering
CREATE TABLE IF NOT EXISTS troubleshooting_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- When collected
    collection_date DATE NOT NULL,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- What type of data
    metric_type TEXT NOT NULL,  -- 'filtered_bids', 'bid_metrics', 'callout_status', 'loser_bids'
    
    -- Extracted keys for querying (from raw_data)
    status_code INTEGER,        -- creative_status_id or callout_status_id
    status_name TEXT,           -- Human-readable status
    
    -- The actual numbers
    bid_count INTEGER,
    impression_count INTEGER,
    
    -- Full API response for anything we didn't extract
    raw_data JSON,
    
    -- Prevent duplicates
    UNIQUE(collection_date, metric_type, status_code)
);

-- Collection log (one row per API call)
CREATE TABLE IF NOT EXISTS troubleshooting_collections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection_date DATE NOT NULL,
    days_requested INTEGER,
    filter_set_name TEXT,
    
    -- What we got
    filtered_bids_count INTEGER DEFAULT 0,
    bid_metrics_count INTEGER DEFAULT 0,
    callout_count INTEGER DEFAULT 0,
    
    -- Full raw response (for debugging)
    raw_response JSON,
    
    status TEXT DEFAULT 'complete',
    error_message TEXT,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(collection_date)
);

-- Minimal indexes - add more when we know query patterns
CREATE INDEX IF NOT EXISTS idx_ts_date_type ON troubleshooting_data(collection_date, metric_type);
CREATE INDEX IF NOT EXISTS idx_ts_status ON troubleshooting_data(status_name);
```

**Why this works:**
- ~200 rows/day max, not millions
- Raw JSON means no schema migrations when Google changes API
- Extracted fields (`status_code`, `status_name`, `bid_count`) cover 90% of queries
- Can always parse `raw_data` for edge cases
- One table instead of four = simpler

### 2.1 Storage Methods

```python
class TroubleshootingStore:
    """Add these methods to SqliteStore."""
    
    def save_troubleshooting_collection(self, metrics: Dict) -> Dict[str, int]:
        """
        Save all metrics from a collection run.
        Simple: iterate through each metric type, extract key fields, store.
        """
        counts = {"filtered_bids": 0, "bid_metrics": 0, "callout": 0}
        collection_date = datetime.now().date()
        
        # Filtered bids (the gold data)
        for row in metrics.get("filtered_bids", []):
            status_id = row.get("creativeStatusId")
            self._upsert_troubleshooting(
                collection_date=collection_date,
                metric_type="filtered_bids",
                status_code=status_id,
                status_name=CREATIVE_STATUS_CODES.get(status_id, f"UNKNOWN_{status_id}"),
                bid_count=int(row.get("bids", {}).get("value", 0)),
                impression_count=int(row.get("impressions", {}).get("value", 0)),
                raw_data=row
            )
            counts["filtered_bids"] += 1
        
        # Bid metrics (funnel data)
        for row in metrics.get("bid_metrics", []):
            self._upsert_troubleshooting(
                collection_date=collection_date,
                metric_type="bid_metrics",
                status_code=0,  # No status code for funnel metrics
                status_name="funnel",
                bid_count=int(row.get("bids", {}).get("value", 0)),
                impression_count=int(row.get("impressionsWon", {}).get("value", 0)),
                raw_data=row
            )
            counts["bid_metrics"] += 1
        
        # Callout status
        for row in metrics.get("filtered_bid_requests", []):
            status_id = row.get("calloutStatusId")
            self._upsert_troubleshooting(
                collection_date=collection_date,
                metric_type="callout_status",
                status_code=status_id,
                status_name=CALLOUT_STATUS_CODES.get(status_id, f"UNKNOWN_{status_id}"),
                bid_count=int(row.get("impressions", {}).get("value", 0)),
                impression_count=0,
                raw_data=row
            )
            counts["callout"] += 1
        
        # Log the collection
        self._log_collection(collection_date, metrics, counts)
        
        return counts
    
    def _upsert_troubleshooting(self, **kwargs):
        """Insert or update a troubleshooting row."""
        self.cursor.execute("""
            INSERT INTO troubleshooting_data 
            (collection_date, metric_type, status_code, status_name, bid_count, impression_count, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(collection_date, metric_type, status_code) DO UPDATE SET
                status_name = excluded.status_name,
                bid_count = excluded.bid_count,
                impression_count = excluded.impression_count,
                raw_data = excluded.raw_data,
                collected_at = CURRENT_TIMESTAMP
        """, (
            kwargs["collection_date"],
            kwargs["metric_type"],
            kwargs["status_code"],
            kwargs["status_name"],
            kwargs["bid_count"],
            kwargs["impression_count"],
            json.dumps(kwargs["raw_data"])
        ))
        self.conn.commit()
    
    def get_filtered_bids_summary(self, days: int = 7) -> List[Dict]:
        """Get summary of why bids were filtered - the key insight."""
        self.cursor.execute("""
            SELECT 
                status_name,
                SUM(bid_count) as total_bids,
                SUM(impression_count) as total_impressions,
                ROUND(100.0 * SUM(bid_count) / 
                    (SELECT SUM(bid_count) FROM troubleshooting_data 
                     WHERE metric_type = 'filtered_bids'
                     AND collection_date >= date('now', ?)), 2) as pct_of_filtered
            FROM troubleshooting_data
            WHERE metric_type = 'filtered_bids'
              AND collection_date >= date('now', ?)
            GROUP BY status_name
            ORDER BY total_bids DESC
        """, (f'-{days} days', f'-{days} days'))
        
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_bid_funnel(self, days: int = 7) -> Dict:
        """Get bid funnel by parsing raw_data from bid_metrics rows."""
        self.cursor.execute("""
            SELECT raw_data 
            FROM troubleshooting_data
            WHERE metric_type = 'bid_metrics'
              AND collection_date >= date('now', ?)
        """, (f'-{days} days',))
        
        # Aggregate from raw JSON
        totals = {
            "bids_submitted": 0,
            "bids_in_auction": 0,
            "impressions_won": 0,
            "billed_impressions": 0,
            "viewable_impressions": 0
        }
        
        for row in self.cursor.fetchall():
            data = json.loads(row["raw_data"])
            totals["bids_submitted"] += int(data.get("bids", {}).get("value", 0))
            totals["bids_in_auction"] += int(data.get("bidsInAuction", {}).get("value", 0))
            totals["impressions_won"] += int(data.get("impressionsWon", {}).get("value", 0))
            totals["billed_impressions"] += int(data.get("billedImpressions", {}).get("value", 0))
            totals["viewable_impressions"] += int(data.get("viewableImpressions", {}).get("value", 0))
        
        # Derived rates
        if totals["bids_submitted"]:
            totals["to_auction_rate"] = round(100 * totals["bids_in_auction"] / totals["bids_submitted"], 2)
        if totals["bids_in_auction"]:
            totals["win_rate"] = round(100 * totals["impressions_won"] / totals["bids_in_auction"], 2)
        
        return totals
```

---

## Part 3: Evaluation Engine

**New File:** `creative-intelligence/analysis/evaluation_engine.py`

The evaluation engine combines data from all sources to produce actionable recommendations.

```python
"""
Evaluation Engine

Combines:
- Performance data (CSV imports)
- Troubleshooting metrics (API)
- Creative inventory (API)

Produces:
- Pretargeting recommendations
- AdOps advice
- Opportunity identification
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RecommendationType(Enum):
    PRETARGETING = "pretargeting"     # Actionable config change
    ADOPS_ADVICE = "adops_advice"      # Needs human review
    OPPORTUNITY = "opportunity"        # Potential improvement
    CREATIVE_TEAM = "creative_team"    # Needs creative changes


@dataclass
class Recommendation:
    """A single actionable recommendation."""
    type: RecommendationType
    priority: int                      # 1 (critical) to 5 (nice-to-have)
    title: str
    description: str
    impact_estimate: str               # e.g., "~15% QPS reduction"
    
    # For pretargeting changes
    config_field: Optional[str] = None
    suggested_value: Optional[str] = None
    current_value: Optional[str] = None
    
    # Supporting data
    evidence: Dict = None
    

class EvaluationEngine:
    """
    Combines all data sources to generate actionable insights.
    """
    
    def __init__(self, store):
        self.store = store
    
    def run_full_evaluation(self, days: int = 7) -> Dict:
        """
        Run complete evaluation and generate recommendations.
        
        Returns:
            {
                "summary": {...},
                "recommendations": [...],
                "data_quality": {...},
                "generated_at": "..."
            }
        """
        results = {
            "recommendations": [],
            "summary": {},
            "data_quality": self._check_data_quality(days),
        }
        
        # Only proceed if we have sufficient data
        if results["data_quality"]["score"] < 0.5:
            results["recommendations"].append(Recommendation(
                type=RecommendationType.ADOPS_ADVICE,
                priority=1,
                title="Insufficient Data",
                description="Need more data to generate accurate recommendations. "
                           f"Missing: {', '.join(results['data_quality']['missing'])}",
                impact_estimate="N/A"
            ))
            return results
        
        # Run each analysis module
        results["recommendations"].extend(self._analyze_filtered_bids(days))
        results["recommendations"].extend(self._analyze_size_coverage(days))
        results["recommendations"].extend(self._analyze_geo_waste(days))
        results["recommendations"].extend(self._analyze_publisher_performance(days))
        results["recommendations"].extend(self._identify_opportunities(days))
        
        # Sort by priority
        results["recommendations"].sort(key=lambda r: r.priority)
        
        # Generate summary
        results["summary"] = self._generate_summary(results["recommendations"])
        
        return results
    
    def _check_data_quality(self, days: int) -> Dict:
        """Check what data sources are available and fresh."""
        quality = {
            "score": 0,
            "missing": [],
            "available": [],
        }
        
        # Check performance data
        perf_count = self.store.get_performance_data_count(days)
        if perf_count > 0:
            quality["available"].append(f"performance_data ({perf_count:,} rows)")
            quality["score"] += 0.4
        else:
            quality["missing"].append("performance_data (import CSV)")
        
        # Check troubleshooting data
        ts_count = self.store.get_troubleshooting_data_count(days)
        if ts_count > 0:
            quality["available"].append(f"troubleshooting_metrics ({ts_count:,} rows)")
            quality["score"] += 0.3
        else:
            quality["missing"].append("troubleshooting_metrics (run: catscan troubleshoot collect)")
        
        # Check creative inventory
        creative_count = self.store.get_creative_count()
        if creative_count > 0:
            quality["available"].append(f"creatives ({creative_count:,})")
            quality["score"] += 0.3
        else:
            quality["missing"].append("creatives (run: catscan sync)")
        
        return quality
    
    def _analyze_filtered_bids(self, days: int) -> List[Recommendation]:
        """
        Analyze WHY bids are being filtered.
        
        This is the most valuable analysis from Troubleshooting API.
        """
        recommendations = []
        
        filtered = self.store.get_filtered_bids_summary(days)
        if not filtered:
            return recommendations
        
        for row in filtered:
            status = row["creative_status"]
            pct = row["pct_of_filtered"]
            bids = row["total_bids"]
            
            # Creative not approved - high priority
            if status == "CREATIVE_NOT_APPROVED" and pct > 10:
                recommendations.append(Recommendation(
                    type=RecommendationType.ADOPS_ADVICE,
                    priority=1,
                    title=f"Creative Approval Issue ({pct}% of filtered)",
                    description=f"{bids:,} bids filtered because creatives not approved. "
                               "Review pending creative approvals in Authorized Buyers UI.",
                    impact_estimate=f"~{pct}% QPS could be recovered",
                    evidence={"status": status, "bids": bids, "pct": pct}
                ))
            
            # Creative disapproved - needs creative team
            elif status == "CREATIVE_DISAPPROVED" and pct > 5:
                recommendations.append(Recommendation(
                    type=RecommendationType.CREATIVE_TEAM,
                    priority=2,
                    title=f"Disapproved Creatives ({pct}% of filtered)",
                    description=f"{bids:,} bids filtered due to disapproved creatives. "
                               "Review disapproval reasons and update creative content.",
                    impact_estimate=f"~{pct}% QPS could be recovered with fixes",
                    evidence={"status": status, "bids": bids, "pct": pct}
                ))
            
            # Bid below floor - pricing issue
            elif status == "BID_BELOW_FLOOR" and pct > 15:
                recommendations.append(Recommendation(
                    type=RecommendationType.ADOPS_ADVICE,
                    priority=2,
                    title=f"Bids Below Floor Price ({pct}% of filtered)",
                    description=f"{bids:,} bids rejected for being below floor. "
                               "Consider increasing bid prices or excluding high-floor inventory.",
                    impact_estimate=f"Bidder adjustment could win {pct}% more",
                    evidence={"status": status, "bids": bids, "pct": pct}
                ))
        
        return recommendations
    
    def _analyze_size_coverage(self, days: int) -> List[Recommendation]:
        """
        Check for size mismatches between traffic and creative inventory.
        """
        recommendations = []
        
        # Get sizes we receive traffic for
        traffic_sizes = self.store.get_traffic_by_size(days)
        
        # Get sizes we have creatives for
        creative_sizes = self.store.get_creative_sizes()
        
        # Find mismatches
        for size_row in traffic_sizes:
            size = size_row["creative_size"]
            queries = size_row["reached_queries"]
            impressions = size_row["impressions"]
            
            if size not in creative_sizes:
                waste_pct = 100 * (queries - impressions) / queries if queries > 0 else 0
                
                if queries > 10000 and waste_pct > 90:
                    recommendations.append(Recommendation(
                        type=RecommendationType.PRETARGETING,
                        priority=2,
                        title=f"No Creatives for Size: {size}",
                        description=f"Receiving {queries:,} queries/day for {size} "
                                   f"but you have no creatives. {waste_pct:.0f}% waste.",
                        impact_estimate=f"~{queries:,} QPS could be excluded",
                        config_field="includedCreativeDimensions",
                        suggested_value=f"Ensure {size} is NOT in the include list",
                        evidence={"size": size, "queries": queries, "waste_pct": waste_pct}
                    ))
        
        # Find underutilized sizes (opportunity)
        for size_row in traffic_sizes:
            size = size_row["creative_size"]
            queries = size_row["reached_queries"]
            impressions = size_row["impressions"]
            
            if size in creative_sizes and queries > 50000:
                win_rate = 100 * impressions / queries if queries > 0 else 0
                
                if win_rate < 2:
                    # Low win rate on a size we have creatives for
                    recommendations.append(Recommendation(
                        type=RecommendationType.ADOPS_ADVICE,
                        priority=3,
                        title=f"Low Win Rate on {size}",
                        description=f"You have creatives for {size} but only {win_rate:.1f}% win rate. "
                                   f"({queries:,} queries, {impressions:,} wins). "
                                   "Check bid pricing or creative quality for this size.",
                        impact_estimate="Potential improvement with bid/creative optimization",
                        evidence={"size": size, "queries": queries, "win_rate": win_rate}
                    ))
        
        return recommendations
    
    def _analyze_geo_waste(self, days: int) -> List[Recommendation]:
        """
        Identify geographic regions with high waste.
        """
        recommendations = []
        
        geo_stats = self.store.get_waste_by_country(days)
        
        for row in geo_stats:
            country = row["country"]
            queries = row["reached_queries"]
            impressions = row["impressions"]
            waste_pct = row["waste_pct"]
            
            # High-volume countries with extreme waste
            if queries > 100000 and waste_pct > 95:
                recommendations.append(Recommendation(
                    type=RecommendationType.PRETARGETING,
                    priority=2,
                    title=f"High Waste from {country} ({waste_pct:.0f}%)",
                    description=f"{queries:,} queries from {country} with only {impressions:,} wins. "
                               f"Consider excluding this geo.",
                    impact_estimate=f"~{queries:,} QPS could be excluded",
                    config_field="geoTargeting.excludedIds",
                    suggested_value=f"Add geo ID for {country}",
                    evidence=row
                ))
            
            # Medium waste - flag for review
            elif queries > 50000 and waste_pct > 80:
                recommendations.append(Recommendation(
                    type=RecommendationType.ADOPS_ADVICE,
                    priority=3,
                    title=f"Review Performance in {country}",
                    description=f"{waste_pct:.0f}% waste in {country} ({queries:,} queries). "
                               "May benefit from geo exclusion or bid adjustment.",
                    impact_estimate="Potential QPS reduction with geo exclusion",
                    evidence=row
                ))
        
        return recommendations
    
    def _analyze_publisher_performance(self, days: int) -> List[Recommendation]:
        """
        Identify problematic publishers/apps.
        """
        recommendations = []
        
        # High traffic, zero engagement (potential fraud)
        fraud_signals = self.store.get_fraud_signal_publishers(days)
        
        for row in fraud_signals[:10]:  # Top 10 suspicious
            recommendations.append(Recommendation(
                type=RecommendationType.ADOPS_ADVICE,
                priority=2,
                title=f"Suspicious Publisher: {row['publisher_name'] or row['publisher_id']}",
                description=f"{row['impressions']:,} impressions, {row['clicks']} clicks "
                           f"({row['signal_type']}). Review for potential fraud.",
                impact_estimate="Review and potentially block",
                evidence=row
            ))
        
        return recommendations
    
    def _identify_opportunities(self, days: int) -> List[Recommendation]:
        """
        Identify opportunities for growth, not just waste reduction.
        """
        recommendations = []
        
        # Find sizes with high win rate but low volume
        # (Could increase QPS allocation)
        size_opps = self.store.get_high_performing_sizes(days)
        
        for row in size_opps:
            if row["win_rate"] > 20 and row["queries"] < 50000:
                recommendations.append(Recommendation(
                    type=RecommendationType.OPPORTUNITY,
                    priority=4,
                    title=f"High-Performing Size: {row['creative_size']}",
                    description=f"{row['win_rate']:.0f}% win rate on {row['creative_size']} "
                               f"but only {row['queries']:,} queries. "
                               "Consider increasing QPS allocation for this size.",
                    impact_estimate="Potential revenue growth",
                    evidence=row
                ))
        
        # Find unusual sizes that could be opportunities
        # (251x300 instead of 300x250 - less competition)
        unusual_sizes = self.store.get_unusual_size_opportunities(days)
        
        for row in unusual_sizes:
            recommendations.append(Recommendation(
                type=RecommendationType.OPPORTUNITY,
                priority=5,
                title=f"Unusual Size Opportunity: {row['creative_size']}",
                description=f"Size {row['creative_size']} has {row['queries']:,} queries "
                           f"with low competition. Creating creatives for this size "
                           "could be profitable.",
                impact_estimate="New revenue opportunity",
                evidence=row
            ))
        
        return recommendations
    
    def _generate_summary(self, recommendations: List[Recommendation]) -> Dict:
        """Generate executive summary from recommendations."""
        return {
            "total_recommendations": len(recommendations),
            "by_priority": {
                "critical": len([r for r in recommendations if r.priority == 1]),
                "high": len([r for r in recommendations if r.priority == 2]),
                "medium": len([r for r in recommendations if r.priority == 3]),
                "low": len([r for r in recommendations if r.priority in (4, 5)]),
            },
            "by_type": {
                "pretargeting": len([r for r in recommendations if r.type == RecommendationType.PRETARGETING]),
                "adops_advice": len([r for r in recommendations if r.type == RecommendationType.ADOPS_ADVICE]),
                "opportunity": len([r for r in recommendations if r.type == RecommendationType.OPPORTUNITY]),
                "creative_team": len([r for r in recommendations if r.type == RecommendationType.CREATIVE_TEAM]),
            }
        }
```

---

## Part 4: CLI Commands

**File:** `creative-intelligence/cli/qps_analyzer.py`

Add new commands for troubleshooting data collection and evaluation:

```python
@cli.group('troubleshoot')
def troubleshoot_group():
    """RTB Troubleshooting API commands."""
    pass


@troubleshoot_group.command('collect')
@click.option('--days', default=7, help='Days of data to collect')
@click.option('--environment', type=click.Choice(['APP', 'WEB']), help='Filter by environment')
def collect_troubleshooting(days, environment):
    """
    Collect troubleshooting metrics from Google API.
    
    Fetches filtered bid reasons, bid funnel metrics, and callout status.
    Requires adexchange.buyer scope on service account.
    """
    from collectors.troubleshooting.client import TroubleshootingClient
    
    config = load_config()
    
    click.echo(f"Collecting {days} days of troubleshooting metrics...")
    
    client = TroubleshootingClient(
        credentials_path=config.credentials_path,
        bidder_id=config.bidder_id
    )
    
    try:
        metrics = client.collect_all_metrics(
            days=days,
            environment=environment
        )
        
        # Save to database
        counts = store.save_troubleshooting_metrics(metrics)
        
        click.echo(f"\n✓ Collected:")
        click.echo(f"  - Filtered bids: {counts['filtered_bids']} rows")
        click.echo(f"  - Bid metrics: {counts['bid_metrics']} rows")
        click.echo(f"  - Callout metrics: {counts['callout_metrics']} rows")
        
    except Exception as e:
        click.echo(f"✗ Error: {e}", err=True)
        click.echo("\nMake sure your service account has the adexchange.buyer scope.", err=True)
        raise click.Abort()


@troubleshoot_group.command('filtered')
@click.option('--days', default=7)
def show_filtered_bids(days):
    """
    Show why bids are being filtered.
    
    This is the key insight for QPS optimization.
    """
    results = store.get_filtered_bids_summary(days)
    
    if not results:
        click.echo("No filtered bid data. Run: catscan troubleshoot collect")
        return
    
    click.echo(f"\nFiltered Bids (Last {days} Days)")
    click.echo("=" * 60)
    
    for row in results:
        click.echo(f"\n{row['creative_status']}")
        click.echo(f"  Bids: {row['total_bids']:,}")
        click.echo(f"  % of Filtered: {row['pct_of_filtered']}%")


@troubleshoot_group.command('funnel')
@click.option('--days', default=7)
def show_bid_funnel(days):
    """
    Show the bid funnel from requests to wins.
    """
    funnel = store.get_bid_funnel(days)
    
    if not funnel:
        click.echo("No funnel data. Run: catscan troubleshoot collect")
        return
    
    click.echo(f"\nBid Funnel (Last {days} Days)")
    click.echo("=" * 60)
    click.echo(f"Bids Submitted:    {funnel.get('bids_submitted', 0):>15,}")
    click.echo(f"  → To Auction:    {funnel.get('bids_in_auction', 0):>15,}  ({funnel.get('to_auction_rate', 0):.1f}%)")
    click.echo(f"  → Impressions:   {funnel.get('impressions_won', 0):>15,}  ({funnel.get('win_rate', 0):.1f}%)")
    click.echo(f"  → Viewable:      {funnel.get('viewable_impressions', 0):>15,}")


@cli.command('evaluate')
@click.option('--days', default=7)
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def run_evaluation(days, as_json):
    """
    Run full evaluation and generate recommendations.
    
    Combines all data sources to produce actionable insights.
    """
    from analysis.evaluation_engine import EvaluationEngine
    
    engine = EvaluationEngine(store)
    results = engine.run_full_evaluation(days)
    
    if as_json:
        import json
        click.echo(json.dumps(results, indent=2, default=str))
        return
    
    # Data quality check
    quality = results["data_quality"]
    click.echo(f"\nData Quality Score: {quality['score']*100:.0f}%")
    if quality["missing"]:
        click.echo(f"Missing: {', '.join(quality['missing'])}")
    
    # Summary
    summary = results["summary"]
    click.echo(f"\n{summary['total_recommendations']} Recommendations Found")
    click.echo(f"  Critical: {summary['by_priority']['critical']}")
    click.echo(f"  High: {summary['by_priority']['high']}")
    click.echo(f"  Medium: {summary['by_priority']['medium']}")
    
    # Recommendations
    click.echo("\n" + "=" * 70)
    
    for rec in results["recommendations"]:
        priority_colors = {1: 'red', 2: 'yellow', 3: 'white', 4: 'green', 5: 'cyan'}
        
        click.echo(f"\n[P{rec.priority}] {rec.title}")
        click.echo(f"Type: {rec.type.value}")
        click.echo(f"Impact: {rec.impact_estimate}")
        click.echo(f"\n{rec.description}")
        
        if rec.config_field:
            click.echo(f"\nAction: {rec.config_field}")
            click.echo(f"Suggested: {rec.suggested_value}")
        
        click.echo("-" * 70)
```

---

## Part 5: Campaign Clustering Enhancement - Country Filter

**File:** `dashboard/src/app/campaigns/page.tsx`

Add in-cluster filtering/sorting by country to support accurate labeling:

```typescript
interface ClusterFilterState {
  country: string | null;
  sortBy: 'spend' | 'impressions' | 'country' | 'date';
  sortOrder: 'asc' | 'desc';
}

function ClusterCard({ 
  campaign, 
  creatives,
  onCreativeMove,
  onRename 
}: ClusterCardProps) {
  const [filters, setFilters] = useState<ClusterFilterState>({
    country: null,
    sortBy: 'spend',
    sortOrder: 'desc'
  });
  const [showFilters, setShowFilters] = useState(false);
  
  // Get unique countries in this cluster
  const countries = useMemo(() => {
    const countrySet = new Set<string>();
    creatives.forEach(c => {
      if (c.performance?.country) {
        countrySet.add(c.performance.country);
      }
    });
    return Array.from(countrySet).sort();
  }, [creatives]);
  
  // Filter and sort creatives
  const displayedCreatives = useMemo(() => {
    let filtered = [...creatives];
    
    // Apply country filter
    if (filters.country) {
      filtered = filtered.filter(c => 
        c.performance?.country === filters.country
      );
    }
    
    // Apply sort
    filtered.sort((a, b) => {
      let aVal, bVal;
      
      switch (filters.sortBy) {
        case 'spend':
          aVal = a.performance?.spend || 0;
          bVal = b.performance?.spend || 0;
          break;
        case 'impressions':
          aVal = a.performance?.impressions || 0;
          bVal = b.performance?.impressions || 0;
          break;
        case 'country':
          aVal = a.performance?.country || '';
          bVal = b.performance?.country || '';
          break;
        case 'date':
          aVal = a.created_at || '';
          bVal = b.created_at || '';
          break;
        default:
          return 0;
      }
      
      if (filters.sortOrder === 'asc') {
        return aVal > bVal ? 1 : -1;
      }
      return aVal < bVal ? 1 : -1;
    });
    
    return filtered;
  }, [creatives, filters]);
  
  return (
    <div className="bg-gray-900 rounded-lg p-4 border border-gray-700">
      {/* Cluster header */}
      <div className="flex justify-between items-center mb-3">
        <EditableClusterName campaign={campaign} onRename={onRename} />
        
        <button
          onClick={() => setShowFilters(!showFilters)}
          className={cn(
            "p-1.5 rounded hover:bg-gray-700 transition",
            showFilters && "bg-gray-700"
          )}
          title="Filter & Sort"
        >
          <Filter className="h-4 w-4" />
        </button>
      </div>
      
      {/* Filter/Sort controls */}
      {showFilters && (
        <div className="mb-3 p-2 bg-gray-800 rounded flex flex-wrap gap-2 items-center text-sm">
          {/* Country filter */}
          <div className="flex items-center gap-1">
            <Globe className="h-3.5 w-3.5 text-gray-400" />
            <select
              value={filters.country || ''}
              onChange={(e) => setFilters(f => ({
                ...f, 
                country: e.target.value || null
              }))}
              className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs"
            >
              <option value="">All Countries</option>
              {countries.map(c => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </div>
          
          {/* Sort by */}
          <div className="flex items-center gap-1">
            <ArrowUpDown className="h-3.5 w-3.5 text-gray-400" />
            <select
              value={filters.sortBy}
              onChange={(e) => setFilters(f => ({
                ...f, 
                sortBy: e.target.value as any
              }))}
              className="bg-gray-700 border border-gray-600 rounded px-2 py-1 text-xs"
            >
              <option value="spend">Spend</option>
              <option value="impressions">Impressions</option>
              <option value="country">Country</option>
              <option value="date">Date Added</option>
            </select>
            
            <button
              onClick={() => setFilters(f => ({
                ...f,
                sortOrder: f.sortOrder === 'asc' ? 'desc' : 'asc'
              }))}
              className="p-1 hover:bg-gray-600 rounded"
            >
              {filters.sortOrder === 'asc' 
                ? <ArrowUp className="h-3 w-3" />
                : <ArrowDown className="h-3 w-3" />
              }
            </button>
          </div>
          
          {/* Clear filters */}
          {(filters.country || filters.sortBy !== 'spend') && (
            <button
              onClick={() => setFilters({
                country: null,
                sortBy: 'spend',
                sortOrder: 'desc'
              })}
              className="text-xs text-gray-400 hover:text-white"
            >
              Reset
            </button>
          )}
        </div>
      )}
      
      {/* Country breakdown badge */}
      {countries.length > 1 && !showFilters && (
        <div className="mb-2 flex flex-wrap gap-1">
          {countries.slice(0, 3).map(c => (
            <span 
              key={c} 
              className="text-xs px-1.5 py-0.5 bg-gray-800 rounded text-gray-400"
            >
              {c}
            </span>
          ))}
          {countries.length > 3 && (
            <span className="text-xs px-1.5 py-0.5 text-gray-500">
              +{countries.length - 3} more
            </span>
          )}
        </div>
      )}
      
      {/* Creative grid */}
      <div className="grid grid-cols-4 gap-1">
        {displayedCreatives.map((creative, idx) => (
          <CreativeMiniCard 
            key={creative.id}
            creative={creative}
            isLarge={idx === 0}
          />
        ))}
      </div>
      
      {/* Cluster stats */}
      <div className="mt-2 text-xs text-gray-400">
        {displayedCreatives.length} creative{displayedCreatives.length !== 1 ? 's' : ''}
        {filters.country && ` in ${filters.country}`}
        {' · '}
        ${(displayedCreatives.reduce((sum, c) => sum + (c.performance?.spend || 0), 0) / 1000).toFixed(1)}K
      </div>
    </div>
  );
}
```

---

## Part 6A: Query Performance Testing Framework

**New File:** `creative-intelligence/tests/query_performance.py`

Before optimizing, measure. This framework tests actual query patterns against real data.

```python
"""
Query Performance Testing Framework

Run after you have real data to identify bottlenecks.
Results inform which indexes to add/remove.

Usage:
    python tests/query_performance.py --db ~/.catscan/catscan.db
"""

import sqlite3
import time
import statistics
from typing import List, Dict, Callable
from dataclasses import dataclass
from datetime import datetime


@dataclass
class QueryResult:
    name: str
    query: str
    runs: int
    avg_ms: float
    min_ms: float
    max_ms: float
    std_dev: float
    row_count: int
    
    def __str__(self):
        return (f"{self.name}: avg={self.avg_ms:.1f}ms, "
                f"min={self.min_ms:.1f}ms, max={self.max_ms:.1f}ms, "
                f"rows={self.row_count}")


class QueryProfiler:
    """Profile query performance against real database."""
    
    def __init__(self, db_path: str):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.results: List[QueryResult] = []
    
    def profile(self, name: str, query: str, params: tuple = (), runs: int = 5) -> QueryResult:
        """Run a query multiple times and measure performance."""
        times = []
        row_count = 0
        
        for i in range(runs):
            start = time.perf_counter()
            cursor = self.conn.execute(query, params)
            rows = cursor.fetchall()
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)
            row_count = len(rows)
        
        result = QueryResult(
            name=name,
            query=query,
            runs=runs,
            avg_ms=statistics.mean(times),
            min_ms=min(times),
            max_ms=max(times),
            std_dev=statistics.stdev(times) if len(times) > 1 else 0,
            row_count=row_count
        )
        
        self.results.append(result)
        return result
    
    def explain(self, query: str, params: tuple = ()) -> List[str]:
        """Get query plan to understand index usage."""
        cursor = self.conn.execute(f"EXPLAIN QUERY PLAN {query}", params)
        return [row[3] for row in cursor.fetchall()]
    
    def table_stats(self) -> Dict[str, int]:
        """Get row counts for all tables."""
        cursor = self.conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        
        stats = {}
        for row in cursor.fetchall():
            table = row[0]
            count = self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            stats[table] = count
        
        return stats
    
    def report(self) -> str:
        """Generate performance report."""
        lines = [
            "=" * 70,
            "QUERY PERFORMANCE REPORT",
            f"Generated: {datetime.now().isoformat()}",
            "=" * 70,
            "",
            "TABLE SIZES:",
        ]
        
        for table, count in sorted(self.table_stats().items(), key=lambda x: -x[1]):
            lines.append(f"  {table}: {count:,} rows")
        
        lines.extend(["", "QUERY RESULTS:", ""])
        
        # Sort by avg time descending (slowest first)
        for r in sorted(self.results, key=lambda x: -x.avg_ms):
            lines.append(str(r))
            plan = self.explain(r.query)
            if plan:
                lines.append(f"  Plan: {' → '.join(plan)}")
            lines.append("")
        
        # Recommendations
        lines.extend(["", "RECOMMENDATIONS:", ""])
        
        slow_queries = [r for r in self.results if r.avg_ms > 100]
        if slow_queries:
            lines.append("⚠️  Queries over 100ms (consider optimizing):")
            for r in slow_queries:
                lines.append(f"  - {r.name}: {r.avg_ms:.0f}ms")
        
        full_scans = []
        for r in self.results:
            plan = self.explain(r.query)
            if any("SCAN" in p for p in plan):
                full_scans.append(r.name)
        
        if full_scans:
            lines.append("")
            lines.append("⚠️  Queries doing full table scans:")
            for name in full_scans:
                lines.append(f"  - {name}")
        
        return "\n".join(lines)


def run_standard_tests(db_path: str):
    """Run standard set of query performance tests."""
    
    profiler = QueryProfiler(db_path)
    
    # Performance data queries (the big table)
    profiler.profile(
        "perf_last_7_days",
        "SELECT * FROM performance_data WHERE metric_date >= date('now', '-7 days')"
    )
    
    profiler.profile(
        "perf_by_creative_7d",
        """SELECT creative_id, SUM(impressions), SUM(spend_micros)
           FROM performance_data 
           WHERE metric_date >= date('now', '-7 days')
           GROUP BY creative_id"""
    )
    
    profiler.profile(
        "perf_by_size_7d",
        """SELECT creative_size, SUM(reached_queries), SUM(impressions)
           FROM performance_data 
           WHERE metric_date >= date('now', '-7 days')
           GROUP BY creative_size"""
    )
    
    profiler.profile(
        "perf_by_country_7d",
        """SELECT country, SUM(reached_queries), SUM(impressions), SUM(spend_micros)
           FROM performance_data 
           WHERE metric_date >= date('now', '-7 days')
           GROUP BY country"""
    )
    
    profiler.profile(
        "perf_by_billing_7d",
        """SELECT billing_id, SUM(reached_queries), SUM(impressions)
           FROM performance_data 
           WHERE metric_date >= date('now', '-7 days')
           GROUP BY billing_id"""
    )
    
    profiler.profile(
        "perf_waste_by_size",
        """SELECT creative_size,
                  SUM(reached_queries) as queries,
                  SUM(impressions) as impressions,
                  ROUND(100.0 * (SUM(reached_queries) - SUM(impressions)) / 
                        NULLIF(SUM(reached_queries), 0), 2) as waste_pct
           FROM performance_data
           WHERE metric_date >= date('now', '-7 days')
           GROUP BY creative_size
           HAVING queries > 1000
           ORDER BY waste_pct DESC"""
    )
    
    # Creative joins
    profiler.profile(
        "creatives_with_perf",
        """SELECT c.id, c.format, c.canonical_size, 
                  SUM(p.impressions) as total_imps,
                  SUM(p.spend_micros) as total_spend
           FROM creatives c
           LEFT JOIN performance_data p ON c.id = p.creative_id
           WHERE p.metric_date >= date('now', '-7 days')
           GROUP BY c.id"""
    )
    
    # Size coverage (key for QPS optimization)
    profiler.profile(
        "size_coverage",
        """SELECT p.creative_size,
                  COUNT(DISTINCT c.id) as creatives_available,
                  SUM(p.reached_queries) as queries
           FROM performance_data p
           LEFT JOIN creatives c ON p.creative_size = c.canonical_size
           WHERE p.metric_date >= date('now', '-7 days')
           GROUP BY p.creative_size"""
    )
    
    # Fraud detection patterns
    profiler.profile(
        "fraud_clicks_gt_imps",
        """SELECT creative_id, app_id, app_name,
                  SUM(clicks) as clicks, SUM(impressions) as imps
           FROM performance_data
           WHERE metric_date >= date('now', '-14 days')
           GROUP BY creative_id, app_id
           HAVING clicks > imps AND imps > 100"""
    )
    
    profiler.profile(
        "fraud_zero_engagement",
        """SELECT creative_id, publisher_id,
                  SUM(impressions) as imps, SUM(clicks) as clicks
           FROM performance_data
           WHERE metric_date >= date('now', '-14 days')
           GROUP BY creative_id, publisher_id
           HAVING imps > 10000 AND clicks = 0"""
    )
    
    # Troubleshooting data (should be fast - small table)
    profiler.profile(
        "troubleshoot_filtered_bids",
        """SELECT status_name, SUM(bid_count), SUM(impression_count)
           FROM troubleshooting_data
           WHERE metric_type = 'filtered_bids'
             AND collection_date >= date('now', '-7 days')
           GROUP BY status_name"""
    )
    
    print(profiler.report())
    return profiler


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="~/.catscan/catscan.db")
    args = parser.parse_args()
    
    import os
    db_path = os.path.expanduser(args.db)
    run_standard_tests(db_path)
```

### 6A.1 CLI Command for Profiling

```python
@cli.command('profile-queries')
@click.option('--runs', default=5, help='Times to run each query')
def profile_queries(runs):
    """
    Profile query performance against current database.
    
    Run this after importing real data to identify slow queries.
    Results guide index optimization.
    """
    from tests.query_performance import run_standard_tests
    run_standard_tests(store.db_path)
```

### 6A.2 When to Run

1. **After first big import** - baseline performance
2. **After adding new queries** - verify they're efficient  
3. **After schema changes** - ensure indexes still help
4. **When things feel slow** - identify bottleneck

### 6A.3 What to Look For

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| Query >500ms | Full table scan | Add index on WHERE/GROUP BY columns |
| Query plan shows "SCAN TABLE" | No usable index | Add composite index matching query |
| std_dev > avg | Inconsistent performance | Check for lock contention, vacuuM |
| Same data, different times | SQLite cache effects | Run PRAGMA cache_size check |

**File:** `creative-intelligence/api/main.py`

```python
@app.get("/api/evaluation")
async def get_evaluation(days: int = 7):
    """
    Run evaluation engine and return recommendations.
    """
    from analysis.evaluation_engine import EvaluationEngine
    
    engine = EvaluationEngine(store)
    results = engine.run_full_evaluation(days)
    
    # Convert dataclasses to dicts for JSON
    results["recommendations"] = [
        {
            "type": r.type.value,
            "priority": r.priority,
            "title": r.title,
            "description": r.description,
            "impact_estimate": r.impact_estimate,
            "config_field": r.config_field,
            "suggested_value": r.suggested_value,
            "evidence": r.evidence,
        }
        for r in results["recommendations"]
    ]
    
    return results


@app.get("/api/troubleshooting/filtered-bids")
async def get_filtered_bids(days: int = 7):
    """Get filtered bid reasons summary."""
    return store.get_filtered_bids_summary(days)


@app.get("/api/troubleshooting/funnel")
async def get_bid_funnel(days: int = 7):
    """Get bid funnel metrics."""
    return store.get_bid_funnel(days)


@app.post("/api/troubleshooting/collect")
async def trigger_collection(
    days: int = 7,
    environment: Optional[str] = None,
    background_tasks: BackgroundTasks = None
):
    """
    Trigger troubleshooting data collection.
    
    Runs in background and returns immediately.
    """
    async def collect():
        from collectors.troubleshooting.client import TroubleshootingClient
        
        config = load_config()
        client = TroubleshootingClient(
            credentials_path=config.credentials_path,
            bidder_id=config.bidder_id
        )
        
        metrics = client.collect_all_metrics(days=days, environment=environment)
        store.save_troubleshooting_metrics(metrics)
    
    background_tasks.add_task(collect)
    
    return {"status": "collection_started", "days": days}
```

---

## Implementation Order

### Step 1: Update Auth Scopes (15 min)
1. Add `adexchange.buyer` scope to credentials loading
2. Test that existing functionality still works
3. Verify service account has the new scope in Google Cloud Console

### Step 2: Database Schema (30 min)
1. Add `troubleshooting_data` and `troubleshooting_collections` tables
2. Add migration logic (create if not exists)
3. Implement `save_troubleshooting_collection()` method
4. Test table creation

### Step 3: Troubleshooting Client (1.5 hours)
1. Create `collectors/troubleshooting/client.py`
2. Implement filter set creation
3. Implement each metric retrieval method
4. Add `collect_all_metrics()` convenience method
5. Test with: `python -c "from collectors.troubleshooting.client import TroubleshootingClient; ..."`

### Step 4: CLI Commands (1 hour)
1. Add `troubleshoot` command group
2. Implement `collect` command
3. Implement `filtered` and `funnel` display commands
4. Test end-to-end: `catscan troubleshoot collect --days 7`

### Step 5: Query Performance Framework (45 min)
1. Create `tests/query_performance.py`
2. Add standard query tests for performance_data
3. Add `profile-queries` CLI command
4. Run against current database to establish baseline
5. Document any slow queries found

### Step 6: Evaluation Engine (2 hours)
1. Create `analysis/evaluation_engine.py`
2. Implement data quality check
3. Implement each analysis module
4. Implement recommendation generation
5. Test: `catscan evaluate --days 7`

### Step 7: Campaign Cluster Country Filter (1 hour)
1. Add filter state to ClusterCard
2. Implement country dropdown
3. Implement sort controls
4. Add country breakdown badges
5. Test filtering and sorting

### Step 8: API Endpoints (30 min)
1. Add `/api/evaluation` endpoint
2. Add `/api/troubleshooting/*` endpoints
3. Test via Swagger UI

### Step 9: Integration Testing (1 hour)
1. Full collection flow
2. Evaluation with all data sources
3. Dashboard display of recommendations
4. Country filtering in clusters
5. Re-run query profiler to verify no regressions

---

## Testing Checklist

### Troubleshooting API
- [ ] Service account has `adexchange.buyer` scope
- [ ] Filter set creation succeeds
- [ ] Filtered bids returns data
- [ ] Bid metrics returns funnel data
- [ ] Data saved to database correctly

### Query Performance
- [ ] `catscan profile-queries` runs without error
- [ ] All queries under 500ms on current data volume
- [ ] No unexpected full table scans
- [ ] Baseline documented for future comparison

### Evaluation Engine
- [ ] Data quality check works with missing data
- [ ] Filtered bid analysis generates recommendations
- [ ] Size coverage analysis works
- [ ] Geo waste analysis works
- [ ] Publisher analysis works
- [ ] Opportunities identified

### CLI
- [ ] `catscan troubleshoot collect` works
- [ ] `catscan troubleshoot filtered` displays data
- [ ] `catscan troubleshoot funnel` displays funnel
- [ ] `catscan evaluate` generates recommendations
- [ ] `catscan evaluate --json` outputs valid JSON

### Campaign Clusters
- [ ] Country filter dropdown populated
- [ ] Filtering by country works
- [ ] Sort by spend/impressions/country works
- [ ] Country badges display
- [ ] Reset filters works

---

## Notes for Next Engineer

1. **Scope Authorization**: The service account needs `adexchange.buyer` scope added in Google Cloud Console AND authorized in Authorized Buyers UI.

2. **Filter Sets**: Transient filter sets don't persist, which is fine for ad-hoc queries. If you need recurring queries, use `is_transient=False`.

3. **Rate Limits**: The Troubleshooting API has separate rate limits from the RTB API. If you hit limits, implement backoff.

4. **Data Freshness**: Troubleshooting data has ~4 hour latency. Don't expect real-time.

5. **Country Labeling**: The in-cluster country filter is critical for accurate labeling. Media buyers often run the same creative in multiple countries with different expectations.

---

## Future Work: Schema Cleanup (Phase 12?)

Current schema has technical debt from iterative development. NOT blocking, but should address eventually:

### Tables to Consolidate

| Keep | Remove/Merge | Reason |
|------|-------------|--------|
| `performance_data` | `performance_metrics` | Duplicate purpose, performance_data is the unified approach |
| `ai_campaigns` | `campaigns` | Two campaign systems, pick one |
| `creative_campaigns` | `campaign_creatives` | Two junction tables for same relationship |

### Tables to Evaluate

| Table | Question |
|-------|----------|
| `daily_creative_summary` | Is this being populated? If not, remove or add population logic |
| `rtb_traffic` | Redundant with performance_data.creative_size? |
| `clusters` | Different from campaigns - is clustering still needed separately? |
| `video_metrics` | Could be columns on performance_data instead |

### After Running Query Profiler

Based on actual query patterns, consider:

1. **Composite indexes** - If queries always filter by (metric_date, billing_id, creative_size), add that composite
2. **Partial indexes** - If you only query recent data, `CREATE INDEX ... WHERE metric_date >= date('now', '-30 days')`
3. **Covering indexes** - If SELECT always gets same columns, include them in index
4. **Remove unused indexes** - Each index slows writes, verify they're used

### Scale Considerations

At 1M rows/day:
- **Partitioning by month** - SQLite doesn't support native partitioning, but you could use attached databases or separate tables per month
- **Archive old data** - Move data >90 days to archive table or separate database
- **Summary tables** - Pre-aggregate daily/weekly totals rather than query raw rows

**Run `catscan profile-queries` first to see what's actually slow before optimizing.**

---

**Version:** 11.0  
**Phase:** RTB Troubleshooting API Integration  
**Created:** December 2, 2025