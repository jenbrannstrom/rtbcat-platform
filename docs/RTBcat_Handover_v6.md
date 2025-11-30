# RTB.cat Creative Intelligence Platform - Handover Document v6

**Date:** November 30, 2025  
**Project:** RTB.cat Creative Intelligence & Performance Analytics Platform  
**Status:** Phase 6 ✅ Complete, Phase 8 🔄 Starting  
**Developer:** Jen (jen@rtb.cat)  
**Latest Updates:** Performance data foundation, opportunity detection architecture

---

## 🎯 Executive Summary

RTB.cat Creative Intelligence has evolved from a creative management tool into a **comprehensive performance analytics and opportunity detection platform**.

**What Changed (v5 → v6):**
1. **Strategic Pivot:** Focus on performance-driven insights, not just creative cataloging
2. **Roadmap Refocus:** Deferred privacy modularization (Phase 7) to prioritize revenue features
3. **Core Value Proposition:** Find profit pockets and eliminate waste through AI-powered analysis
4. **Database Expansion:** Adding performance metrics table (millions of records)
5. **New Revenue Model:** Open source core + proprietary analytics (open core strategy)

**Current State:**
- ✅ 652 creatives collected and normalized
- ✅ Smart URL parsing and app store detection
- ✅ Waste analysis with recommendations
- ✅ Professional dashboard with virtual scrolling
- 🔄 **NEW:** Performance data foundation (Phase 8 in progress)
- 📋 **NEXT:** AI opportunity detection, geographic intelligence

---

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [What's New in v6](#whats-new-in-v6)
3. [Updated System Architecture](#updated-system-architecture)
4. [Phase 8: Performance Data Foundation](#phase-8-performance-data-foundation)
5. [Phase 9-12: Advanced Features Roadmap](#phase-9-12-advanced-features-roadmap)
6. [Database Schema Updates](#database-schema-updates)
7. [API Endpoints (Updated)](#api-endpoints-updated)
8. [Open Core Strategy](#open-core-strategy)
9. [Development Workflow](#development-workflow)
10. [Management Instructions](#management-instructions)

---

## 🚀 Quick Start

### System Status

```bash
# Check what's running
ps aux | grep -E "uvicorn|npm"

# Backend (should be on port 8000)
cd /home/jen/Documents/rtbcat-platform/creative-intelligence
source venv/bin/activate
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (should be on port 3000 or 3001)
cd /home/jen/Documents/rtbcat-platform/dashboard
npm run dev

# Access
Dashboard: http://localhost:3000
API Docs: http://localhost:8000/docs
Database: ~/.rtbcat/rtbcat.db
```

### Current Data State

```bash
# Check database
sqlite3 ~/.rtbcat/rtbcat.db

.tables
# Should show: creatives, campaigns, buyer_seats, rtb_traffic
# After Phase 8: performance_metrics

SELECT COUNT(*) FROM creatives;
# Should show: 652

SELECT COUNT(*) FROM buyer_seats;
# Should show: 1-2 buyer accounts

# Exit
.exit
```

---

## 🆕 What's New in v6

### **1. Strategic Pivot: Performance-First**

**Old Focus (v1-v5):**
- Creative cataloging
- Size normalization
- Basic waste analysis
- Privacy-first architecture

**New Focus (v6+):**
- **Performance analytics** (spend, CPC, CPM)
- **Opportunity detection** (find profit pockets)
- **AI-powered insights** (geographic intelligence)
- **Campaign optimization** (what's working, what's not)

**Why the change:**
- Creative management alone is commodity (copycats can build in 2 weeks with AI)
- **Performance intelligence** is the differentiator (requires data, AI, domain expertise)
- DSPs don't just want to see creatives - they want to **know what's profitable**

---

### **2. Roadmap Reordering**

**Original Plan:**
```
Phase 6 → Phase 7 (Privacy/Modularization) → Phase 8 (AI Clustering) → Phase 9+ (Advanced)
```

**New Plan:**
```
Phase 6 ✅ → Phase 8 (Performance Data) 🔄 → Phase 9 (AI Clustering) → Phase 10 (Opportunities) → Phase 7 (Privacy/Modularization) 📋
```

**Rationale:**
- Need to **use all features locally** before modularizing
- Performance data is **blocking** for AI clustering and opportunity detection
- Privacy modularization can wait until product is proven
- Revenue features take priority over open-sourcing

---

### **3. Open Core Business Model**

**Community Edition (FREE, Open Source):**
- Creative fetching
- Size normalization
- Basic waste analysis
- Manual CSV export

**Pro Edition ($2,499/year, Proprietary):**
- ✅ Performance data import
- ✅ Sort by spend
- ✅ AI campaign clustering
- ✅ Opportunity detection
- ✅ Geographic insights (basic)

**Enterprise Edition ($15k-50k/year, Proprietary):**
- ✅ Cross-campaign pattern detection
- ✅ Predictive analytics
- ✅ Custom AI prompts
- ✅ BigQuery/Snowflake connectors
- ✅ Real-time streaming
- ✅ White-label UI

**Why Open Core:**
- **Trojan horse:** Open source gets us into secure client environments
- **Trust:** Security teams can audit the code
- **Revenue:** Upsell proprietary features after deployment
- **Defensibility:** Community can copy code, but not expertise/data/AI

---

### **4. New Core Features**

#### **A. Performance Tracking**
```
Before: Creatives sorted by ID (useless)
After:  Creatives sorted by spend (actionable)

Creative Card:
  [Thumbnail]
  ID: 79783
  💰 Spend (7d): $1,234
  📊 CPC: $0.45  CPM: $2.20
  🌍 Top Geo: Brazil
```

#### **B. Opportunity Detection**
```
Find profit pockets that bidder optimization missed:

Opportunity 1: Undervalued Geography
  Campaign: "Puzzle Game Brazil"
  Finding: Angola has CPC $0.30 (40% better than avg $0.50)
  Current: Only $200/week spend
  Recommendation: Scale to $1,000/week
  Potential savings: $400/week

Opportunity 2: High-CPC Low-Spend
  Campaign: "Finance Vertical Video"
  Finding: Best CPC in portfolio ($0.20)
  Current: Only $500/week (neglected by optimizer)
  Recommendation: Scale to $5,000/week
  Potential profit: +$4,500 weekly spend at superior CPC
```

#### **C. Geographic Intelligence (Enterprise)**
```
Cross-campaign pattern detection:

Pattern: Puzzle games perform 4x better in Brazil vs Ireland
  Brazil CPC: $0.30
  Ireland CPC: $1.20
  Recommendation: Stop Irish traffic for puzzle genre
  Potential savings: $500/week
```

---

## 🏗️ Updated System Architecture

### High-Level Diagram

```
┌─────────────────────────────────────────────────────────┐
│         Next.js Dashboard (Port 3000/3001)              │
│  Location: /dashboard/                                  │
│                                                          │
│  ✅ Creatives Viewer (sort by spend, performance badges)│
│  ✅ Waste Analysis Dashboard                            │
│  ✅ Campaigns Page (AI-clustered)                       │
│  🔄 Opportunity Dashboard (NEW - Phase 10)              │
│  📋 Performance Import UI (NEW - Phase 8)               │
└─────────────────────────────────────────────────────────┘
                          │
                          │ HTTP/JSON
                          ▼
┌─────────────────────────────────────────────────────────┐
│    Creative Intelligence Backend (Port 8000)            │
│    Location: /creative-intelligence/                    │
│    Language: Python 3.12 + FastAPI                      │
│                                                          │
│  Existing Endpoints:                                    │
│  ✅ GET  /creatives (with slim mode)                    │
│  ✅ GET  /creatives/{id}                                │
│  ✅ GET  /analytics/waste                               │
│  ✅ GET  /seats (buyer account management)              │
│                                                          │
│  NEW Endpoints (Phase 8):                               │
│  🔄 POST /api/performance/import (CSV upload)           │
│  🔄 GET  /api/performance/metrics/{creative_id}         │
│  🔄 GET  /creatives?sort=spend&period=7d                │
│                                                          │
│  Future Endpoints (Phase 9-10):                         │
│  📋 POST /campaigns/cluster (AI clustering)             │
│  📋 GET  /opportunities (detect profit pockets)         │
│  📋 GET  /insights/geographic (cross-campaign patterns) │
└─────────────────────────────────────────────────────────┘
                          │
         ┌────────────────┴────────────────┐
         ▼                                 ▼
┌──────────────────────┐        ┌──────────────────────┐
│ SQLite Database      │        │ Google Authorized    │
│ ~/.rtbcat/rtbcat.db  │        │ Buyers API           │
│                      │        │                      │
│ Existing Tables:     │        │ - Creatives          │
│  • creatives (652)   │        │ - Pretargeting       │
│  • campaigns         │        │ - Buyers.list        │
│  • buyer_seats       │        │                      │
│  • rtb_traffic       │        └──────────────────────┘
│                      │
│ NEW Tables (Phase 8):│
│  • performance_      │
│    metrics (millions)│
│  • opportunities     │
│    (Phase 10)        │
└──────────────────────┘
         │
         ▼
┌──────────────────────┐
│ AI Services          │
│ (Phase 9+)           │
│                      │
│ • Claude API         │
│ • Google Gemini      │
│ • Rule-based fallback│
└──────────────────────┘
```

---

## 📊 Phase 8: Performance Data Foundation

**Status:** 🔄 In Progress  
**Priority:** CRITICAL - Blocks all advanced features  
**ETA:** Week 1-2

### Overview

Performance data (spend, clicks, impressions, CPM, CPC) is the **foundation** for:
- Sorting creatives by spend (what's actually working)
- AI opportunity detection (find profit pockets)
- Geographic intelligence (what works where)
- Campaign optimization (ROI analysis)

Without performance data, we only have a creative catalog. With it, we have actionable intelligence.

---

### Phase 8.1: Database Schema Extension

**New Table: `performance_metrics`**

```sql
CREATE TABLE performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creative_id INTEGER REFERENCES creatives(id),
    date DATE NOT NULL,
    hour INTEGER,  -- 0-23 for hourly granularity
    
    -- Performance metrics
    impressions BIGINT DEFAULT 0,
    clicks BIGINT DEFAULT 0,
    spend DECIMAL(12,2) DEFAULT 0,
    cpm DECIMAL(8,4),  -- Calculated: spend / impressions * 1000
    cpc DECIMAL(8,4),  -- Calculated: spend / clicks
    
    -- Dimensions
    geography VARCHAR(2),  -- BR, IE, US, etc.
    device_type VARCHAR(20),  -- mobile, desktop, tablet
    placement VARCHAR(100),
    
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    
    UNIQUE(creative_id, date, hour, geography, device_type)
);

-- Indexes for fast querying
CREATE INDEX idx_perf_creative_date ON performance_metrics(creative_id, date DESC);
CREATE INDEX idx_perf_spend ON performance_metrics(spend DESC);
CREATE INDEX idx_perf_cpc ON performance_metrics(cpc ASC);
```

**Why These Indexes:**
- `creative_id, date DESC` - Fast date range queries for single creative
- `spend DESC` - Sort all creatives by spend
- `cpc ASC` - Find best-performing creatives

**Update `campaigns` Table:**

```sql
ALTER TABLE campaigns ADD COLUMN total_spend_7d DECIMAL(12,2);
ALTER TABLE campaigns ADD COLUMN total_spend_30d DECIMAL(12,2);
ALTER TABLE campaigns ADD COLUMN avg_cpc_7d DECIMAL(8,4);
ALTER TABLE campaigns ADD COLUMN top_geography VARCHAR(2);
```

**Why Cache These:**
- Calculating campaign totals from millions of rows is slow
- Update nightly or after imports
- Fast reads for dashboard display

---

### Phase 8.2: Data Import System

**Multiple Import Methods:**

#### 1. CSV Upload (Manual)
```bash
curl -X POST http://localhost:8000/api/performance/import \
  -F "file=@performance_data.csv"
```

**CSV Format:**
```csv
creative_id,date,impressions,clicks,spend,geography,device_type
79783,2025-11-29,10000,250,125.50,BR,mobile
79783,2025-11-29,5000,100,80.00,BR,desktop
144634,2025-11-29,50000,800,200.00,US,mobile
```

**Validation:**
- creative_id exists
- date not in future
- clicks <= impressions
- spend, clicks, impressions >= 0
- Duplicate detection (UPSERT on conflict)

#### 2. S3 Bucket Sync (Automated - Future)
```
Customer drops CSV/JSON in S3 bucket
→ Lambda triggers on new file
→ Import to database
→ Update campaign aggregates
```

#### 3. BigQuery Connector (Enterprise - Future)
```python
# Scheduled query from customer's BigQuery
SELECT creative_id, date, SUM(impressions), SUM(clicks), SUM(spend)
FROM bidder_logs
WHERE date >= CURRENT_DATE - 7
GROUP BY creative_id, date
```

---

### Phase 8.3: Creatives Page Enhancement

**Before:**
```
Cards sorted by creative_id (useless)
No performance data shown
```

**After:**
```
┌─────────────────────────────────┐
│  [Creative Thumbnail]           │
│                                 │
│  79783                          │  ← Creative ID
│  Google Auth. Buyers →          │  ← Clickable link
│                                 │
│  💰 Spend (7d): $1,234          │  ← NEW
│  📊 CPC: $0.45  CPM: $2.20      │  ← NEW
│  🌍 Top Geo: Brazil (60%)       │  ← NEW
│  📈 +15% vs last week           │  ← NEW (trend)
│                                 │
│  [View Details]                 │
└─────────────────────────────────┘

Sort by: [Spend (7d) ▼]
Filter: [All Formats] [All Geos] [Performance: High/Med/Low]
```

**Sorting Options:**
- Yesterday
- Last 7 days (default)
- Last 30 days
- All time

**Performance Tiers:**
- High spend: Top 25% by spend
- Medium spend: 25-75%
- Low spend: Bottom 25%
- Zero spend: No performance data

---

### Phase 8.4: Campaign Performance Aggregation

**Aggregate creative-level data to campaign-level:**

```python
# Example
Campaign: "Mobile Game - Puzzle - Brazil Portuguese"
  Creatives: 15

  Performance (7d):
    Total Spend: $2,500
    Impressions: 5M
    Clicks: 5,000
    Avg CPC: $0.50
    
  Geographic Breakdown:
    Brazil:   $2,000 (80%), CPC $0.45
    Portugal: $300 (12%),  CPC $0.55
    Angola:   $200 (8%),   CPC $0.30  ← Opportunity!
    
  Top Creative: #79783 ($800/week, CPC $0.40)
```

**Update Schedule:**
- Real-time: After CSV import
- Nightly: Recalculate all campaigns (cronjob)
- On-demand: "Refresh" button in UI

---

## 🎯 Phase 9-12: Advanced Features Roadmap

### Phase 9: AI Campaign Clustering (Week 3-4)

**Cluster creatives into campaigns using AI:**

```
Input: 652 creatives with metadata
AI Provider: Claude, Gemini, or rule-based

Output: 15-20 campaigns
  Campaign 1: "Mobile Game - Puzzle - Brazil Portuguese"
    - Creative 101, 205, 387
    - Confidence: 95%
  
  Campaign 2: "Finance App - Vertical Video - US English"
    - Creative 422, 501
    - Confidence: 88%
```

**AI Prompt Structure:**
```
"Analyze these creatives and group them into campaigns.
Consider: visual similarity, language, product, geography.
Return JSON with campaign names and creative IDs."

Creatives: [
  {id: 101, format: "HTML", size: "300x250", language: "pt_br", ...},
  {id: 205, format: "VIDEO", size: "16:9", language: "pt_br", ...},
  ...
]

Expected output: {campaigns: [...]}
```

**Pricing:** Pro tier ($2,499/year)

---

### Phase 10: Opportunity Detection (Week 5-6)

**The Core Value Proposition**

Find profit pockets that bidder optimization missed.

**Algorithm:**

```python
# Pseudocode
for campaign in campaigns:
    avg_cpc = campaign.total_spend / campaign.total_clicks
    
    # Find undervalued geographies
    for geo in campaign.geos:
        if geo.cpc < avg_cpc * 0.8 and geo.spend < total_spend * 0.05:
            create_opportunity(
                type="undervalued_geo",
                current_cpc=geo.cpc,
                avg_cpc=avg_cpc,
                current_spend=geo.spend,
                recommendation=f"Scale {geo.country} from ${geo.spend} to ${recommended}",
                potential_savings=calculate_savings(...)
            )
```

**Opportunity Types:**

1. **Undervalued Geography**
   - CPC >20% better than average
   - But <5% of total spend
   - Recommendation: Scale spend in this geo

2. **High-CPC Low-Spend Campaign**
   - Top quartile CPC (efficient)
   - Bottom quartile spend (neglected)
   - Recommendation: Increase budget

3. **Size/Format Gap**
   - Missing a size that performs well in similar campaigns
   - Recommendation: Create creative in this size

4. **Neglected Creative**
   - Excellent CPC but minimal impressions
   - Recommendation: Check pretargeting/bid

**Opportunity Dashboard:**

```
Spreadsheet-style grid:

Campaign      | Insight              | Current | Potential | Action
(thumbnail)   |                      | CPC     | Savings   |
──────────────┼──────────────────────┼─────────┼───────────┼────────
[img] Puzzle  | Undervalued Geo:     | $0.30   | $400/wk   | [Scale]
Game Brazil   | Angola 40% better    |         |           |
──────────────┼──────────────────────┼─────────┼───────────┼────────
[img] Finance | High-CPC Low-Spend:  | $0.20   | $900/wk   | [Scale]
Vertical Vid  | Best CPC, neglected  |         |           |
──────────────┼──────────────────────┼─────────┼───────────┼────────
[img] Fashion | Size Gap: 728x90     | $0.42   | $270/wk   | [Add]
E-commerce    | 30% lower CPC        | (est.)  |           |Creative
```

**Export to CSV** for manual execution.

**Pricing:** Pro tier ($2,499/year)

---

### Phase 11: Geographic Intelligence (Quarter 2 2026)

**Cross-Campaign Pattern Detection**

AI analyzes ALL campaigns to find patterns:

```
Pattern: Puzzle games perform 4x better in Brazil vs Ireland

Data:
  Campaign A (Puzzle): Brazil $0.30, Ireland $1.20
  Campaign B (Puzzle): Brazil $0.35, Ireland $1.15
  Campaign C (Strategy): Brazil $0.50, Ireland $0.45

Insight: Puzzle genre specifically underperforms in Ireland
Recommendation: Stop Irish traffic for puzzle games
Potential savings: $500/week
```

**Segment Performance Matrix:**

```
           │ Brazil │ Ireland │ India │ USA
───────────┼────────┼─────────┼───────┼─────
Puzzle     │ $0.30  │ $1.20   │ $0.40 │ $0.80
Strategy   │ $0.50  │ $0.45   │ $0.60 │ $0.55
Casino     │ $0.20  │ $0.95   │ $0.25 │ $0.70
Finance    │ $0.80  │ $0.60   │ $0.90 │ $0.50
```

**Custom AI Queries:**

Users can define custom analyses:
- "Find campaigns where iOS CPC > Android CPC by >50%"
- "Show creatives with >2% CTR in Tier 3 countries"
- "Which creative styles work best on weekends?"

**Pricing:** Enterprise tier ($15k-50k/year)

---

### Phase 12: Real-Time & Automation (Quarter 3 2026)

**12.1: Live Data Connectors**
- BigQuery streaming (hourly updates)
- Snowflake connector
- Kafka/Kinesis integration

**12.2: Alerting**
- Slack/Email when CPC spikes >20%
- Alert when spend drops >50%
- Alert when new opportunity detected

**12.3: Pretargeting Automation (⚠️ High Liability)**

**The ONLY Destructive Feature:**

```
Risk: Auto-applying pretargeting changes can kill QPS
Recovery: ~1 hour manual fix
Lost revenue: Varies by customer
```

**Safeguards:**

1. **Dry-Run Mode (Default)**
   - Show what WOULD change
   - Require explicit approval
   - No auto-execution

2. **Backup & Rollback**
   - Save current config before changes
   - One-click rollback button
   - Auto-rollback if QPS drops >50%

3. **Gradual Rollout**
   - Apply to 10% of traffic
   - Monitor for 1 hour
   - If stable → 50% → 100%
   - Auto-rollback on issues

4. **Liability Protection**
   - Customer liability waiver
   - Warning: "May impact QPS"
   - Optional insurance ($10k/year, $100k coverage)

**Pricing:** Enterprise + optional insurance

---

## 🗄️ Database Schema Updates

### Current Schema (Phase 1-6)

```sql
-- Creatives
CREATE TABLE creatives (
    id INTEGER PRIMARY KEY,
    buyer_id TEXT,
    creative_id TEXT,
    format TEXT,  -- HTML, VIDEO, NATIVE
    width INTEGER,
    height INTEGER,
    canonical_size TEXT,
    size_category TEXT,
    declared_click_urls TEXT,
    destination_urls_parsed TEXT,  -- NEW in Phase 6
    google_buyers_url TEXT,  -- NEW in Phase 6
    html_snippet TEXT,
    vast_xml TEXT,
    creative_attributes TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Campaigns
CREATE TABLE campaigns (
    id INTEGER PRIMARY KEY,
    campaign_name TEXT,
    creative_ids TEXT,  -- JSON array
    confidence_score REAL,
    ai_provider TEXT,
    created_at TIMESTAMP
);

-- Buyer Seats
CREATE TABLE buyer_seats (
    buyer_id TEXT PRIMARY KEY,
    display_name TEXT,
    bidder_account_id TEXT,
    creative_count INTEGER,
    last_sync TIMESTAMP
);

-- RTB Traffic (for waste analysis)
CREATE TABLE rtb_traffic (
    id INTEGER PRIMARY KEY,
    timestamp TIMESTAMP,
    size TEXT,
    format TEXT,
    geo TEXT,
    device_type TEXT,
    qps REAL
);
```

---

### NEW Schema (Phase 8+)

```sql
-- Performance Metrics (NEW)
CREATE TABLE performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creative_id INTEGER REFERENCES creatives(id),
    date DATE NOT NULL,
    hour INTEGER CHECK (hour >= 0 AND hour <= 23),
    
    -- Metrics
    impressions BIGINT DEFAULT 0,
    clicks BIGINT DEFAULT 0,
    spend DECIMAL(12,2) DEFAULT 0,
    cpm DECIMAL(8,4),
    cpc DECIMAL(8,4),
    
    -- Dimensions
    geography VARCHAR(2),
    device_type VARCHAR(20),
    placement VARCHAR(100),
    
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    
    UNIQUE(creative_id, date, hour, geography, device_type)
);

-- Indexes
CREATE INDEX idx_perf_creative_date ON performance_metrics(creative_id, date DESC);
CREATE INDEX idx_perf_geo_date ON performance_metrics(geography, date DESC);
CREATE INDEX idx_perf_spend ON performance_metrics(spend DESC);
CREATE INDEX idx_perf_cpc ON performance_metrics(cpc ASC);

-- Opportunities (Phase 10)
CREATE TABLE opportunities (
    id INTEGER PRIMARY KEY,
    campaign_id INTEGER REFERENCES campaigns(id),
    insight_type TEXT,  -- undervalued_geo, high_cpc_low_spend, size_gap, etc.
    
    -- Current state
    current_metric_name TEXT,  -- "CPC", "Spend", etc.
    current_metric_value REAL,
    
    -- Recommendation
    recommendation TEXT,
    potential_savings_weekly REAL,
    confidence_score REAL,
    
    -- Supporting data
    geography TEXT,
    device_type TEXT,
    size TEXT,
    
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Update campaigns table
ALTER TABLE campaigns ADD COLUMN total_spend_7d DECIMAL(12,2) DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN total_spend_30d DECIMAL(12,2) DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN total_spend_all_time DECIMAL(12,2) DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN avg_cpc_7d DECIMAL(8,4);
ALTER TABLE campaigns ADD COLUMN avg_cpm_7d DECIMAL(8,4);
ALTER TABLE campaigns ADD COLUMN top_geography VARCHAR(2);
ALTER TABLE campaigns ADD COLUMN top_device_type VARCHAR(20);
ALTER TABLE campaigns ADD COLUMN last_performance_update TIMESTAMP;
```

---

## 🔌 API Endpoints (Updated)

### Existing Endpoints (Working)

**System:**
- `GET /health` - Health check
- `GET /stats` - Aggregate statistics
- `GET /sizes` - Available creative sizes

**Creatives:**
- `GET /creatives?slim=true` - List creatives (slim mode, 26x faster)
- `GET /creatives/{id}` - Get single creative
- `GET /creatives/cluster` - Get clustering suggestions (placeholder)

**Campaigns:**
- `GET /campaigns` - List campaigns
- `GET /campaigns/{id}` - Get campaign details

**Buyer Seats:**
- `GET /seats` - List buyer accounts
- `POST /seats/discover` - Discover seats from Google API
- `POST /seats/{buyer_id}/sync` - Sync creatives

**Analytics:**
- `GET /analytics/waste?buyer_id={id}&days=7` - Waste analysis
- `GET /analytics/size-coverage` - Size coverage data

---

### NEW Endpoints (Phase 8)

**Performance Data:**
- `POST /api/performance/import` - Upload CSV file
  - Accepts: multipart/form-data
  - Returns: {imported: X, skipped: Y, errors: [...]}
  
- `GET /api/performance/metrics/{creative_id}` - Get performance for creative
  - Query params: start_date, end_date, geography
  - Returns: Array of performance records

- `GET /creatives?sort=spend&period=7d` - Sort by spend
  - Params: sort={id|spend|cpc|cpm}, period={1d|7d|30d|all}
  - Returns: Creatives with performance data included

---

### Future Endpoints (Phase 9-10)

**AI Clustering:**
- `POST /campaigns/cluster` - Trigger AI clustering
  - Body: {ai_provider: "claude"|"gemini"|"rule-based"}
  - Returns: {campaigns: [...], confidence: X}

**Opportunities:**
- `GET /opportunities` - List detected opportunities
  - Query: type, campaign_id, min_savings
  - Returns: Array of opportunities sorted by potential savings

- `GET /opportunities/{id}` - Get opportunity details
  - Returns: Full opportunity with supporting data

**Geographic Insights:**
- `GET /insights/geographic` - Cross-campaign patterns
  - Returns: Segment performance matrix + insights

---

## 🎯 Open Core Strategy

### Why Open Core?

**Problem:** If we open source everything, copycats can clone in 2 weeks.

**Solution:** Open the foundation, keep the intelligence proprietary.

---

### What's Open Source (Community Edition - FREE)

```
GitHub: github.com/rtbcat/creative-intel
License: MIT

Features:
✓ Google Authorized Buyers API integration
✓ Creative fetching and parsing
✓ Size normalization
✓ Basic waste analysis
✓ SQLite storage
✓ Basic web UI
✓ Multi-seat support
✓ Manual CSV export
```

**Purpose:**
- **Trojan horse:** Get into client environments (security audit pass)
- **Trust:** Open source = auditable = trustworthy
- **Community:** Free R&D from contributors
- **Marketing:** GitHub stars, tutorials, ecosystem

---

### What's Proprietary (Pro/Enterprise - PAID)

```
Private repos
License-gated features

Pro ($2,499/year):
💰 Performance data import
💰 Sort by spend
💰 AI campaign clustering (Claude/Gemini)
💰 Opportunity detection
💰 Geographic insights (basic)
💰 S3 bucket sync

Enterprise ($15k-50k/year):
💰💰 Cross-campaign pattern detection
💰💰 Predictive analytics
💰💰 Custom AI prompts
💰💰 BigQuery/Snowflake connectors
💰💰 Real-time streaming
💰💰 White-label UI
💰💰 Pretargeting automation (with insurance)
```

**Purpose:**
- **Revenue:** Recurring income from support + features
- **Defensibility:** Copycats get commodity, we keep intelligence
- **Upsell:** Free gets us in, paid keeps us there

---

### Competitive Moat

**What copycats can steal:**
- ✓ Basic code (it's open source)
- ✓ Database schema
- ✓ API structure

**What they CANNOT steal:**
- ✗ AI clustering prompts (proprietary, refined over time)
- ✗ Opportunity detection algorithms (proprietary)
- ✗ Customer data (stays in customer's infrastructure)
- ✗ Brand trust ("RTBcat" trademark)
- ✗ Customer relationships
- ✗ Domain expertise (AdTech, RTB, Google API nuances)
- ✗ AWS Marketplace presence (takes months to get listed)
- ✗ Security audit reports (Trail of Bits, $30k)

**First-Mover Advantage:**
- We launch first
- We get the customers
- We become the "original"
- Copycats are "the knockoff"

---

## 🔧 Development Workflow

### Current Setup (Local Development)

**Backend:**
```bash
cd /home/jen/Documents/rtbcat-platform/creative-intelligence

# Activate venv
source venv/bin/activate

# Run backend
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Access API docs
open http://localhost:8000/docs
```

**Frontend:**
```bash
cd /home/jen/Documents/rtbcat-platform/dashboard

# Install dependencies (if needed)
npm install

# Run dev server
npm run dev

# Access dashboard
open http://localhost:3000
```

**Database:**
```bash
# Location
~/.rtbcat/rtbcat.db

# Inspect
sqlite3 ~/.rtbcat/rtbcat.db

# Backup
cp ~/.rtbcat/rtbcat.db ~/.rtbcat/rtbcat_backup_$(date +%Y%m%d).db
```

---

### Phase 8 Workflow

**Step 1: Run Migration**
```bash
cd creative-intelligence

# Create migration file
# storage/migrations/008_add_performance_metrics.py

# Run migration
python -m storage.migrations.run

# Verify
sqlite3 ~/.rtbcat/rtbcat.db
.tables
# Should show: performance_metrics
```

**Step 2: Test CSV Import**
```bash
# Create example CSV
cat > test_performance.csv << EOF
creative_id,date,impressions,clicks,spend,geography,device_type
79783,2025-11-29,10000,250,125.50,BR,mobile
79783,2025-11-29,5000,100,80.00,BR,desktop
EOF

# Import via API
curl -X POST http://localhost:8000/api/performance/import \
  -F "file=@test_performance.csv"

# Should return:
# {"imported": 2, "skipped": 0, "errors": []}
```

**Step 3: Verify Import**
```bash
sqlite3 ~/.rtbcat/rtbcat.db

SELECT * FROM performance_metrics WHERE creative_id = 79783;
# Should show 2 rows

SELECT 
    creative_id,
    date,
    SUM(spend) as total_spend,
    SUM(clicks) as total_clicks,
    SUM(spend) / SUM(clicks) as avg_cpc
FROM performance_metrics
WHERE date >= date('now', '-7 days')
GROUP BY creative_id
ORDER BY total_spend DESC
LIMIT 10;
# Should show top spenders
```

**Step 4: Update Frontend**
```bash
cd dashboard

# Update creatives page to show performance data
# src/app/creatives/page.tsx

# Test locally
npm run dev
open http://localhost:3000/creatives

# Should see performance badges on cards
```

---

### Testing Checklist (Phase 8)

**Database:**
- [ ] Migration runs successfully
- [ ] performance_metrics table created
- [ ] Indexes created
- [ ] campaigns table updated with new columns
- [ ] Migration is idempotent (safe to run twice)

**API:**
- [ ] POST /api/performance/import accepts CSV
- [ ] Validation catches bad data (negative values, future dates)
- [ ] Duplicate detection works (UPSERT on conflict)
- [ ] GET /api/performance/metrics/{id} returns data
- [ ] GET /creatives?sort=spend&period=7d works

**Frontend:**
- [ ] Creatives page shows performance badges
- [ ] Sort by spend works
- [ ] Date range selector works
- [ ] Performance data loads without errors
- [ ] Virtual scrolling still smooth with performance data

**Performance:**
- [ ] Import 10,000 rows completes in <2 minutes
- [ ] Query performance metrics for creative in <100ms
- [ ] Sort 652 creatives by spend in <100ms
- [ ] Page load with performance data in <1 second

---

## 👨‍💼 Management Instructions

### For Managing Claude Instances

You're managing **two Claude instances:**

1. **Claude CLI** (command-line, backend work)
2. **Claude in VSCode** (UI work, frontend)

**Division of Labor:**

| Task | Assign To | Why |
|------|-----------|-----|
| Database migrations | CLI | File operations, SQL |
| API endpoints | CLI | Backend logic, FastAPI |
| Data validation | CLI | Python business logic |
| CSV parsing | CLI | File handling |
| Frontend UI changes | VSCode | React components |
| Styling/layout | VSCode | Tailwind CSS |
| State management | VSCode | React hooks |
| API integration | VSCode | Fetch calls, error handling |

---

### Current Priority: Phase 8.1

**Assign to Claude CLI:**

1. Create database migration:
   - `storage/migrations/008_add_performance_metrics.py`
   - Support both SQLite and PostgreSQL
   - Create indexes
   - Update campaigns table

2. Create API endpoints:
   - `api/performance.py`
   - POST /api/performance/import (CSV upload)
   - GET /api/performance/metrics/{creative_id}
   - Update `api/main.py` to include router

3. Create example files:
   - `docs/performance_import_example.csv`
   - `docs/PERFORMANCE_DATA_IMPORT.md`

4. Test thoroughly:
   - Import 10,000 rows
   - Verify validation
   - Check duplicate handling
   - Benchmark performance

**Prompt file:** `/mnt/user-data/outputs/PHASE_8_CLI_PROMPT.md`

---

### Next Priority: Phase 8.2-8.3

**Assign to Claude in VSCode:**

1. Update creatives page:
   - Add "Sort by" dropdown (yesterday, 7d, 30d, all-time)
   - Fetch performance data from API
   - Display performance badges on cards
   - Add performance filters (high/med/low spend)

2. Update creative card component:
   - Show spend badge
   - Show CPC/CPM
   - Show top geography
   - Show trend indicator

3. Add loading states:
   - Skeleton for performance data
   - Error handling for missing data
   - Empty state (no performance data yet)

---

### Communication Protocol

**When CLI finishes a task:**
- Commit code with descriptive message
- Update handover doc with "✅ Complete" status
- Notify about any blockers for frontend work
- Provide API endpoint documentation

**When VSCode finishes a task:**
- Commit code
- Update handover doc
- Screenshot new UI for reference
- Note any API changes needed

**Daily Sync:**
- Review what each instance completed
- Identify blockers
- Adjust priorities if needed
- Update roadmap ETA

---

## 🎯 Success Metrics

### Phase 8 Goals

**Database:**
- ✓ Import 1M+ performance records
- ✓ Query performance <100ms
- ✓ Support both SQLite and PostgreSQL

**API:**
- ✓ CSV import completes in <2 minutes for 100k rows
- ✓ Validation catches all invalid data
- ✓ Duplicate detection works (no duplicate records)

**Frontend:**
- ✓ Sort 652 creatives by spend in <100ms
- ✓ Performance badges visible on all cards with data
- ✓ Date range selector works smoothly
- ✓ Virtual scrolling still performant

**User Experience:**
- ✓ Can upload CSV file via UI
- ✓ Can see import progress/errors
- ✓ Can sort creatives by spend
- ✓ Can filter by performance tier

---

### Phase 9-10 Goals (Future)

**AI Clustering:**
- ✓ Cluster 652 creatives into 15-20 campaigns in <60 seconds
- ✓ >80% user agreement with AI groupings
- ✓ Campaign names are descriptive and accurate

**Opportunity Detection:**
- ✓ Detect 10+ opportunities per customer
- ✓ Opportunities show $500+ weekly potential
- ✓ Statistical significance >90%
- ✓ >50% of recommendations are actionable

---

## 📞 Support & Contact

**Developer:** Jen (jen@rtb.cat)  
**Project:** RTB.cat Creative Intelligence  
**Repository:** /home/jen/Documents/rtbcat-platform/  
**Documentation:** This handover document  

**Quick Reference Commands:**

```bash
# Start backend
cd creative-intelligence && source venv/bin/activate
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Start frontend
cd dashboard && npm run dev

# Check database
sqlite3 ~/.rtbcat/rtbcat.db ".tables"

# Backup database
cp ~/.rtbcat/rtbcat.db ~/.rtbcat/backup_$(date +%Y%m%d).db

# Run migration
cd creative-intelligence
python -m storage.migrations.run

# Test CSV import
curl -X POST http://localhost:8000/api/performance/import \
  -F "file=@test.csv"
```

---

## 🔄 Version History

### v6.0 - November 30, 2025 (Current)
- 🔄 **Phase 8:** Performance data foundation (in progress)
- 📝 Strategic pivot to performance-first analytics
- 📝 Roadmap reordered (Phase 8 before Phase 7)
- 📝 Open core business model defined
- 📝 Database schema designed for performance metrics
- 📝 Opportunity detection algorithm designed

### v5.0 - November 30, 2025 (Earlier)
- ✅ **Phase 6:** Smart URL intelligence complete
- ✅ Performance optimization (slim mode, 26x improvement)
- ✅ UX improvements (modal, buttons, HTML rendering)

### v4.0 - November 29, 2025
- ✅ Phase 5 Complete: Dashboard UI integration
- ✅ All 8 routes generated
- ✅ Production-ready

### v3.0 - November 29, 2025 (Earlier)
- ✅ Added waste analysis engine
- ✅ Implemented multi-seat support
- ✅ Completed size normalization (98%)

---

## 🎉 Platform Status

**RTB.cat Creative Intelligence Platform is:**
- ✅ **Phase 1-6:** Production-ready (652 creatives, waste analysis, smart URLs)
- 🔄 **Phase 8:** In development (performance data foundation)
- 📋 **Phase 9-10:** Designed and ready (AI clustering, opportunity detection)
- 💰 **Revenue Model:** Defined (open core, Pro $2.5k, Enterprise $15k+)

**Next Session:**
1. Build Phase 8.1 (database schema + CSV import)
2. Test with real performance data
3. Update creatives page with performance badges
4. Move to Phase 9 (AI clustering)

---
## 🤖 Rules for Claude CLI

### Server Management
- RTB.cat API runs as a persistent systemd service
- **NEVER** start/stop the server directly
- **NEVER** use pkill, killall, or kill commands
- If code changes require restart, tell user: "Please restart server with: sudo systemctl restart rtbcat-api"
- Can check if running: curl http://localhost:8000/health

### Development Workflow
- Make code changes
- Tell user to restart service
- Continue other work while waiting
- Verify with health check after restart
---

**End of Handover Document v6**

*Last updated: November 30, 2025*  
*Next update: After Phase 8.1 completion*

---

**Congratulations on reaching Phase 8!** 🎉

The pivot to performance-first analytics positions RTBcat as a true competitive intelligence platform, not just a creative catalog. The open core strategy gives us the best of both worlds: trust through transparency + revenue through proprietary intelligence.

**Focus:** Ship Phase 8 this week, then AI clustering becomes trivial with performance data in place.

---

**Developer:** Jen (jen@rtb.cat)  
**Total Development Time:** ~3 weeks (Phases 1-8)  
**Lines of Code:** ~6,000+ (growing)  
**Test Coverage:** 53 backend tests + integration tests  
**Status:** 🚀 PHASE 8 IN PROGRESS - PERFORMANCE DATA FOUNDATION
