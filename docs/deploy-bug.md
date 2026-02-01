# Deployment Failure Report

## Summary
Deployment of commit `623f376` ("Fix health configured + bump version") fails due to a **circular import error** that causes the API container to crash on startup.

## Root Cause Analysis

**The Error:**
```
ImportError: cannot import name 'QpsSizeCoverageAnalyzer' from partially initialized module
'analytics.cli_size_analyzer' (most likely due to a circular import)
```

**The Circular Import Chain:**
```
api/routers/recommendations.py
  → services/recommendations_service.py (NEW in 623f376)
    → analytics.recommendation_engine
      → analytics/__init__.py
        → analytics.cli_size_analyzer
          → importers.constants (triggers importers/__init__.py)
            → importers/__init__.py
              → analytics.cli_size_analyzer  ← CIRCULAR!
```

**Why It Worked Before (sha-7db7592):**
The previous version used **lazy imports** inside function bodies:
```python
async def get_recommendations(...):
    from analytics.recommendation_engine import RecommendationEngine  # Lazy
```

**What Changed in 623f376:**
A new `services/recommendations_service.py` was added with **module-level imports**:
```python
from analytics.recommendation_engine import RecommendationEngine, Severity  # Eager
```

This triggers the full import chain at application startup instead of at request time.

## The Offending Code

`importers/__init__.py` lines 48-51:
```python
# Re-export analyzers from analytics/ for backwards compatibility
from analytics.cli_size_analyzer import QpsSizeCoverageAnalyzer, CoverageReport
from analytics.cli_config_tracker import ConfigPerformanceTracker, ConfigReport
from analytics.cli_fraud_detector import FraudSignalDetector, FraudReport
```

These re-exports exist for backwards compatibility but create a circular dependency with `analytics/`.

---

## Recommendations

**Option 1: Lazy Imports in importers/__init__.py (Recommended)**
Replace eager imports with `__getattr__` pattern:
```python
def __getattr__(name: str):
    if name in ("QpsSizeCoverageAnalyzer", "CoverageReport"):
        from analytics.cli_size_analyzer import QpsSizeCoverageAnalyzer, CoverageReport
        return {"QpsSizeCoverageAnalyzer": QpsSizeCoverageAnalyzer, "CoverageReport": CoverageReport}[name]
    # ... similar for other analyzers
    raise AttributeError(f"module 'importers' has no attribute {name!r}")
```
- Preserves backwards compatibility
- No changes needed elsewhere

**Option 2: Remove Re-exports Entirely**
Delete lines 48-51 and update any code using `from importers import QpsSizeCoverageAnalyzer` to use `from analytics.cli_size_analyzer import QpsSizeCoverageAnalyzer`.
- Cleaner architecture
- May break external scripts

**Option 3: Revert to Lazy Imports in recommendations.py**
Change `services/recommendations_service.py` to use function-level imports:
```python
class RecommendationsService:
    async def generate(self, ...):
        from analytics.recommendation_engine import RecommendationEngine, Severity
        # ...
```
- Quick fix but defers the problem

---

## Immediate Workaround

To get production running now, roll back to the previous working image:

```bash
# On VM: /opt/catscan
sudo sed -i 's/IMAGE_TAG=sha-623f376/IMAGE_TAG=sha-7db7592/' .env
sudo docker compose -f docker-compose.gcp.yml up -d --force-recreate
```

This restores v0.9.0 without the health fix, but the API will be running.

---

## Next Steps

1. Apply Option 1 fix to `importers/__init__.py`
2. Commit and push to trigger new build
3. Redeploy with fixed image
