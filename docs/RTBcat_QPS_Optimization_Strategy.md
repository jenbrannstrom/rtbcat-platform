# RTBcat QPS Optimization System - Strategic Overview

## The Problem in Plain English

Imagine you run a hot dog stand at a stadium. The stadium sends you customers based on where you're located (endpoints) and what food types you sell (pretargeting). 

But here's the problem:
- Customers ask for foods you don't have (wrong creative sizes)
- Some customers are actually robots who just waste your time (fraud)
- You're paying rent for all the foot traffic, whether they buy or not (QPS costs)

**Your goal:** Only receive customers you can actually serve profitably.

---

## The Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GOOGLE'S AD UNIVERSE                              │
│                        (Billions of requests/day)                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PRETARGETING FILTER (Your 10 Configs)                    │
│                                                                             │
│  Each config says: "Send me requests that match these criteria"             │
│  - Geos: IN, PH, BR, US, etc.                                              │
│  - Platforms: Android, iOS, Desktop                                        │
│  - Environments: App, Web                                                  │
│  - Formats: Banner, Video, Native                                          │
│                                                                             │
│  ⚠️ Problem: You CAN'T filter by creative SIZE here!                        │
│     Google will send you 300x250, 336x280, 392x327, etc.                   │
│     If you don't have that size, the QPS is WASTED.                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ENDPOINT BOTTLENECK (90K QPS Total)                      │
│                                                                             │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐               │
│  │   US West       │ │     Asia        │ │    US East      │               │
│  │   10,000 QPS    │ │   30,000 QPS    │ │   50,000 QPS    │               │
│  │                 │ │                 │ │                 │               │
│  │ Handles: CA, MX │ │ Handles: IN, PH │ │ Handles: US, BR │               │
│  │ (closest geos)  │ │ ID, TH, VN, etc │ │ and others      │               │
│  └────────┬────────┘ └────────┬────────┘ └────────┬────────┘               │
│           │                   │                   │                        │
│           └───────────────────┼───────────────────┘                        │
│                               ▼                                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         YOUR BIDDER (Nova Beyond)                           │
│                                                                             │
│  Receives up to 90,000 bid requests per second.                            │
│  For each request, must decide in <100ms:                                  │
│                                                                             │
│  1. "Do I have a creative for size 336x280?"                               │
│     → NO? Can't bid. WASTED QPS.                                           │
│                                                                             │
│  2. "Is this app/publisher worth bidding on?"                              │
│     → Known fraud? Don't bid.                                              │
│                                                                             │
│  3. "What price should I bid?"                                             │
│     → Too low = lose auction. Too high = no profit.                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
            ┌─────────────┐                   ┌─────────────┐
            │  BID PLACED │                   │  NO BID     │
            │  (success!) │                   │  (waste!)   │
            └──────┬──────┘                   └─────────────┘
                   │
                   ▼
            ┌─────────────┐
            │  AUCTION    │
            │  (compete)  │
            └──────┬──────┘
                   │
         ┌─────────┴─────────┐
         ▼                   ▼
   ┌───────────┐       ┌───────────┐
   │ AUCTION   │       │ AUCTION   │
   │   WON     │       │   LOST    │
   └─────┬─────┘       └───────────┘
         │
         ▼
   ┌───────────┐
   │IMPRESSION │
   │ DELIVERED │
   └─────┬─────┘
         │
         ▼
   ┌───────────┐
   │  PROFIT   │
   └───────────┘
```

---

## Where RTBcat Fits In

RTBcat is your **intelligence layer**. It answers:

### Question 1: What sizes am I receiving that I can't serve?

**Data source:** Daily CSV (has `Creative size` + `Reached queries` + `Impressions`)

**Analysis:**
- Size 300x250: 107K reached, 80K impressions = 74% efficiency ✓
- Size 336x280: 1.4K reached, 0.4K impressions = 29% efficiency ✗

**Recommendation:** Investigate why 336x280 is low. If you don't have creatives for it, exclude from pretargeting (if possible) or accept the waste.

### Question 2: Which pretargeting config is most wasteful?

**Data source:** Daily CSV (has `Billing ID` which maps to config)

**Analysis:**
- Config 72245759413 (Africa/Asia): 126K reached, 92K imps = 73% ✓
- Config 151274651962 (USEast CA/MX): 826 reached, 420 imps = 51% ⚠️

**Recommendation:** Investigate the CA/MX config - something is wrong.

### Question 3: Which apps/publishers are burning QPS with no conversions?

**Data source:** Daily CSV (has `Mobile app ID` + `Clicks` + `Impressions`)

**Analysis:**
- App com.game.xyz: 50K impressions, 0 clicks, VAST error 402 = timeout issues
- App com.sketchy.app: High impressions, clicks > impressions = fraud

**Recommendation:** Block sketchy apps, investigate timeout issues.

---

## The 10 Pretargeting Configs (Your Levers)

| # | Billing ID | Short Name | Geos | Budget | QPS Cap |
|---|------------|------------|------|--------|---------|
| 1 | 72245759413 | Africa/Asia | BF,BR,CI,CM,EG,NG,SA,SE,IN,PH,KZ | $1,200 | 50K |
| 2 | 83435423204 | ID/BR Android | ID,BR,IN,US,KR,ZA,AR (Android) | $2,000 | 50K |
| 3 | 104602012074 | MENA iOS&AND | SA,AE,EG,PH,IT,ES,BF,KZ,FR,PE,ZA,HU,SK | $1,200 | 50K |
| 4 | 137175951277 | SEA Whitelist | BR,ID,MY,TH,VN (WL) | $1,200 | 30K |
| 5 | 151274651962 | USEast CA/MX | CA,MX (Blacklist) | $1,500 | 5K |
| 6 | 153322387893 | Brazil AND | BR (Android, WL) | $1,500 | 30K |
| 7 | 155546863666 | Asia BL2003 | ID,IN,TH,CN,KR,TR,VN,BD,PH,MY | $1,800 | 50K |
| 8 | 156494841242 | Nova WL | ? | $2,000 | 30K |
| 9 | 157331516553 | US/Global | US,PH,AU,KR,EG,PK,BD,UZ,SA,JP,PE,ZA,HU,SK,AR,KW | $3,000 | 50K |
| 10 | 158323666240 | BR/PH Spotify | BR,PH (Spotify only) | $2,000 | 30K |

**Total Budget:** ~$17,600/day
**Total QPS Cap:** 375K (but limited to 90K by endpoints)

---

## What You CAN Control in Pretargeting

✅ **Geography** - Include/exclude countries
✅ **Platform** - Include/exclude Desktop, Phone, Tablet, Connected TV
✅ **Environment** - Web, App, or both
✅ **Specific Apps/URLs** - Whitelist or blacklist
✅ **Publisher Verticals** - News, Games, etc.
✅ **Creative Dimensions** - Include/exclude specific sizes (!)
✅ **Maximum QPS** - Cap per config

**The size dimension is key!** If you're getting 336x280 requests but have no creatives, you could add size filtering to pretargeting (if the UI/API supports it).

---

## RTBcat Modules

### Module 1: Size Efficiency Analyzer ✓
- Input: Daily CSV with size data
- Output: List of sizes ranked by waste
- Action: Recommend sizes to exclude

### Module 2: Config Performance Tracker ✓
- Input: Daily CSV with Billing ID
- Output: Efficiency per pretargeting config
- Action: Identify underperforming configs

### Module 3: Fraud Signal Detector (Existing)
- Input: Performance metrics
- Output: Apps/publishers with fraud patterns
- Action: Add to blocklist

### Module 4: Creative Coverage Mapper (Planned)
- Input: Your 653 creatives from API + market sizes from CSV
- Output: Gap analysis
- Action: Identify sizes you COULD serve with new creatives

### Module 5: Opportunity Finder (Planned)
- Input: Low-efficiency sizes with decent volume
- Output: "If you created a 336x280 creative, you could capture X QPS"
- Action: Brief for creative team

---

## The Printout Philosophy

**All RTBcat outputs are "printouts" by default.**

Why?
1. **Transparency** - AdOps can see exactly what's recommended
2. **Safety** - No accidental changes to live bidding
3. **Learning** - Team builds intuition about QPS optimization
4. **Audit trail** - Document why changes were made

The printout shows:
```
================================================================================
QPS WASTE ANALYSIS REPORT
================================================================================

RECOMMENDATION #1: Exclude size 336x280
- Current efficiency: 28.6%
- Wasted QPS: 10,397 per day
- Affected configs: 72245759413, 155546863666
- Confidence: HIGH

TO IMPLEMENT:
1. Go to Authorized Buyers UI
2. Navigate to Bidder Settings → Pretargeting
3. Edit config "BF, BR, CI, CM, EG..." (72245759413)
4. Under Creative dimensions, add 336x280 to EXCLUDED
5. Click Save

⚠️ This change affects live bidding. Monitor for 24 hours after applying.
================================================================================
```

---

## CSV Automation Options

Current state: Manual download from Google UI → Upload to RTBcat

Options to automate:

### Option A: Scheduled Email → Google Drive → RTBcat
1. Google UI sends scheduled CSV to email
2. Email rule forwards to Google Drive (via Zapier or similar)
3. RTBcat polls Google Drive for new files

### Option B: BigQuery Direct Integration
1. Set up Google Authorized Buyers → BigQuery export
2. RTBcat queries BigQuery directly via API
3. No CSV files needed

### Option C: Keep It Simple
1. Manual download once daily
2. Drop into watched folder
3. RTBcat auto-imports

Recommendation: Start with Option C, upgrade to B when volume justifies it.

---

## Success Metrics

| Metric | Current | Target | How to Measure |
|--------|---------|--------|----------------|
| Overall Efficiency | ~70%? | 85%+ | Impressions / Reached Queries |
| Waste QPS | Unknown | <10% | (Reached - Bids) / Reached |
| Config Utilization | Unknown | Balanced | Compare efficiency across 10 configs |
| Fraud Rate | Unknown | <1% | Flagged impressions / Total |

---

## Next Steps

1. **Run API test** to verify credentials work
2. **Import sample CSV** using the BigQuery importer
3. **Generate first report** to see actual waste numbers
4. **Review with AdOps** to validate recommendations
5. **Implement first exclusions** (manually, via UI)
6. **Measure impact** after 7 days

---

**Document Author:** Claude + Jen
**Date:** December 1, 2025
**Version:** 1.0
