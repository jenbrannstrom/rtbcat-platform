# Cat-Scan Required CSV Reports Guide

**Version:** 2.0 | **Updated:** December 18, 2025

Cat-Scan supports **5 CSV report types** from Google Authorized Buyers for comprehensive QPS optimization.

---

## Report Types Overview

| Report | Table | Purpose |
|--------|-------|---------|
| **1. Performance Detail** | `rtb_daily` | Creative, Size, App-level performance |
| **2. RTB Funnel (Geo)** | `rtb_funnel` | Full bid pipeline by country |
| **3. RTB Funnel (Publisher)** | `rtb_funnel` | Publisher-level bid pipeline |
| **4. Bid Filtering** | `rtb_bid_filtering` | Why bids are being filtered |
| **5. Quality Signals** | `rtb_quality` | Fraud and viewability signals |

Reports 1-3 are **required** for basic QPS optimization.
Reports 4-5 are **optional** but enable advanced fraud detection and bid filtering analysis.

---

## Why Multiple Reports?

When creating reports in Google Authorized Buyers, certain fields are **mutually exclusive**:

> **Google Error:** "Mobile app ID is not compatible with [Bid requests], [Inventory matches] and 4 more field(s)."

This means:
- **To get App/Creative performance** → You lose bid pipeline metrics (Bid requests, Bids, etc.)
- **To get bid pipeline metrics** → You lose App/Creative detail
- **Publisher CAN be combined** with bid metrics (but not Apps)

---

## The 3 Required Reports

### Report 1: Performance Detail
**Purpose:** Creative, Size, and App-level performance data
**Database Table:** `rtb_daily`
**Filename:** `catscan-performance`

| Type | Fields |
|------|--------|
| **Dimensions** | Day, Billing ID, Creative ID, Creative size, Creative format, Country, Publisher ID, Mobile app ID, Mobile app name |
| **Metrics** | Reached queries, Impressions, Clicks, Spend (buyer currency) |

**What this tells you:**
- Which creatives are performing
- Which sizes have inventory
- Which apps/publishers drive wins
- Revenue by creative

---

### Report 2: RTB Funnel (Geo Only)
**Purpose:** Full bid-to-win pipeline by country
**Database Table:** `rtb_funnel`
**Filename:** `catscan-funnel-geo`

| Type | Fields |
|------|--------|
| **Dimensions** | Day, Country, Buyer account ID, Hour (optional) |
| **Metrics** | Bid requests, Inventory matches, Successful responses, Reached queries, Bids, Bids in auction, Auctions won, Impressions, Clicks |

**⚠️ Cannot include:** Creative ID, Creative size, Mobile app ID, Billing ID

**What this tells you:**
- How much traffic Google sends you per geo
- Your bid rate (Bids / Reached queries)
- Your win rate (Auctions won / Bids in auction)
- Where you're losing in the funnel

---

### Report 3: RTB Funnel (With Publishers)
**Purpose:** Publisher-level bid-to-win pipeline
**Database Table:** `rtb_funnel`
**Filename:** `catscan-funnel-publishers`

| Type | Fields |
|------|--------|
| **Dimensions** | Day, Country, Buyer account ID, Publisher ID, Publisher name, Hour (optional) |
| **Metrics** | Bid requests, Inventory matches, Successful responses, Reached queries, Bids, Bids in auction, Auctions won, Impressions, Clicks |

**⚠️ Cannot include:** Creative ID, Creative size, Mobile app ID

**What this tells you:**
- Which publishers send the most traffic
- Publisher-level win rates
- Where to focus publisher optimization

---

### Report 4: Bid Filtering (Optional)
**Purpose:** Understand why bids are being filtered
**Database Table:** `rtb_bid_filtering`
**Filename:** `catscan-bid-filtering`

| Type | Fields |
|------|--------|
| **Dimensions** | Day, Country, Buyer account ID |
| **Required Metrics** | Bid filtering reason, Bids, Bids in auction |

**What this tells you:**
- Why your bids are being rejected
- Which creative policies are affecting your QPS
- Opportunity cost of filtering

---

### Report 5: Quality Signals (Optional)
**Purpose:** Fraud and viewability analysis by publisher
**Database Table:** `rtb_quality`
**Filename:** `catscan-quality`

| Type | Fields |
|------|--------|
| **Dimensions** | Day, Publisher ID, Publisher name, Country |
| **Metrics** | Impressions, Pre-filtered impressions, IVT credited impressions, Billed impressions, Active View measurable, Active View viewable |

**What this tells you:**
- Which publishers have high fraud (IVT) rates
- Which publishers have low viewability
- Where to reduce bids or block

---

## Enhanced Fields for QPS Optimization

The following optional fields can be added to Reports 1-3 for better optimization:

### Performance Detail (Report 1) - Optional Fields
| Field | Column Name | Why Useful |
|-------|-------------|------------|
| Hour | `Hour` | Hourly traffic patterns |
| Platform | `Platform` | Desktop vs Mobile optimization |
| Environment | `Environment` | App vs Web strategy |
| Viewable | `Active View viewable` | Viewability tracking |
| Measurable | `Active View measurable` | Viewability tracking |

### RTB Funnel (Reports 2 & 3) - Optional Fields
| Field | Column Name | Why Useful |
|-------|-------------|------------|
| Platform | `Platform` | Device-level optimization |
| Environment | `Environment` | App vs Web analysis |
| Transaction Type | `Transaction type` | Open vs Private auction analysis |

---

## Step-by-Step: Creating Reports in Google AB

### Go to Authorized Buyers
1. Navigate to **Authorized Buyers** → **Reporting** → **Scheduled Reports**
2. Click **New Report**

### Report 1: Performance Detail

```
Report Name: catscan-performance

DIMENSIONS (add in this order):
1. Day
2. Billing ID
3. Creative ID
4. Creative size
5. Creative format
6. Country
7. Publisher ID
8. Mobile app ID
9. Mobile app name

METRICS:
✓ Reached queries
✓ Impressions
✓ Clicks
✓ Spend (buyer currency)

SCHEDULE:
• Frequency: Daily
• Time period: Yesterday
• Format: CSV
```

### Report 2: RTB Funnel (Geo)

```
Report Name: catscan-funnel-geo

DIMENSIONS (add in this order):
1. Day
2. Country
3. Buyer account ID
4. Hour (optional - for hourly patterns)

METRICS:
✓ Bid requests
✓ Inventory matches
✓ Successful responses
✓ Reached queries
✓ Bids
✓ Bids in auction
✓ Auctions won
✓ Impressions
✓ Clicks

SCHEDULE:
• Frequency: Daily
• Time period: Yesterday
• Format: CSV
```

### Report 3: RTB Funnel (Publishers)

```
Report Name: catscan-funnel-publishers

DIMENSIONS (add in this order):
1. Day
2. Country
3. Buyer account ID
4. Publisher ID
5. Publisher name
6. Hour (optional)

METRICS:
✓ Bid requests
✓ Inventory matches
✓ Successful responses
✓ Reached queries
✓ Bids
✓ Bids in auction
✓ Auctions won
✓ Impressions
✓ Clicks

SCHEDULE:
• Frequency: Daily
• Time period: Yesterday
• Format: CSV
```

---

## How Cat-Scan Joins the Data

Cat-Scan automatically joins these reports to give you the full picture:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FULL FUNNEL VIEW                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Report 2 (funnel-geo)     Report 1 (performance)                   │
│  ─────────────────────     ──────────────────────                   │
│                                                                     │
│  Bid requests: 100M   ─┐                                            │
│  Inventory matches    ─┤                                            │
│  Successful responses ─┤   JOIN ON                                  │
│  Reached queries ─────┼──► (date, country) ──► Creative breakdown   │
│  Bids                 ─┤                       Size breakdown       │
│  Bids in auction      ─┤                       App breakdown        │
│  Auctions won ────────┼──────────────────────► Impressions          │
│                                                Spend                │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Joined metrics give AI:**
- **Total Addressable Traffic:** Bid requests (from funnel)
- **Pretargeting Efficiency:** Reached / Inventory matches
- **Bid Rate:** Bids / Reached queries
- **Win Rate:** Auctions won / Bids in auction
- **Revenue per Traffic:** Spend / Bid requests
- **By Creative/Size/App:** From performance report

---

## Importing CSVs

### Smart Import (Recommended)
```bash
cd creative-intelligence
./venv/bin/python -m qps.smart_importer /path/to/report.csv
```
Auto-detects report type and imports to correct table.

### Manual Import
```bash
# Performance Detail → rtb_daily
./venv/bin/python -m qps.importer /path/to/catscan-performance.csv

# RTB Funnel → rtb_funnel
./venv/bin/python -m qps.funnel_importer /path/to/catscan-funnel-geo.csv
```

### Via Dashboard
1. Go to **Setup** → **Import**
2. Drag and drop any CSV
3. Cat-Scan auto-detects the type

---

## Database Schema

### rtb_daily (Performance Detail)
```sql
- metric_date, billing_id, creative_id, creative_size, creative_format
- country, publisher_id, app_id, app_name
- reached_queries, impressions, clicks, spend_micros
```

### rtb_funnel (Bid Pipeline)
```sql
- metric_date, hour, country, buyer_account_id
- publisher_id, publisher_name (when available)
- bid_requests, inventory_matches, successful_responses
- reached_queries, bids, bids_in_auction, auctions_won
- impressions, clicks
```

---

## Troubleshooting

### "Mobile app ID is not compatible with Bid requests"
You're trying to add App fields to a Funnel report. This is a Google limitation.
**Solution:** Keep App fields in Report 1 (Performance Detail) only.

### "Import failed: missing required columns"
Check that your CSV has all required columns for its type.
**Solution:** Run `./venv/bin/python -m qps.smart_importer --help` to see requirements.

### "No funnel data showing"
You may have only imported Performance Detail reports.
**Solution:** Create and import the Funnel reports (Reports 2 & 3).

---

## AI Optimization Data Requirements

For AI to make intelligent QPS optimization recommendations, it needs:

| Data | Source Report | Why Needed |
|------|---------------|------------|
| Total traffic available | Funnel (bid_requests) | Know addressable market |
| What you actually bid on | Funnel (bids) | Calculate bid rate |
| What you win | Funnel (auctions_won) | Calculate win rate |
| What converts | Performance (impressions) | Calculate efficiency |
| By creative/size | Performance | Know inventory gaps |
| By app/publisher | Performance + Funnel | Target optimization |
| Revenue | Performance (spend) | ROI calculation |

**Without all 3 reports, AI can only partially optimize.**
