# Cat-Scan Claude CLI Prompts

Use these with `claude` in your project directory.

---

## 1. Project Orientation (Start Here)

```bash
claude "You are continuing work on Cat-Scan, a privacy-first QPS optimization platform for Google Authorized Buyers.

Read these files first:
- README.md (project overview)
- docs/CatScan_Handover_v10.md (current state)

Then explore the codebase structure:
- creative-intelligence/ (Python backend, FastAPI, CLI)
- dashboard/ (Next.js frontend)
- Database: ~/.catscan/catscan.db

Current status: Phase 9.6 complete (Unified Data Architecture). Summarize the project state and what you find."
```

---

## 2. Fix Seat Dropdown (Known Bug)

```bash
claude "TASK: Fix the 'Seat dropdown shows 0 creatives' bug.

Context: The dashboard seat dropdown should show 600+ creatives but displays 0.

Investigation steps:
1. Find the seat dropdown component in dashboard/src/
2. Trace the API call it makes to the FastAPI backend
3. Check the API endpoint in creative-intelligence/api/
4. Query the database directly: sqlite3 ~/.catscan/catscan.db 'SELECT COUNT(*) FROM creatives;'
5. Compare what the DB returns vs what the API returns vs what the frontend receives

Identify where the disconnect is and propose a fix."
```

---

## 3. Phase 8.5 - Seat Hierarchy Investigation

```bash
claude "TASK: Investigate seat hierarchy for Phase 8.5.

Context: Cat-Scan needs to properly handle multi-seat accounts in Google Authorized Buyers. Currently seat names display instead of just IDs, and the hierarchy may not be clear.

Steps:
1. Check how 'buyer_account_id' and 'buyer_account_name' are used in performance_data
2. Review the creatives table for seat-related fields
3. Query actual data: sqlite3 ~/.catscan/catscan.db 'SELECT DISTINCT buyer_account_id, buyer_account_name FROM performance_data LIMIT 20;'
4. Document the current seat structure and propose how to improve the hierarchy display"
```

---

## 4. Validate Import Pipeline (Health Check)

```bash
claude "TASK: Verify the CSV import pipeline is working correctly.

Run these commands and report results:

cd creative-intelligence
source venv/bin/activate

# Check CLI help
python cli/qps_analyzer.py --help

# Check database state
python cli/qps_analyzer.py summary

# Verify API is running
curl http://localhost:8000/health
curl http://localhost:8000/docs

Report any issues found."
```

---

## 5. Phase 9.0 - AI Campaign Clustering Prep

```bash
claude "TASK: Prepare for Phase 9.0 - AI Campaign Clustering.

Context: We want to use Claude API to automatically group creatives into meaningful campaigns based on patterns in performance_data.

Steps:
1. Analyze what data is available: sqlite3 ~/.catscan/catscan.db '.schema performance_data'
2. Query sample data showing different creative patterns
3. Identify which columns would be useful for clustering (creative_id, advertiser, creative_size, country, app patterns, etc.)
4. Draft a prompt template that could be sent to Claude API to cluster a batch of creatives
5. Propose a minimal implementation plan"
```

---

## 6. Run Full QPS Report

```bash
claude "Run the full QPS analysis report:

cd creative-intelligence
source venv/bin/activate

python cli/qps_analyzer.py full-report --days 7

Analyze the output and summarize:
- Size coverage gaps (sizes receiving QPS with no creatives)
- Config performance (which billing IDs perform best/worst)
- Any fraud signals detected

Provide actionable recommendations."
```

---

## 7. Debug Mode (When Things Break)

```bash
claude "TASK: Debug Cat-Scan issue.

Current symptoms: [DESCRIBE WHAT'S BROKEN]

Debugging checklist:
1. Check API: sudo systemctl status catscan-api && journalctl -u catscan-api --since '10 minutes ago'
2. Check DB: sqlite3 ~/.catscan/catscan.db 'PRAGMA integrity_check;'
3. Check dashboard: ls dashboard/node_modules (if empty, run npm install)
4. Check ports: sudo lsof -i :8000 && sudo lsof -i :3000

Investigate and fix."
```

---

## Quick Reference Commands

```bash
# Start fresh session with context
claude "Read README.md and summarize Cat-Scan in 3 sentences, then await instructions."

# Quick database check
claude "Run: sqlite3 ~/.catscan/catscan.db 'SELECT COUNT(*) as creatives FROM creatives; SELECT COUNT(*) as perf_rows FROM performance_data;'"

# Check what's importable
claude "Show me the required CSV columns for Cat-Scan import and explain what each one does."
```
