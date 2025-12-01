# Claude CLI Prompt 3/4: Update Analyzers for Unified Table

## Context

Analyzers need to query `performance_data` instead of the old `size_metrics_daily` table.

**Project:** `/home/jen/Documents/rtbcat-platform/creative-intelligence/`

---

## Task

### Update `qps/size_analyzer.py`

Replace the `get_traffic_sizes` method:

```python
def get_traffic_sizes(self, days: int = 7) -> Dict[str, Dict]:
    """
    Get sizes from performance_data table.
    Aggregates at query time (not import time).
    """
    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()
    
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    sizes: Dict[str, Dict] = {}
    
    try:
        cursor.execute("""
            SELECT 
                creative_size,
                SUM(COALESCE(reached_queries, 0)) as total_reached,
                SUM(COALESCE(impressions, 0)) as total_impressions,
                SUM(COALESCE(clicks, 0)) as total_clicks,
                SUM(COALESCE(spend_micros, 0)) as total_spend
            FROM performance_data
            WHERE metric_date >= ?
              AND creative_size IS NOT NULL 
              AND creative_size != ''
            GROUP BY creative_size
            ORDER BY SUM(COALESCE(reached_queries, 0)) DESC
        """, (cutoff_date,))
        
        for row in cursor.fetchall():
            size_str = row[0]
            sizes[size_str] = {
                "reached_queries": row[1] or 0,
                "impressions": row[2] or 0,
                "clicks": row[3] or 0,
                "spend_micros": row[4] or 0,
            }
    
    finally:
        conn.close()
    
    return sizes
```

---

### Update `qps/config_tracker.py`

Replace the `get_config_metrics` method:

```python
def get_config_metrics(self, days: int = 7) -> Dict[str, Dict]:
    """
    Get aggregated metrics by billing_id from performance_data.
    """
    conn = sqlite3.connect(self.db_path)
    cursor = conn.cursor()
    
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    
    metrics: Dict[str, Dict] = {}
    
    try:
        cursor.execute("""
            SELECT 
                billing_id,
                SUM(COALESCE(reached_queries, 0)) as total_reached,
                SUM(COALESCE(impressions, 0)) as total_impressions,
                SUM(COALESCE(clicks, 0)) as total_clicks,
                SUM(COALESCE(spend_micros, 0)) as total_spend_micros
            FROM performance_data
            WHERE metric_date >= ?
              AND billing_id IS NOT NULL
            GROUP BY billing_id
        """, (cutoff_date,))
        
        for row in cursor.fetchall():
            billing_id = str(row[0])
            metrics[billing_id] = {
                "reached_queries": row[1] or 0,
                "impressions": row[2] or 0,
                "clicks": row[3] or 0,
                "spend_micros": row[4] or 0,
            }
    
    finally:
        conn.close()
    
    return metrics
```

---

### Update `qps/fraud_detector.py`

Replace `detect_high_ctr` query:

```python
cursor.execute("""
    SELECT 
        app_id,
        app_name,
        SUM(COALESCE(impressions, 0)) as total_impressions,
        SUM(COALESCE(clicks, 0)) as total_clicks,
        COUNT(DISTINCT metric_date) as days_active
    FROM performance_data
    WHERE metric_date >= ?
      AND app_id IS NOT NULL
      AND app_id != ''
    GROUP BY app_id, app_name
    HAVING SUM(COALESCE(impressions, 0)) > 100 AND SUM(COALESCE(clicks, 0)) > 0
""", (cutoff_date,))
```

Replace `detect_clicks_exceed_impressions` query:

```python
cursor.execute("""
    SELECT 
        app_id,
        app_name,
        COUNT(*) as total_days,
        SUM(CASE WHEN COALESCE(clicks, 0) > COALESCE(impressions, 0) THEN 1 ELSE 0 END) as violation_days,
        SUM(COALESCE(clicks, 0)) as total_clicks,
        SUM(COALESCE(impressions, 0)) as total_impressions
    FROM performance_data
    WHERE metric_date >= ?
      AND impressions > 0
    GROUP BY app_id, app_name
    HAVING SUM(CASE WHEN COALESCE(clicks, 0) > COALESCE(impressions, 0) THEN 1 ELSE 0 END) >= 2
""", (cutoff_date,))
```

---

### Update `qps/__init__.py`

```python
"""QPS Optimization Module for RTBcat.

Unified data storage in performance_data table.
Analysis/aggregation happens at query time.

Example:
    >>> from qps import validate_csv, import_csv, SizeCoverageAnalyzer
    >>> 
    >>> # Validate first
    >>> validation = validate_csv("/path/to/export.csv")
    >>> if not validation.is_valid:
    >>>     print(validation.get_fix_instructions())
    >>> 
    >>> # Import
    >>> result = import_csv("/path/to/export.csv")
    >>> 
    >>> # Analyze
    >>> analyzer = SizeCoverageAnalyzer()
    >>> print(analyzer.generate_report(days=7))
"""

from qps.importer import (
    validate_csv,
    import_csv,
    import_bigquery_csv,  # Backward compat
    get_data_summary,
    get_import_summary,   # Backward compat
    ImportResult,
    ValidationResult,
)
from qps.size_analyzer import SizeCoverageAnalyzer, CoverageReport
from qps.config_tracker import ConfigPerformanceTracker, ConfigReport
from qps.fraud_detector import FraudSignalDetector, FraudReport
from qps.models import (
    CreativeSizeInfo,
    SizeCoverageResult,
    ConfigPerformance,
    FraudSignal,
)
from qps.constants import (
    GOOGLE_AVAILABLE_SIZES,
    PRETARGETING_CONFIGS,
    ENDPOINTS,
    TOTAL_ENDPOINT_QPS,
    ACCOUNT_ID,
    ACCOUNT_NAME,
)

__all__ = [
    # Importer
    "validate_csv",
    "import_csv",
    "import_bigquery_csv",
    "get_data_summary",
    "get_import_summary",
    "ImportResult",
    "ValidationResult",
    # Analyzers
    "SizeCoverageAnalyzer",
    "CoverageReport",
    "ConfigPerformanceTracker",
    "ConfigReport",
    "FraudSignalDetector",
    "FraudReport",
    # Models
    "CreativeSizeInfo", 
    "SizeCoverageResult",
    "ConfigPerformance",
    "FraudSignal",
    # Constants
    "GOOGLE_AVAILABLE_SIZES",
    "PRETARGETING_CONFIGS",
    "ENDPOINTS",
    "TOTAL_ENDPOINT_QPS",
    "ACCOUNT_ID",
    "ACCOUNT_NAME",
]
```

---

## Success Criteria

- [ ] size_analyzer queries performance_data table
- [ ] config_tracker queries performance_data table
- [ ] fraud_detector queries performance_data table
- [ ] All use COALESCE for NULL safety
- [ ] __init__.py exports validate_csv and ValidationResult

---

## After Completing

Tell Jen: "Analyzers updated. Ready for Prompt 4 (CLI & Cleanup)."
