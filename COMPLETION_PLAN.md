# Cat-Scan Platform Completion Plan

**Created:** January 4, 2026
**Updated:** January 6, 2026
**Status:** Active Development

---

## Executive Summary

Cat-Scan is a QPS optimization platform for Google Authorized Buyers. The codebase has **118 API endpoints**, **17+ dashboard pages**, and **41 database tables**. The app is deployed at `scan.rtb.cat` on AWS.

This plan addresses:
1. **Documentation accuracy** - Update README and docs to reflect actual state
2. **Missing local dev scripts** - Create setup.sh and run.sh
3. **Paid feature roadmap** - Document the automated configuration feature for open source
4. **Data science documentation** - Document available metrics and analyses

---

## Part 1: Feature Development

### 1.1 Creative Geo Display (High Priority)

**Problem:** Creatives can have localization mismatches (Spanish text in German market) that go unnoticed.

**Solution:** Add "Serving Countries" section to creative detail modal showing where creative actually serves with spend breakdown.

**Details:** See [PLAN_CREATIVE_GEO_DISPLAY.md](./PLAN_CREATIVE_GEO_DISPLAY.md)

| Component | Change |
|-----------|--------|
| Backend | New endpoint `GET /creatives/{id}/countries` |
| Frontend | New section in `preview-modal.tsx` |
| Data | Already exists in `rtb_daily` table |

**Estimate:** ~235 lines of code

### 1.2 Navigation Reorganization (Medium Priority)

**Problem:** Current navigation doesn't reflect Cat-Scan's purpose as a QPS optimization tool. "Waste Optimizer" is confusing, Pretargeting is buried.

**Solution:** Restructure navigation around user tasks: Monitor → Optimize → Configure.

**Details:** See [NAVIGATION_REORGANIZATION_PLAN.md](./NAVIGATION_REORGANIZATION_PLAN.md)

| Current | Proposed |
|---------|----------|
| Waste Optimizer | QPS Dashboard |
| (buried) | Pretargeting |
| Creatives | Creatives |
| Campaigns | (demoted) |
| Change History | (moved to Pretargeting) |
| Import | Import |
| Setup | Settings |

### 1.3 Auto-Optimization (Paid Feature)

**Problem:** Manual pretargeting adjustments are time-consuming and reactive.

**Solution:** Automatically adjust pretargeting when new creatives are approved.

**Details:** See [DATA_SCIENCE_EVALUATION.md](./DATA_SCIENCE_EVALUATION.md) Part 9

**Two-tier approach:**
1. **Proactive (API-driven):** When creative approved → add size to pretargeting
2. **Reactive (CSV-driven):** Block bad publishers/geos based on performance

| Component | Status |
|-----------|--------|
| Creative sync | ✅ Complete |
| Pretargeting API | ✅ Complete |
| Trigger on approval | ❌ Missing |
| Auto-apply | ❌ Missing |
| Outcome tracking | ⚠️ Partial |

---

## Part 2: Documentation Updates

### 2.1 README.md Overhaul

**Current issues with "(in question)" sections:**

| Section | Issue | Fix |
|---------|-------|-----|
| Quick Start | References non-existent scripts | Create `setup.sh`/`run.sh` |
| Dashboard Pages | Lists 6 pages | Update to 17+ pages |
| Database Schema | Shows 6 tables | Reference DATA_MODEL.md |
| CSV Format | Says 3 reports | Update to 5 report types |
| API Endpoints | Lists ~7 | Reference /docs for 118 endpoints |
| Project Status | Says "Next: deployment" | Update - already deployed |

### 2.2 New Documentation

| Document | Purpose | Status |
|----------|---------|--------|
| DATA_MODEL.md | Full 41-table schema | ✅ Exists |
| DATA_SCIENCE_EVALUATION.md | Metrics & optimization analysis | ✅ Exists |
| CSV_REPORTS_GUIDE.md | Report setup instructions | ✅ Exists |
| ARCHITECTURE.md | System architecture | ❌ Needed |
| MCP_INTEGRATION.md | AI tool integration | ❌ Needed |

---

## Part 3: Development Scripts

### 3.1 Create setup.sh

```bash
#!/bin/bash
set -e
echo "=== Cat-Scan Setup ==="

# Python
python3 -m venv venv
./venv/bin/pip install -r requirements.txt

# Node
cd dashboard && npm install && cd ..

# Database
./venv/bin/python -c "from storage.sqlite_store import SQLiteStore; SQLiteStore()"

echo "=== Setup Complete. Run ./run.sh ==="
```

### 3.2 Create run.sh

```bash
#!/bin/bash
set -e
echo "=== Starting Cat-Scan ==="

./venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 &
cd dashboard && npm run dev &

echo "Dashboard: http://localhost:3000"
echo "API: http://localhost:8000"
wait
```

---

## Part 3: Paid Feature - Automated Configuration

### 3.1 Current State

The README describes the paid feature as:
> "a paid-for upgrade that adjusts Pretargeting settings based on new creatives that get uploaded and approved to the Google AB seat, so it is effectively hands-free"

- [ ] Create `setup.sh` and `run.sh`
- [ ] Update README.md "(in question)" sections
- [ ] Implement Creative Geo Display feature

1. **Creative Change Monitoring**
   - Monitor for newly approved creatives via API
   - Compare to current pretargeting configs
   - Initiate optimization workflow

- [ ] Create `/pretargeting` pages
- [ ] Create `/analytics` hub
- [ ] Update sidebar navigation
- [ ] Add route redirects for backwards compatibility
- [ ] Update translations

3. **Automated Update Logic**
   - Apply changes when confidence > threshold
   - Track outcomes for learning
   - Support rollback if performance degrades

4. **Billing Integration** (for paid tier)
   - User subscription management
   - Feature gating for automated updates
   - Usage metering

### Phase 4: Auto-Optimization (1-2 weeks)

- [ ] Implement creative approval trigger
- [ ] Build auto-apply logic with confidence thresholds
- [ ] Add outcome tracking
- [ ] Design billing/subscription system

---

| Phase | Feature | Complexity |
|-------|---------|------------|
| 1 | Creative change monitoring webhook | Low |
| 2 | Automated recommendation generation | Medium |
| 3 | Confidence-based updates | Medium |
| 4 | Learning from outcomes | High |
| 5 | Billing/subscription system | High |

---

## Part 4: Data Science Documentation

### 4.1 Available Data Sources

**From Google RTB API:**
- Creatives (format, size, approval status, URLs)
- Pretargeting configs (geos, formats, platforms, sizes)
- RTB endpoints (QPS limits, trading locations)
- Buyer seats (account hierarchy)

**From CSV Reports (5 types):**

| Report | Key Metrics | Analysis Use |
|--------|-------------|--------------|
| Performance Detail | Reached queries, Impressions, Clicks, Spend | Creative ROI, Size efficiency |
| Funnel (Geo) | Bid requests, Bids, Auctions won | Geo targeting efficiency |
| Funnel (Publishers) | Same + Publisher dimension | Publisher quality scoring |
| Bid Filtering | Filtering reasons, Lost bids | Policy compliance |
| Quality Signals | Non-human traffic rate, Viewability | Traffic quality review |

### 4.2 Available Analyses

| Analysis | Endpoint | Data Science Value |
|----------|----------|-------------------|
| Size Coverage | `/analytics/size-coverage` | Identify inventory gaps |
| Geo Inefficiency | `/analytics/geo-waste` | Optimize geo targeting |
| Publisher Inefficiency | `/analytics/publisher-waste` | Exclusion candidates |
| Traffic Quality | `/analytics/traffic-quality` | Non-human traffic review |
| Platform Efficiency | `/analytics/platform-efficiency` | App vs Web strategy |
| Hourly Patterns | `/analytics/hourly-patterns` | Dayparting optimization |
| Config Performance | `/qps/config-performance` | A/B testing configs |
| Bid Filtering | `/analytics/bid-filtering` | Policy optimization |

### 4.3 Key Metrics for Optimization

| Metric | Formula | Target |
|--------|---------|--------|
| Bid Rate | Bids / Reached Queries | Maximize |
| Win Rate | Auctions Won / Bids in Auction | Optimize by segment |
| Inefficiency Rate | (Reached - Impressions) / Reached | Minimize |
| QPS Efficiency | Impressions / Bid Requests | Maximize |
| Revenue per QPS | Spend / Bid Requests | Maximize |

**Creative Management (3):** creatives, clusters, thumbnail_status

**Campaign Management (5):** campaigns, ai_campaigns, creative_campaigns, campaign_creatives, campaign_daily_summary

### Phase 1: Quick Wins (Day 1)
- [x] Create `setup.sh`
- [x] Create `run.sh`
- [ ] Update README.md "(in question)" sections
- [ ] Commit and push

### Phase 2: Documentation (Days 2-3)
- [ ] Create ARCHITECTURE.md
- [ ] Create MCP_INTEGRATION.md
- [ ] Create METRICS_GUIDE.md
- [ ] Update INSTALL.md for current workflow
- [ ] Merge AWS_DEPLOYMENT.md into docs/

### Phase 3: Verify Deployment (Day 4)
- [ ] Test live app at scan.rtb.cat
- [ ] Verify all endpoints working
- [ ] Test CSV import flow
- [ ] Document any issues found

### Phase 4: Paid Feature Design (Week 2+)
- [ ] Design automated configuration architecture
- [ ] Create feature specification
- [ ] Plan billing integration
- [ ] Create roadmap for implementation

**Pretargeting (7):** pretargeting_configs, pretargeting_history, pretargeting_snapshots, snapshot_comparisons, pretargeting_pending_changes, pretargeting_change_log, rtb_endpoints

## Appendix A: Accurate Dashboard Pages

| Page | URL | Purpose | Status |
|------|-----|---------|--------|
| Home | `/` | Main dashboard with stats | Implemented |
| Login | `/login` | User authentication | Implemented |
| Setup | `/setup` | Initial configuration | Implemented |
| Campaigns | `/campaigns` | Campaign listing | Implemented |
| Campaign Detail | `/campaigns/[id]` | Campaign details & creatives | Implemented |
| Creatives | `/creatives` | Creative browser | Implemented |
| Import | `/import` | CSV upload interface | Implemented |
| Uploads | `/uploads` | Upload tracking | Implemented |
| History | `/history` | Import history | Implemented |
| Waste Analysis | `/waste-analysis` | Waste signal dashboard | Implemented |
| Settings | `/settings` | Settings hub | Implemented |
| Connected Accounts | `/settings/accounts` | API credential setup | Implemented |
| Seats | `/settings/seats` | Buyer seat management | Implemented |
| Retention | `/settings/retention` | Data retention policies | Implemented |
| System Status | `/settings/system` | System diagnostics | Implemented |
| Admin | `/admin` | Admin dashboard | Implemented |
| Users | `/admin/users` | User management | Implemented |
| Configuration | `/admin/configuration` | System settings | Implemented |
| Audit Log | `/admin/audit-log` | Action audit trail | Implemented |

**User Auth (6):** users, user_sessions, user_service_account_permissions, login_attempts, audit_log, system_settings

**Lookup Tables (5):** apps, publishers, geographies, billing_accounts, recommendations

---

## Appendix C: Related Plans

### PLAN_CREATIVE_GEO_DISPLAY.md

Adds country serving data to the creative detail modal:
- Shows all countries where creative served
- Displays spend/impressions per country
- Enables detection of geo/language mismatches
- Foundation for future MCP-based image recognition alerts

### NAVIGATION_REORGANIZATION_PLAN.md

Restructures dashboard navigation:
- Renames "Waste Optimizer" → "QPS Dashboard"
- Promotes Pretargeting to main nav
- Creates Analytics hub
- Consolidates Settings
- Improves discoverability of optimization tools

### DATA_SCIENCE_EVALUATION.md

Comprehensive analysis of optimization capabilities:
- Data model score: 9.5/10
- Identifies chicken-and-egg problem for blocked creatives
- Documents proactive vs reactive optimization approaches
- Lists missing components for auto-optimization

---

*This plan consolidates all Cat-Scan development work. Updated January 6, 2026.*
