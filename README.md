# Cat-Scan: a QPS optimizer & Creative Intelligence Platform

**Privacy-First Campaign Performance Intelligence for bidders & DSPs**

> 🔒 **Your data. Your infrastructure. Provably private.**

**Status:** Phase 9 Complete | Phase 10 Planned (Thumbnail Generation)

---

## 🎯 What is RTB.cat?

Cat is a **privacy-first platform** for DSPs and performance bidders to:

1. **Eliminate waste**d QPS (cut 20-40% of unprofitable QPS)
2. Plug in your Agent (Claude, ChatGPT, Grok, Gemini, ...)
3. **Classify creatives** from Google Authorized Buyers (and other SSPs soon)
4. **Agentic Investigation of performance** (spend, clicks, impressions, CPM, CPC)
5. **Agentic Classification of campaigns** collect creatives using AI clustering
6. **Agentic  opportunities finder** (under- or over-valued geos/bundleID's/placements, high-CPC low-spend, profit pockets)
7.  **Run everything privately** in your own infrastructure

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│              YOUR AWS ACCOUNT / PRIVATE VPC              │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────────────────────────────────┐             │
│  │   Cat-Scan Creative Intel Backend        │             │
│  │   (Python FastAPI)                     │             │
│  │   • Fetch creatives from Google API    │             │
│  │   • Import performance data            │             │
│  │   • AI campaign clustering             │             │
│  │   • Opportunity detection              │             │
│  └────────────────────────────────────────┘             │
│                      ▲                                   │
│                      │                                   │
│  ┌────────────────────────────────────────┐             │
│  │   Web Dashboard (Next.js)              │             │
│  │   • Creative browser (sort by spend)   │             │
│  │   • Waste analysis                     │             │
│  │   • Opportunity grid                   │             │
│  │   • Campaign performance               │             │
│  └────────────────────────────────────────┘             │
│                                                          │
│  ┌────────────────────────────────────────┐             │
│  │   YOUR Database (PostgreSQL/SQLite)    │             │
│  │   • Creatives (652+)                   │             │
│  │   • Performance metrics (millions)     │             │
│  │   • Campaigns (AI-clustered)           │             │
│  │   • Opportunities (AI-detected)        │             │
│  └────────────────────────────────────────┘             │
│                                                          │
└─────────────────────────────────────────────────────────┘
                          │
                          │ (Your API calls)
                          ▼
              ┌──────────────────────────┐
              │  Google Authorized       │
              │  Buyers API              │
              └──────────────────────────┘
```

---

## 💡 Core Value Proposition

### **The Problem**
Traditional AdTech SaaS platforms:
- Store YOUR creative and performance data on THEIR servers
- Give you generic waste analysis
- Miss profit opportunities (undervalued geos, neglected high-performers)
- Charge $500-5000/month
- Vendor lock-in

### **The Solution**
RTBcat runs in YOUR infrastructure:
- ✅ Your data never leaves your AWS/VPC
- ✅ AI finds opportunities (not just waste)
- ✅ Sort creatives by spend (see what's actually working)
- ✅ Geographic intelligence ("Works in Brazil, fails in Ireland")
- ✅ Open source core (free) + proprietary features (paid)
- ✅ From $2,499/year or FREE

---

## 📋 Roadmap & Features

### ✅ **Phase 1-5: Foundation (Complete)**

| Phase | Feature | Status |
|-------|---------|--------|
| 1 | Creative Management | ✅ Complete |
| 2 | Size Normalization (2000+ → 18 IAB) | ✅ Complete |
| 3 | Multi-Seat Support | ✅ Complete |
| 4 | Waste Analysis Engine | ✅ Complete |
| 5 | Dashboard UI | ✅ Complete |
| 5.5 | Performance Optimization (26x faster) | ✅ Complete |

**What's Working:**
- Fetch 652+ creatives from Google Authorized Buyers API
- Normalize sizes to IAB standards
- Multi-buyer account support
- Identify RTB waste (what you CAN'T bid on vs what you're ASKED for)
- Beautiful dashboard with waste visualization
- Virtual scrolling for smooth UX

---

### ✅ **Phase 6: Smart URL Intelligence (Complete)**

| Task | Status |
|------|--------|
| Google Auth Buyers links | ✅ Complete |
| Destination URL parsing | ✅ Complete |
| Attribution platform detection | ✅ Complete |
| App store metadata | ✅ Complete |

**Features:**
- Parse complex destination URLs (AppsFlyer → DoubleClick → App Store)
- Intelligent categorization (attribution links, trackers, final destinations)
- Tooltips explaining each link type
- Direct links to Google Authorized Buyers UI

---

### ✅ **Phase 8: Performance Data Foundation (Complete)**

**Status:** Complete

This is the **critical foundation** for all advanced features (AI clustering, opportunity detection, geographic insights).

#### **8.1: Database Schema Extension** ✅ Complete

**New Tables:**

```sql
-- Performance metrics (granular data)
CREATE TABLE performance_metrics (
    id SERIAL PRIMARY KEY,
    creative_id INTEGER REFERENCES creatives(id),
    date DATE NOT NULL,
    hour INTEGER,  -- 0-23 for hourly data
    impressions BIGINT DEFAULT 0,
    clicks BIGINT DEFAULT 0,
    spend DECIMAL(12,2) DEFAULT 0,
    cpm DECIMAL(8,4),  -- Calculated or imported
    cpc DECIMAL(8,4),  -- Calculated or imported
    geography VARCHAR(2),  -- ISO country code (BR, IE, US)
    device_type VARCHAR(20),  -- mobile, desktop, tablet
    placement VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(creative_id, date, hour, geography, device_type)
);

-- Indexes for fast querying
CREATE INDEX idx_perf_creative_date ON performance_metrics(creative_id, date);
CREATE INDEX idx_perf_geo_date ON performance_metrics(geography, date);
CREATE INDEX idx_perf_spend ON performance_metrics(spend DESC);
CREATE INDEX idx_perf_cpc ON performance_metrics(cpc ASC);

-- Campaign performance aggregation (cached for speed)
ALTER TABLE campaigns ADD COLUMN total_spend_7d DECIMAL(12,2);
ALTER TABLE campaigns ADD COLUMN total_spend_30d DECIMAL(12,2);
ALTER TABLE campaigns ADD COLUMN total_spend_all_time DECIMAL(12,2);
ALTER TABLE campaigns ADD COLUMN avg_cpc_7d DECIMAL(8,4);
ALTER TABLE campaigns ADD COLUMN avg_cpm_7d DECIMAL(8,4);
ALTER TABLE campaigns ADD COLUMN top_geography VARCHAR(2);
ALTER TABLE campaigns ADD COLUMN last_performance_update TIMESTAMP;
```

**Why This Matters:**
- Enables "Sort by spend" on creatives page
- Foundation for opportunity detection
- Enables geographic performance analysis
- Supports AI clustering based on performance

---

#### **8.2: Data Import System** ✅ Complete

**Multiple Import Methods:**

1. **CSV Upload (Manual)**
   - Web UI upload form
   - Drag-and-drop CSV file
   - Validate and import in batches
   - Show progress bar

2. **JSON API (Programmatic)**
   - POST /api/performance/import
   - Batch import (1000 rows at a time)
   - Duplicate detection
   - Return import summary

3. **S3 Bucket Sync (Automated)**
   - Customer drops CSV/JSON files in S3
   - Lambda function triggers import
   - Schedule daily/hourly imports
   - Error logging to CloudWatch

4. **Google API Integration (Partial)**
   - Fetch available metrics from Authorized Buyers API
   - Limited data (not all fields available)
   - Supplement with customer's own data

5. **BigQuery Connector (Enterprise)**
   - Direct connection to customer's BigQuery
   - Scheduled queries
   - Real-time or batch sync

**CSV Format Example:**
```csv
creative_id,date,impressions,clicks,spend,geography,device_type
79783,2025-11-29,10000,250,125.50,BR,mobile
79783,2025-11-29,5000,100,80.00,BR,desktop
79783,2025-11-29,2000,15,30.00,IE,mobile
144634,2025-11-29,50000,800,200.00,US,mobile
```

**Data Validation:**
- Required fields: creative_id, date, impressions, clicks, spend
- Validations:
  - spend >= 0
  - clicks >= 0 and clicks <= impressions
  - date not in future
  - geography is valid ISO code (optional)
  - creative_id exists in database
- Duplicate detection (unique constraint)
- Error reporting (which rows failed)

---

#### **8.3: Creatives Page Enhancement** ✅ Complete

**Current State:**
- Cards sorted by creative_id (not useful)
- No performance data shown

**New Features:**

1. **Sort by Spend**
   - Dropdown: [Yesterday | Last 7 Days | Last 30 Days | All Time]
   - Default: Last 7 Days
   - Highest spend first

2. **Performance Badges on Cards**
   ```
   ┌─────────────────────────────────┐
   │  [Creative Thumbnail]           │
   │                                 │
   │  79783                          │  ← Creative ID (large)
   │  buyers/299.../creatives/79783  │  ← Google link
   │                                 │
   │  💰 Spend (7d): $1,234          │  ← NEW
   │  📊 CPC: $0.45  CPM: $2.20      │  ← NEW
   │  🌍 Top Geo: Brazil             │  ← NEW
   │  📈 +15% vs last week           │  ← NEW (trend)
   │                                 │
   │  [View Details]                 │
   └─────────────────────────────────┘
   ```

3. **Filters**
   - Existing: Format (Video, Native, Banner, HTML5)
   - Existing: Size (300x250, 728x90, etc.)
   - NEW: Geography (Brazil, Ireland, US, etc.)
   - NEW: Performance tier (High spend, Medium, Low, Zero)

4. **Quick Stats Bar**
   ```
   Total Creatives: 652
   With Performance Data: 487
   Total Spend (7d): $45,678
   Avg CPC: $0.52
   Top Geo: Brazil (40% of spend)
   ```

---

#### **8.4: Campaign Performance Aggregation** ✅ Complete

**Aggregate performance to campaign level:**

```python
# Example aggregation
Campaign: "Mobile Game - Puzzle - Brazil Portuguese"
  Creatives: 15
  
  Performance (7d):
    Total Spend: $2,500
    Total Impressions: 5M
    Total Clicks: 5,000
    Avg CPC: $0.50
    Avg CPM: $0.50
    
  Geographic Breakdown:
    Brazil: $2,000 (80%), CPC $0.45
    Portugal: $300 (12%), CPC $0.55
    Angola: $200 (8%), CPC $0.30  ← Opportunity!
    
  Size Breakdown:
    300x250: $1,500 (60%)
    728x90: $800 (32%)
    320x50: $200 (8%)
    
  Top Creative: #79783 ($800, CPC $0.40)
```

**Use Cases:**
- Compare campaign performance
- Find best/worst performers
- Identify opportunities at campaign level
- Roll up creatives for executive reporting

---

### ✅ **Phase 9: AI Campaign Clustering (Pro Feature) - Complete**

**Status:** Complete

**Features:**
- AI groups 652+ creatives into 15-20 campaigns
- Based on: visual similarity, language, product, geography
- Multi-provider: Claude, Gemini, rule-based fallback
- Campaign naming (AI-generated)
- Performance attribution (which creatives drive campaign success)

**Example:**
```
Campaign: "Mobile Game - Puzzle - Brazil Portuguese"
  - Creative 101 (300x250, pt_br)
  - Creative 205 (728x90, pt_br)
  - Creative 387 (320x50, pt_br)
  
  Performance: $2,500/week, CPC $0.50
```

**Pricing:** Pro tier ($2,499/year)

---

### 🔄 **Phase 10: Thumbnail Generation (CURRENT)**

**Status:** Planned

Generate offline thumbnails for faster card previews:

**HTML Creatives:**
- Use Playwright/Puppeteer to render HTML and screenshot
- Store thumbnails locally or in S3

**Video Creatives:**
- Use ffmpeg to extract frame at 1 second
- Generate poster image for video cards

**Database Changes:**
```sql
ALTER TABLE creatives ADD COLUMN thumbnail_url TEXT;
```

**Implementation:**
- Background job on creative sync/import
- Queue system (Celery or cron-based)
- Thumbnail storage: `~/.rtbcat/thumbnails/` or S3

---

### 💰 **Phase 11: Opportunity Intelligence (Pro Feature)**

**Status:** Designed

**The Magic Feature: Find Profit Pockets**

**Algorithm detects:**

1. **Undervalued Geographies**
   - Geography with >20% better CPC than average
   - But represents <5% of total spend
   - Example: Angola has CPC $0.30 (40% better) but only $200/week spend
   - Recommendation: Scale Angola spend to $1,000/week
   - Potential savings: $400/week

2. **High-CPC Low-Spend Campaigns**
   - Campaign with top-quartile CPC (efficient)
   - But bottom-quartile spend (neglected by bidder)
   - Example: Finance campaign has CPC $0.20 (best) but only $500/week
   - Recommendation: Scale to $5,000/week
   - Potential profit: +$4,500 weekly spend at superior CPC

3. **Size/Format Gaps**
   - Campaign missing a size that performs well in similar campaigns
   - Example: Only uses 300x250, but 728x90 has 30% lower CPC elsewhere
   - Recommendation: Create 728x90 creative
   - Potential savings: $270/week

4. **Neglected Creatives**
   - Creative with excellent CPC but minimal impressions
   - Blocked by pretargeting or low bid
   - Recommendation: Check pretargeting config

**Opportunity Dashboard (New Page):**

```
┌────────────────────────────────────────────────────────────────┐
│                    OPPORTUNITY DASHBOARD                        │
├────────────────────────────────────────────────────────────────┤
│  Sort: [Potential Savings ▼]  Filter: [All Types ▼]           │
├────────────────────────────────────────────────────────────────┤
│ Campaign      │ Insight              │ Current │ Potential │   │
│ (thumbnail)   │                      │ CPC     │ Savings   │   │
├───────────────┼──────────────────────┼─────────┼───────────┼───┤
│ [img] Puzzle  │ Undervalued Geo:     │ $0.30   │ $400/wk   │[→]│
│ Game Brazil   │ Angola 40% better    │         │           │   │
├───────────────┼──────────────────────┼─────────┼───────────┼───┤
│ [img] Finance │ High-CPC Low-Spend:  │ $0.20   │ $900/wk   │[→]│
│ Vertical Vid  │ Best CPC, neglected  │         │           │   │
├───────────────┼──────────────────────┼─────────┼───────────┼───┤
│ [img] Fashion │ Size Gap: 728x90     │ $0.42   │ $270/wk   │[+]│
│ E-commerce    │ 30% lower CPC        │ (est.)  │           │   │
└───────────────┴──────────────────────┴─────────┴───────────┴───┘
```

**Export to CSV** for manual execution or integration with bidder.

**Pricing:** Pro tier ($2,499/year)

---

### 💰💰 **Phase 12: Geographic Intelligence (Enterprise)**

**Status:** Advanced R&D  
**ETA:** Quarter 2 2026

**Cross-Campaign Pattern Detection:**

AI analyzes ALL campaigns to find patterns:
- "Puzzle games work well in Brazil (CPC $0.30), poorly in Ireland (CPC $1.20)"
- "Video format works in APAC, display works in EU"
- "Finance creatives underperform on weekends"

**Segment Performance Matrix:**
```
           │ Brazil │ Ireland │ India │ USA
───────────┼────────┼─────────┼───────┼─────
Puzzle     │ $0.30  │ $1.20   │ $0.40 │ $0.80
Strategy   │ $0.50  │ $0.45   │ $0.60 │ $0.55
Casino     │ $0.20  │ $0.95   │ $0.25 │ $0.70

Insight: Puzzle genre performs 4x better in Brazil vs Ireland
Recommendation: Shift budget from Ireland to Brazil
Potential savings: $500/week
```

**Predictive Analytics:**
- "This campaign will likely perform well in Brazil based on similar campaigns"
- "This creative style historically underperforms on mobile"
- "This vertical sees 30% higher CPC on weekends"

**Custom AI Prompts:**
- Customer defines custom queries
- "Find campaigns where iOS CPC > Android CPC by >50%"
- "Show creatives with >2% CTR in Tier 3 countries"

**Pricing:** Enterprise tier ($15k-50k/year)

---

### 💰💰 **Phase 13: Real-Time & Automation (Enterprise)**

**Status:** Future  
**ETA:** Quarter 3 2026

**12.1: Live Data Connectors**
- BigQuery streaming
- Snowflake connector
- Kafka/Kinesis integration
- Hourly performance updates

**12.2: Alerting & Monitoring**
- Alert when campaign CPC increases >20%
- Alert when spend drops >50%
- Alert when new opportunity detected
- Slack/Email/Webhook notifications

**12.3: Pretargeting Automation (⚠️ High Liability)**
- Auto-apply recommendations (with safeguards)
- Dry-run mode (default)
- One-click rollback
- QPS monitoring
- Auto-rollback if QPS drops >50%
- Gradual rollout (10% → 50% → 100%)

**Liability Protection:**
- Backup of current pretargeting config
- Emergency stop button
- Customer liability waiver
- Optional insurance ($10k/year covers up to $100k lost revenue)

**Pricing:** Enterprise tier + optional insurance

---

### 🔄 **Phase 7: Privacy Modularization (DEFERRED)**

**Status:** Designed, Build Later  
**Reason:** Need to develop and use all features locally first

**Will include:**
- Pip-installable module (`pip install rtbcat-creative-intel`)
- CLI interface (`rtbcat serve`, `rtbcat sync`, etc.)
- Static UI export (upload to customer's S3)
- Open source release (MIT license)
- Network monitoring guide (prove zero data exfiltration)

**Deferred until:** After Phase 8-10 are working and tested

---

## 💰 Pricing & Features Matrix

| Feature | Community (FREE) | Pro ($2,499/yr) | Enterprise (Custom) |
|---------|------------------|-----------------|---------------------|
| **Creative Management** |
| Fetch from Google API | ✓ | ✓ | ✓ |
| Size normalization | ✓ | ✓ | ✓ |
| Multi-seat support | ✓ | ✓ | ✓ |
| Basic waste analysis | ✓ | ✓ | ✓ |
| **Performance Tracking** |
| CSV import | ✗ | ✓ | ✓ |
| Sort by spend | ✗ | ✓ | ✓ |
| Performance badges | ✗ | ✓ | ✓ |
| Date range filters | ✗ | ✓ | ✓ |
| **AI Features** |
| Campaign clustering | ✗ | ✓ | ✓ |
| Opportunity detection | ✗ | ✓ | ✓ |
| Geographic insights | ✗ | ✗ | ✓ |
| Predictive analytics | ✗ | ✗ | ✓ |
| Custom AI prompts | ✗ | ✗ | ✓ |
| **Data Integration** |
| Manual CSV upload | ✗ | ✓ | ✓ |
| S3 bucket sync | ✗ | ✓ | ✓ |
| BigQuery connector | ✗ | ✗ | ✓ |
| Real-time streaming | ✗ | ✗ | ✓ |
| **Support** |
| GitHub issues | ✓ | ✗ | ✗ |
| Email support | ✗ | ✓ (48h) | ✓ (4h) |
| Slack support | ✗ | ✓ | ✓ |
| Phone support | ✗ | ✗ | ✓ |
| Dedicated engineer | ✗ | ✗ | ✓ |

---

## 🚀 Quick Start

### **Development (Current)**

```bash
# Backend
cd creative-intelligence
source venv/bin/activate
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd dashboard
npm install
npm run dev

# Access
Dashboard: http://localhost:3000
API Docs: http://localhost:8000/docs
```

### **Production Deployment (Future - Phase 7)**

```bash
# One-command deployment to customer's AWS
terraform apply

# Upload UI to customer's S3
npm run build
aws s3 sync out/ s3://customer-bucket/
```

---

## 📊 Database Schema

### **Existing Tables**

```sql
-- Creatives (652+)
creatives (
    id, buyer_id, creative_id, format,
    width, height, canonical_size, size_category,
    declared_click_urls, destination_urls_parsed,
    html_snippet, vast_xml, creative_attributes
)

-- Campaigns (AI-clustered)
campaigns (
    id, campaign_name, creative_ids[],
    confidence_score, ai_provider
)

-- Buyer seats (multi-account)
buyer_seats (
    buyer_id, display_name, bidder_account_id,
    creative_count, last_sync
)

-- RTB traffic (waste analysis)
rtb_traffic (
    timestamp, size, format, geo,
    device_type, qps
)
```

### **Phase 8 Tables (Complete)**

```sql
-- Performance metrics (granular)
performance_metrics (
    creative_id, date, hour,
    impressions, clicks, spend, cpm, cpc,
    geography, device_type, placement
)

-- Opportunities (AI-detected)
opportunities (
    campaign_id, insight_type,
    current_metric, potential_savings,
    recommendation, confidence_score
)
```

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.12, FastAPI |
| Database | PostgreSQL / SQLite |
| Frontend | Next.js 16, React 19, Tailwind CSS |
| AI | Claude (Anthropic), Gemini (Google) |
| Charts | Recharts |
| Data Fetching | TanStack React Query |
| Virtual Scrolling | @tanstack/react-virtual |
| RTB Analyzer | Rust (CAT_SCAN module) |

---

## 📈 Success Metrics

### **Phase 8 Goals**
- ✓ Import 1M+ performance records
- ✓ Sort 652 creatives by spend in <100ms
- ✓ Display performance data on all creative cards
- ✓ Support CSV, JSON, S3 import methods
- ✓ Handle duplicates gracefully
- ✓ Geographic breakdown for all creatives

### **Phase 9 Goals**
- ✓ Cluster 652 creatives into 15-20 campaigns
- ✓ AI clustering completes in <60 seconds
- ✓ >80% customer agreement with AI groupings
- ✓ Campaign names are descriptive and accurate

### **Phase 10 Goals**
- ✓ Detect 10+ opportunities per customer
- ✓ Opportunities show $500+ weekly potential savings
- ✓ Statistical significance >90% for all insights
- ✓ Customer acts on >50% of recommendations

---

## 📞 Support & Community

**Current (Development):**
- Developer: Jen (jen@rtb.cat)
- Repository: /home/jen/Documents/rtbcat-platform/
- Documentation: This README + handover docs

**Future (Production):**
- GitHub: https://github.com/rtbcat/creative-intel
- Documentation: https://docs.rtb.cat
- Support: support@rtb.cat
- Community: Discord (TBD)

---

## 📜 License

**Current:** Proprietary (in development)  
**Future (Phase 7):** Open source core (MIT) + proprietary features

---

## 🎉 Current Status

**Phase 1-6: Complete ✅**
- 652 creatives collected
- Smart URL parsing working
- Waste analysis operational
- Dashboard polished and performant

**Phase 8: Complete ✅**
- Performance metrics database schema
- CSV import system working
- Sort by spend on creatives page
- Performance badges on cards (spend, CTR, CPM, CPC)
- Seat name display in creatives

**Phase 9: Complete ✅**
- AI campaign clustering functional
- Auto-cluster button in campaigns page
- Campaign management (rename, delete)

**Phase 10: Planned 🚀**
- Thumbnail generation for HTML/Video creatives
- Playwright/Puppeteer for HTML screenshots
- ffmpeg for video poster frames

---

**Last Updated:** November 30, 2025
**Version:** 9.0 (Phase 9 Complete)
**Next Milestone:** Thumbnail generation (Phase 10)

---

**End of README**