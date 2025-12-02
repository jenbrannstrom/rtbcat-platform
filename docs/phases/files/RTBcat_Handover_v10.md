# Cat-Scan Handover v10.2

**Date:** December 1, 2025  
**Status:** Phase 9.6 - Unified Data Architecture (Complete)  
**Purpose:** Complete project context for continuation in new chat

---

## Quick Start for New Chat

```
You are a world class developer. 
You write and architect beautiful and elegant  systems.
You don't write code yourself. You are managing a CLAUDE CLI who does the actual coding. Except when you want specific style of code, or you want to provide ane example.
You write accurate prompts, set expectations and ask a report back from the CLI ai on what was done.
You are continuing work on Cat-Scan, a privacy-first QPS optimization platform 
for Google Authorized Buyers. 

Key files to read:
- /mnt/user-data/uploads/README.md (project overview)
- /mnt/user-data/uploads/CatScan_Handover_v10.md (this document)

Current state: Unified data architecture COMPLETE and working.
Database: ~/.catscan/catscan.db (SQLite)
Project path: Use relative paths from project root
```

---

## What is Cat-Scan?

A **free tool** for DSPs and performance bidders distributed as a marketing trojan horse to gain introductions and establish trust as RTB experts. Must be:
- **Professional quality** - production-ready
- **Easy to install** - minimal setup
- **Privacy-first** - runs entirely on user's infrastructure

### Core Value Proposition

Helps users eliminate 20-40% of wasted QPS by identifying:
1. **Size mismatch** - Receiving bid requests for sizes you have no creatives for
2. **Config inefficiency** - Pretargeting configs with poor performance
3. **Fraud signals** - Suspicious patterns for human review

---

## Current Architecture (v10.2)

### Single Source of Truth

```
CSV Export → Validator → performance_data → Query-time aggregation
                              ↓
                 Size Coverage | Config Perf | Fraud Detection
```

### Database Schema

**Main table: `performance_data`**

```sql
-- Required columns (import fails without these)
metric_date DATE NOT NULL
creative_id TEXT          -- Links to creatives table
billing_id TEXT           -- Pretargeting config
creative_size TEXT        -- "300x250", "Interstitial", etc.
reached_queries INTEGER   -- THE critical waste metric
impressions INTEGER

-- Optional dimensions (imported if present)
creative_format, country, platform, environment
app_id, app_name, publisher_id, publisher_name, publisher_domain
deal_id, deal_name, transaction_type
advertiser, buyer_account_id, buyer_account_name

-- Optional metrics
clicks, spend_micros
video_starts, video_completions, vast_errors, etc.

-- Deduplication
row_hash TEXT UNIQUE

-- Tracking
import_batch_id TEXT, imported_at TIMESTAMP
```

**Supporting tables:**
- `creatives` - Synced from Google RTB API
- `fraud_signals` - Detected patterns for review
- `import_history` - Track imports

---

## Import Options (Both Working)

### CLI (Recommended for large files)
```bash
cd creative-intelligence
source venv/bin/activate
python cli/qps_analyzer.py validate /path/to/export.csv
python cli/qps_analyzer.py import /path/to/export.csv
```

### Dashboard UI
http://localhost:3000/import - supports chunked uploads for large files

---

## Required CSV Columns

| Column | Maps To | Why Required |
|--------|---------|--------------|
| Day / #Day | metric_date | Time dimension |
| Creative ID | creative_id | Links to inventory |
| Billing ID | billing_id | Config tracking |
| Creative size | creative_size | QPS coverage |
| Reached queries | reached_queries | THE waste metric |
| Impressions | impressions | Basic performance |

---

## CLI Commands

```bash
cd creative-intelligence
source venv/bin/activate

python cli/qps_analyzer.py validate /path/to/file.csv
python cli/qps_analyzer.py import /path/to/file.csv
python cli/qps_analyzer.py summary
python cli/qps_analyzer.py coverage --days 7
python cli/qps_analyzer.py configs --days 7
python cli/qps_analyzer.py fraud --days 14
python cli/qps_analyzer.py include-list
python cli/qps_analyzer.py full-report --days 7
```

---

## Critical Domain Knowledge

### Size Filtering is INCLUDE-ONLY
- Empty size list = Accept ALL sizes
- Add ONE size = ONLY that size (all others EXCLUDED)
- NO "exclude" option exists

### Fraud Detection Approach
Cat-Scan FLAGS patterns for human review. Does NOT definitively identify fraud.

**Key Principle:** Patterns over time matter, not single anomalies.

**Signals detected (no fixed thresholds):**
- Clicks > Impressions frequently
- Zero engagement over 7+ days
- Suspiciously consistent metrics
- Video starts with zero completions
- High VAST error rates

**Context matters:** What's suspicious for one campaign may be normal for another.

---

## Endpoint Configuration

Configure in `qps/constants.py`:
```python
ENDPOINTS = [
    {"name": "Region 1", "url": "your-url-1", "qps_limit": 10000},
    {"name": "Region 2", "url": "your-url-2", "qps_limit": 30000},
]
```

---

## Known Issues

| Issue | Status |
|-------|--------|
| Seat dropdown shows 0 | Closed |

---

## Services

```bash
sudo systemctl status catscan-api
cd dashboard && npm run dev
```

---

## Files for New Chat

- README.md
- CatScan_Handover_v10.md
- RTB_FRAUD_SIGNALS_REFERENCE.md (optional)

---

**Version:** 10.2  
**Last Updated:** December 1, 2025