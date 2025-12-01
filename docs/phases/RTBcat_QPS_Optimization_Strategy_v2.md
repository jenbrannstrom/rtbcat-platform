# RTBcat QPS Optimization System - Strategic Overview v2

## The Problem in Plain English

Imagine you run a hot dog stand at a stadium. The stadium sends you customers based on where you're located (endpoints) and what food types you sell (pretargeting). 

But here's the problem:
- Customers ask for foods you don't have (wrong creative sizes)
- Some customers are actually robots who waste your time, but they're mixed in with real customers - 70-80% real, 20-30% fake (smart fraud)
- You're paying rent for all the foot traffic, whether they buy or not (QPS costs)
- Even real customers who don't buy aren't "waste" - that's just the cost of doing business

**Your goal:** Optimize the traffic you receive to maximize the customers you can actually serve profitably, while understanding that not every impression leads to profit - and that's okay.

---

## The Real Profit Funnel

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         THE COMPLETE PROFIT FUNNEL                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────┐                                                          │
│  │   REACHED     │  ← QPS that matched your pretargeting                    │
│  │   QUERIES     │                                                          │
│  └───────┬───────┘                                                          │
│          │                                                                  │
│          ▼                                                                  │
│  ┌───────────────┐     ┌──────────────────────────────────────────────┐    │
│  │  CAN YOU BID? │────►│ NO: Wrong size, no matching creative         │    │
│  └───────┬───────┘     │     → TRUE WASTE (QPS you can't use)         │    │
│          │ YES         └──────────────────────────────────────────────┘    │
│          ▼                                                                  │
│  ┌───────────────┐     ┌──────────────────────────────────────────────┐    │
│  │  AUCTION WON? │────►│ NO: Outbid by competitors                    │    │
│  └───────┬───────┘     │     → Normal competition, not waste          │    │
│          │ YES         └──────────────────────────────────────────────┘    │
│          ▼                                                                  │
│  ┌───────────────┐     ┌──────────────────────────────────────────────┐    │
│  │  IMPRESSION   │────►│ Delivery failures (VAST errors, timeouts)    │    │
│  │  DELIVERED?   │     │     → Technical waste, investigate           │    │
│  └───────┬───────┘     └──────────────────────────────────────────────┘    │
│          │ YES                                                              │
│          ▼                                                                  │
│  ┌───────────────┐     ┌──────────────────────────────────────────────┐    │
│  │    CLICK?     │────►│ NO CLICK (95%+ of impressions)               │    │
│  └───────┬───────┘     │     → Cost of doing business                 │    │
│          │ YES         │     → Builds brand awareness                 │    │
│          │             │     → Expected, NOT waste                    │    │
│          ▼             └──────────────────────────────────────────────┘    │
│  ┌───────────────┐                                                          │
│  │  REAL CLICK   │  ← This is where fraud hides                            │
│  │  OR BOT?      │                                                          │
│  └───────┬───────┘                                                          │
│          │                                                                  │
│     ┌────┴────────────────────────────────────────────────────┐            │
│     │                                                          │            │
│     ▼                                                          ▼            │
│  ┌─────────────┐                                    ┌─────────────────┐    │
│  │ REAL CLICK  │                                    │   BOT CLICK     │    │
│  │ (70-80%)    │                                    │   (20-30%)      │    │
│  └──────┬──────┘                                    │                 │    │
│         │                                           │ Smart fraudsters │    │
│         ▼                                           │ mix fake with    │    │
│  ┌───────────────┐                                  │ real to avoid    │    │
│  │  CONVERSION?  │                                  │ detection        │    │
│  └───────┬───────┘                                  └─────────────────┘    │
│          │                                                                  │
│     ┌────┴────┐                                                            │
│     ▼         ▼                                                            │
│  ┌──────┐  ┌────────────────────────────────────────────────────────┐     │
│  │PROFIT│  │ NO CONVERSION                                          │     │
│  │  $   │  │     → Cost of customer acquisition                     │     │
│  └──────┘  │     → Normal sales funnel behavior                     │     │
│            │     → Not every visitor becomes a customer             │     │
│            └────────────────────────────────────────────────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Key insight:** The only TRUE waste is QPS for sizes you can't serve. Everything else is either competition, cost of business, or fraud (which requires pattern detection over time).

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
│                                                                             │
│  LOGIC:                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ All settings use AND logic with each other:                         │   │
│  │                                                                      │   │
│  │ (Geo = India)                                                        │   │
│  │   AND (Platform = Mobile)                                            │   │
│  │   AND (Size = 300x250 OR 320x50)  ← sizes are OR within the list    │   │
│  │   AND (Environment = Web OR App)  ← Web/App are OR with each other  │   │
│  │                                                                      │   │
│  │ Request must match ALL criteria to be sent to your bidder           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  SIZE FILTERING (Critical!):                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ • Leave size list BLANK = Accept ALL sizes (including odd ones)     │   │
│  │ • Add ONE size to list = ONLY that size accepted (others excluded)  │   │
│  │ • Add MULTIPLE sizes = Those sizes accepted (OR logic within list)  │   │
│  │                                                                      │   │
│  │ ⚠️  There is no "exclude" option - it's INCLUDE-only               │   │
│  │ ⚠️  Once you include ANY size, all unlisted sizes are excluded     │   │
│  │ ⚠️  This is powerful but DANGEROUS - mistakes block good traffic   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
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
│  │ bidder.         │ │ bidder-sg.      │ │ bidder-us.      │               │
│  │ novabeyond.com  │ │ novabeyond.com  │ │ novabeyond.com  │               │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘               │
│                                                                             │
│  Your 10 pretargeting configs sum to 375K QPS capacity,                    │
│  but endpoints can only handle 90K total. Configs compete for pipe.        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         YOUR BIDDER (Nova Beyond)                           │
│                                                                             │
│  Receives up to 90,000 bid requests per second.                            │
│  For each request, decides in <100ms whether/how much to bid.              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## The Size Problem & Solution

### Available Sizes in Google's List (98 sizes)

```
468x60    728x90    250x250   200x200   336x280   300x250   120x600   160x600
320x50    300x50    425x600   300x600   970x90    240x400   980x120   930x180
250x360   580x400   300x1050  480x320   320x480   768x1024  1024x768  480x32
1024x90   970x250   300x100   750x300   750x200   750x100   950x90    88x31
220x90    300x31    320x100   980x90    240x133   200x446   292x30    960x90
970x66    300x57    120x60    375x50    414x736   736x414   320x400   600x314
400x400   480x800   500x500   500x720   600x500   672x560   1160x800  600x100
640x100   640x200   240x1200  320x1200  600x1200  600x2100  936x120   1456x180
1860x360  1940x180  1940x500  1960x240  850x1200  960x640   640x960   1536x2048
2048x1536 960x64    2048x180  600x200   1500x600  1500x400  1500x200  1900x180
176x62    440x180   600x62    1960x180  480x266   400x892   584x60    1920x180
1940x132  600x114   240x120   828x1472  1472x828  640x800   800x800   960x1600
1000x1000 1000x1440 1200x1000 1344x1120 2320x1600 1200x200  1280x200  1280x400
... and more
```

### The Trade-off

| Strategy | Pros | Cons |
|----------|------|------|
| **Blank (accept all)** | Get all opportunities, including future sizes | Receive QPS for sizes you can't serve (waste) |
| **Include your sizes only** | Every request is servable, zero size waste | Miss new size opportunities, must maintain list |
| **Include standard + buffer** | Balance of efficiency and opportunity | Requires ongoing management |

### RTBcat's Role

RTBcat should answer these questions:

1. **What sizes are you currently receiving?** (from CSV data)
2. **Which of those do you have creatives for?** (from Creatives API)
3. **What's the match rate?** (% of QPS you can actually serve)
4. **If you set an INCLUDE list, what would you keep/lose?**
5. **Which high-volume sizes should you create new creatives for?**

---

## Fraud Detection Reality

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FRAUD DETECTION LAYERS                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  LAYER 1: Google's Systems (catches obvious fraud)                          │
│  ├── Pure fraud apps (100% fake traffic) → Blocked                         │
│  ├── Known bot signatures → Filtered                                       │
│  └── Blatant policy violations → Account banned                            │
│                                                                             │
│  LAYER 2: Smart Fraudsters Evade Detection                                  │
│  ├── Mix 70-80% real traffic with 20-30% fake                              │
│  ├── Use real devices in click farms (not emulators)                       │
│  ├── Randomize timing to look human                                        │
│  └── Rotate through many apps to stay under radar                          │
│                                                                             │
│  LAYER 3: What RTBcat Can Detect (patterns over time)                       │
│  ├── App-level anomalies:                                                  │
│  │   • Clicks > Impressions consistently (timing vs fraud)                 │
│  │   • CTR way above/below average for category                            │
│  │   • High impressions, zero conversions over weeks                       │
│  │                                                                          │
│  ├── Statistical anomalies:                                                │
│  │   • Suspiciously consistent metrics (too regular = bot)                 │
│  │   • Sudden spikes that don't match organic patterns                     │
│  │                                                                          │
│  └── What RTBcat CANNOT reliably detect:                                   │
│      • Geographic anomalies - VPNs are everywhere                          │
│      • Android has built-in Chrome VPN/IP masking                          │
│      • Single-occurrence oddities (need patterns)                          │
│                                                                             │
│  RTBcat's job: FLAG suspicious patterns for human review                   │
│  NOT: Definitively identify fraud (that requires more data)                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## The 10 Pretargeting Configs

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

## RTBcat Modules

### Module 1: Size Coverage Analyzer
**Purpose:** Understand the gap between sizes you receive and sizes you can serve

**Output:**
```
SIZE COVERAGE REPORT
================================================================================

Your Creative Inventory:
  You have 653 creatives across these sizes:
  ✓ 300x250 (127 creatives)
  ✓ 320x50 (89 creatives)
  ✓ 728x90 (45 creatives)
  ... etc

Sizes You're Receiving (last 7 days):
  300x250:  107,663 reached queries  →  You CAN serve
  336x280:    1,457 reached queries  →  You CANNOT serve (no creatives)
  360x300:   11,584 reached queries  →  You CANNOT serve (no creatives)
  392x327:      690 reached queries  →  You CANNOT serve (no creatives)
  ... etc

MATCH ANALYSIS:
  Total reached queries:     127,134
  Queries you can serve:      94,851 (74.6%)
  Queries you cannot serve:   32,283 (25.4%)  ← This is your size waste

IF YOU SET AN INCLUDE LIST with only your creative sizes:
  You would KEEP:   74.6% of current QPS
  You would LOSE:   25.4% of current QPS (can't serve anyway)
  
  ⚠️ WARNING: You would also lose any NEW sizes that appear in the future
  ⚠️ Recommendation: Review quarterly and add new high-volume sizes

OPPORTUNITY: Sizes worth creating creatives for (high volume, no coverage):
  1. 336x280 -   1,457 QPS/day  →  Standard IAB size, easy to create
  2. 360x300 -  11,584 QPS/day  →  High volume, investigate
  3. 336x300 -   3,694 QPS/day  →  Near-standard, consider
```

### Module 2: Config Performance Tracker
**Purpose:** Compare efficiency across your 10 pretargeting configs

**Output:**
```
CONFIG PERFORMANCE (last 7 days)
================================================================================

Billing ID       Name              Reached    Impressions  Efficiency  Issues
--------------------------------------------------------------------------------
72245759413      Africa/Asia       126,263    92,250       73.1%       None
151274651962     USEast CA/MX          826       420       50.8%       ⚠️ Low
83435423204      ID/BR Android          45        31       68.9%       Low volume

INVESTIGATION NEEDED:
  Config 151274651962 (USEast CA/MX) has only 50.8% efficiency
  Possible causes:
  - Size mismatch (check size distribution for this config)
  - Poor inventory quality in CA/MX
  - Pretargeting too broad
```

### Module 3: Fraud Signal Detector
**Purpose:** Flag suspicious patterns for human review (not definitive fraud detection)

**Output:**
```
FRAUD SIGNALS (requires human review)
================================================================================

⚠️ APPS WITH SUSPICIOUS PATTERNS:

App: com.sketchy.game
  - CTR: 4.2% (average for category: 0.8%)
  - Clicks: 1,247 | Impressions: 29,690
  - Pattern: Consistently high CTR over 14 days
  - Signal strength: MEDIUM
  - Recommendation: Monitor for 7 more days, consider blocking if continues

App: com.another.app  
  - Clicks exceed impressions on 3 of 7 days
  - Could be timing issue OR click injection
  - Signal strength: LOW (needs more data)
  - Recommendation: Flag for review, don't block yet

NOTE: These are patterns, not proof. Smart fraud mixes 70-80% real traffic
with 20-30% fake. Single signals are not conclusive.
```

### Module 4: Opportunity Finder (Planned)
**Purpose:** Identify cheap inventory opportunities

**Output:**
```
OPPORTUNITIES (for media buyer review)
================================================================================

HIGH-VOLUME SIZES WITHOUT CREATIVES:
  If you created creatives for these sizes, you could capture more QPS:
  
  Size      Daily QPS   Est. CPM   Opportunity
  -----------------------------------------------
  360x300   11,584      $0.80      Low competition, worth testing
  336x280    1,457      $0.85      Standard IAB, easy to create
  
ACTION: Brief creative team to produce these sizes
```

---

## The Printout Philosophy

**All RTBcat outputs are "printouts" by default.**

Why?
1. **Transparency** - AdOps can see exactly what's recommended
2. **Safety** - No accidental changes to live bidding
3. **Learning** - Team builds intuition about QPS optimization
4. **Audit trail** - Document why changes were made

The printout for size changes should look like:

```
================================================================================
RECOMMENDED PRETARGETING SIZE LIST
================================================================================

Based on analysis of your 653 creatives and 7 days of traffic data,
here are the sizes you should INCLUDE in pretargeting:

SIZES TO INCLUDE (you have creatives for these):
  300x250   ← 127 creatives, high volume
  320x50    ← 89 creatives, high volume  
  728x90    ← 45 creatives, medium volume
  160x600   ← 32 creatives, medium volume
  300x600   ← 28 creatives, medium volume
  320x100   ← 21 creatives, low volume
  ... [full list]

TO IMPLEMENT:
  1. Go to Authorized Buyers UI
  2. Navigate to Bidder Settings → Pretargeting
  3. Edit config [NAME] (Billing ID: XXXXXXX)
  4. Under "Creative dimensions", add the sizes listed above
  5. Click Save
  
  ⚠️ WARNING: Once you add ANY size, all other sizes are EXCLUDED
  ⚠️ Double-check the list before saving
  ⚠️ Monitor traffic for 24 hours after applying

SIZES NOT INCLUDED (no creatives, will be excluded):
  336x280   ← 1,457 QPS/day will be lost (can't serve anyway)
  360x300   ← 11,584 QPS/day will be lost (can't serve anyway)
  ... [full list of excluded sizes]

================================================================================
```

---

## Success Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| Size Match Rate | % of reached queries for sizes you have creatives | 90%+ |
| Impression Rate | Impressions / Reached Queries | 75%+ |
| Config Balance | Variance in efficiency across 10 configs | Low |
| Fraud Flag Rate | % of traffic flagged as suspicious | Track trend |

---

## Next Steps

1. **Import CSV data** to establish baseline metrics
2. **Map your 653 creatives** to available sizes
3. **Generate size coverage report** to see the gap
4. **Decide strategy:** 
   - Keep sizes blank (accept waste)
   - Set include list (eliminate waste, lose flexibility)
   - Hybrid (include list + quarterly review)
5. **Review with AdOps** before any pretargeting changes
6. **Implement carefully** - one config at a time
7. **Monitor for 7 days** after each change

---

**Document Author:** Claude + Jen  
**Date:** December 1, 2025  
**Version:** 2.0

**Key corrections in v2:**
- Size filtering is INCLUDE-only (not exclude)
- Adding one size excludes all others (AND logic)
- Fraud detection limited by VPN prevalence
- Most non-converting traffic is "cost of business" not waste
- Only size mismatch is true QPS waste
