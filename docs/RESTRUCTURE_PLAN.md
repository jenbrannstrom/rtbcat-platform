# Codebase Restructuring Plan

> **Status:** PLAN - Awaiting approval
> **Goal:** Simplify project structure for OSS readability

---

## Current Structure (19 directories - confusing)

```
rtbcat-platform/
├── analysis/              # Evaluation engine (1 file, 600 lines)
├── analytics/             # RTB analytics modules (14 files)
├── api/                   # FastAPI backend
├── collectors/            # Google API clients (16 files)
├── config/                # Config manager
├── creative-intelligence/ # CLI + tests (orphaned sub-project)
│   ├── cli/               # → Should be at root
│   ├── tests/             # → Should be at root
│   └── venv/              # → Redundant (root has venv/)
├── dashboard/             # Next.js frontend
├── data/                  # [gitignored]
├── docs/                  # Documentation
├── investigations/        # [gitignored]
├── migrations/            # DB migrations
├── prompts/               # Claude prompts
├── qps/                   # QPS importers & analyzers (12 files)
├── scripts/               # Utility scripts
├── services/              # Business logic services
├── storage/               # Database layer
├── terraform/             # Infrastructure
├── utils/                 # Shared utilities (5 files)
└── venv/                  # Python environment
```

### Problems

1. **`creative-intelligence/`** - Orphaned sub-project with its own venv, tests scattered
2. **No root `cli/`** - CLI tool buried in sub-project
3. **No root `tests/`** - Tests scattered in `creative-intelligence/tests/` and `scripts/`
4. **`analysis/` vs `analytics/`** - Confusing naming (both do analysis)
5. **`qps/` vs `analytics/`** - Overlapping concerns (both analyze RTB data)

---

## Proposed Structure (14 directories - clear)

```
rtbcat-platform/
├── api/                   # FastAPI backend (unchanged)
├── dashboard/             # Next.js frontend (unchanged)
├── cli/                   # CLI tools (moved from creative-intelligence/)
├── tests/                 # All tests consolidated
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── analytics/             # All analysis code (merged)
│   ├── evaluation.py      # ← from analysis/evaluation_engine.py
│   ├── waste.py           # existing
│   ├── qps.py             # existing
│   └── ...
├── collectors/            # Google API clients (unchanged)
├── importers/             # CSV/data importers (renamed from qps/)
├── services/              # Business logic (unchanged)
├── storage/               # Database layer (unchanged)
├── config/                # Configuration (unchanged)
├── utils/                 # Shared utilities (unchanged)
├── migrations/            # DB migrations (unchanged)
├── scripts/               # Utility scripts (unchanged)
├── docs/                  # Documentation (unchanged)
└── terraform/             # Infrastructure (unchanged)
```

---

## Migration Steps

### Phase 1: Move CLI to root (LOW RISK)

**Goal:** Eliminate `creative-intelligence/` as a separate sub-project

```bash
# Step 1: Move CLI to root
git mv creative-intelligence/cli cli

# Step 2: Update imports in cli/qps_analyzer.py
# Change: sys.path.insert(0, str(Path(__file__).parent.parent))
# To: (remove - no longer needed at root level)

# Step 3: Move tests to root
mkdir -p tests/unit tests/integration
git mv creative-intelligence/tests/*.py tests/unit/

# Step 4: Delete empty creative-intelligence/ (keep venv locally)
git rm -r creative-intelligence/
rm -rf creative-intelligence/  # local cleanup
```

**Files affected:**
- `creative-intelligence/cli/qps_analyzer.py` → `cli/qps_analyzer.py`
- `creative-intelligence/cli/__init__.py` → `cli/__init__.py`
- `creative-intelligence/tests/*.py` → `tests/unit/*.py`

**Import changes needed:**
- `cli/qps_analyzer.py` line 44: Remove `sys.path.insert()` hack

---

### Phase 2: Merge analysis/ into analytics/ (MEDIUM RISK)

**Goal:** One directory for all analysis code

```bash
# Step 1: Move evaluation engine
git mv analysis/evaluation_engine.py analytics/evaluation.py

# Step 2: Update import in api/routers/troubleshooting.py
# From: from analysis.evaluation_engine import EvaluationEngine
# To:   from analytics.evaluation import EvaluationEngine

# Step 3: Delete empty analysis/
git rm -r analysis/
```

**Files affected:**
- `analysis/evaluation_engine.py` → `analytics/evaluation.py`
- `api/routers/troubleshooting.py` - Update import

---

### Phase 3: Rename qps/ to importers/ (MEDIUM RISK)

**Goal:** Clarify that `qps/` handles data import, not QPS analysis

**Current `qps/` contents:**
- `importer.py`, `smart_importer.py`, `funnel_importer.py` - Data import
- `size_analyzer.py`, `fraud_detector.py`, `config_tracker.py` - Analysis
- `utils.py`, `constants.py` - Utilities

**Decision:** Keep as `qps/` OR split into:
- `importers/` - CSV import logic
- Keep analyzers in `analytics/`

**Recommendation:** DEFER - This is a larger refactor. The `qps/` name is accurate for the domain (QPS = Queries Per Second optimization). Keep for now.

---

### Phase 4: Update documentation (LOW RISK)

Update these files to reflect new structure:
- `README.md` - Project structure section
- `ARCHITECTURE.md` - Module descriptions
- `INSTALL.md` - CLI commands section (new path)

---

## Detailed Changes

### 1. cli/qps_analyzer.py

**Before (line 44-50):**
```python
sys.path.insert(0, str(Path(__file__).parent.parent))

from qps.importer import validate_csv, import_csv, get_data_summary
from qps.size_analyzer import QpsSizeCoverageAnalyzer
```

**After:**
```python
# No sys.path hack needed - cli/ is at root level

from qps.importer import validate_csv, import_csv, get_data_summary
from qps.size_analyzer import QpsSizeCoverageAnalyzer
```

### 2. api/routers/troubleshooting.py

**Before (line 15):**
```python
from analysis.evaluation_engine import EvaluationEngine, RecommendationType
```

**After:**
```python
from analytics.evaluation import EvaluationEngine, RecommendationType
```

### 3. tests/ structure

**New layout:**
```
tests/
├── __init__.py
├── conftest.py              # Pytest fixtures
├── unit/
│   ├── __init__.py
│   ├── test_waste_analysis.py    # from creative-intelligence/tests/
│   ├── test_multi_seat.py        # from creative-intelligence/tests/
│   └── test_evaluation.py        # new - for analytics/evaluation.py
├── integration/
│   ├── __init__.py
│   └── test_api_access.py        # from scripts/test_api_access.py
└── fixtures/
    └── sample_data/
```

---

## Risk Assessment

| Phase | Risk | Impact if Failed | Rollback |
|-------|------|------------------|----------|
| 1. Move CLI | LOW | CLI commands break | `git revert` |
| 2. Merge analysis | MEDIUM | /api/evaluation breaks | `git revert` |
| 3. Rename qps | HIGH | Many imports break | DEFER |
| 4. Update docs | NONE | Just docs | N/A |

---

## Verification Checklist

After each phase, verify:

```bash
# 1. Tests pass
pytest tests/ -v

# 2. CLI works
python -m cli.qps_analyzer --help

# 3. API starts
python -m uvicorn api.main:app --port 8000

# 4. Key endpoints work
curl http://localhost:8000/health
curl http://localhost:8000/api/evaluation?days=7
```

---

## Files to Delete (cleanup)

| Path | Reason |
|------|--------|
| `creative-intelligence/` | Moved to root `cli/` and `tests/` |
| `analysis/` | Merged into `analytics/` |

---

## Decision Points

**Q1: Rename `qps/` to `importers/`?**
- Pro: Clearer purpose (it imports CSV data)
- Con: Many files import from `qps.`, high change count
- **Recommendation:** DEFER - Keep `qps/` for now, document purpose in README

**Q2: Keep `utils/` or merge into modules?**
- Pro of merge: Less top-level directories
- Con of merge: Utils are truly cross-cutting
- **Recommendation:** KEEP `utils/` - It's well-designed and widely used

**Q3: Create `core/` for shared models?**
- Would contain: data models, constants, shared types
- **Recommendation:** DEFER - Current structure works, don't over-engineer

---

## Summary

**Immediate actions (Phases 1-2):**
1. Move `creative-intelligence/cli/` → `cli/`
2. Move `creative-intelligence/tests/` → `tests/unit/`
3. Move `analysis/evaluation_engine.py` → `analytics/evaluation.py`
4. Delete empty directories
5. Update 2 import statements
6. Update documentation

**Result:**
- 19 directories → 14 directories
- Clear separation: `api/`, `dashboard/`, `cli/`, `tests/`
- No orphaned sub-projects
- All tests in one place

**Deferred:**
- Renaming `qps/` (too many import changes)
- Creating `core/` module (not needed yet)
