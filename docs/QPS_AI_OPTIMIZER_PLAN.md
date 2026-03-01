# QPS AI Optimizer — Reconciled Data Model & Roadmap

**Version:** 0.7 | **Date:** 2026-03-01

---

## Executive Summary

Cat-Scan is a workaround to Google's lack of a reporting API, using CSVs. It seeks to be an RTB analytics and recommendation engine — the toolbox that gives advertisers and agencies the spanners, wrenches, and diagnostic gauges to tune their RTB operation themselves.

**Our role:** Collect the data, compile it, present it clearly, and provide the tools. The customer controls the strategy.

The path to advertiser-first optimization:

1. **Phase 0 (completed)** — Data-plumbing gaps fixed so the foundation is trustworthy.
2. **Phase 1** — Build the conversion schema. A universal database structure that can store conversion events of all types (installs, deposits, purchases, signups) regardless of where they come from.
3. **Phase 2** — Connect to conversion data sources. MMP integrations (AppsFlyer, Adjust, Branch) are the primary path since most app advertisers already use them. Secondary: agency pixels (Redtrack, Voluum), our own pixel, or bidder data feeds.
4. **Phase 3** — BYOM (Bring Your Own Model). Once we have real outcome data flowing in, let customers plug in their own AI to generate recommendations from Cat-Scan's compiled data.

### Roadmap Tracking Update (2026-03-01)

Current roadmap execution status (implemented in code, pending environment-by-environment rollout validation):

1. **Conversion connectors (Phase 2) are live in platform code**:
   - AppsFlyer, Adjust, Branch, generic postback, Redtrack/Voluum aliases, CSV upload, and lightweight pixel endpoint.
2. **Conversion readiness is now first-class**:
   - `GET /conversions/readiness` aggregates health + ingestion volume + freshness with explicit reason strings.
   - Setup/System UI now consume readiness and show buyer-scoped status + troubleshooting reasons.
   - System UI now also surfaces webhook security posture from `GET /conversions/security/status` for faster operator verification.
   - Setup checklist now includes webhook security posture summary alongside conversion readiness guidance.
3. **Operator/QA gates hardened**:
   - canary includes workflow profile controls, optional pixel checks, strict conversion-ready checks, and strict go/no-go target.
   - canary now includes optional generic webhook auth verification (401 without secret, 200 with secret) for security go/no-go runs.
   - canary now includes optional generic webhook HMAC verification (200 valid signature, 401 invalid signature) for security go/no-go runs.
   - canary now includes optional generic webhook freshness verification (200 fresh timestamp, 401 stale timestamp) and optional rate-limit verification (200 until threshold, 429 after threshold).
   - canary now includes optional `/conversions/security/status` contract checks with minimum secured-source thresholds.
   - bundled security canary target `make v1-canary-webhook-security` runs auth/HMAC/freshness/rate-limit/security-status checks in one command.
   - root `make v1-gate` now combines phase0 + conversion/readiness regression, and CI uses it.
4. **BYOM workflow controls are now operationally consistent**:
   - workflow preset/profile handling is aligned across backend API, dashboard UI, and canary wrappers.
5. **Webhook security hardening now supports secret rotation windows**:
   - provider/shared webhook secret and HMAC envs can carry multiple active secrets (comma/semicolon/newline-separated) for zero-downtime rotations.
   - `/conversions/security/status` now exposes non-secret security posture (enabled controls + rotation counts + freshness/rate-limit config) for operator verification.
   - operator runbook includes bundled webhook security canary execution (`make v1-canary-webhook-security`) for repeatable controls validation.
6. **Known UX/runtime gap (planned, not yet executed): QPS page/table hydration latency**:
   - observed on reload: prolonged `Data freshness pending...` and skeleton rows before pretargeting tables render.
   - scope is performance hardening (query/runtime + API fan-out + frontend hydration), not data-accuracy semantics.

---

## 1. Current State (Reconciled)

### 1.1 What is ingested and usable now

| Source | Primary table/path | Current status | Notes |
|---|---|---|---|
| Performance Detail / Quality-style CSV (`catscan-quality`) | `rtb_daily` | Live | Includes core delivery metrics and viewability-related fields where present |
| Bids-in-auction CSV (`catscan-bidsinauction`) | `rtb_daily` | Live | Complements quality-style report for bid-side metrics |
| RTB Funnel Geo CSV (`catscan-pipeline-geo`) | `rtb_bidstream` | Live | Funnel metrics by country/hour |
| RTB Funnel Publisher CSV (`catscan-pipeline`) | `rtb_bidstream` | Live | Funnel metrics with publisher dimension |
| Bid Filtering CSV (`catscan-bid-filtering`) | `rtb_bid_filtering` | Live | Filtering reasons and opportunity cost |
| Quality Signals / IVT CSV (dedicated report) | `rtb_quality` | Live | Unified importer writes directly to `rtb_quality`; freshness/coverage exposed in `/system/data-health` |
| Authorized Buyers API sync | Postgres + services | Live | Seats, pretargeting, endpoints, creatives |

### 1.2 Existing optimization modules

- `analytics/qps_optimizer.py`
- `analytics/recommendation_engine.py`
- `analytics/fraud_analyzer.py`
- `analytics/waste_analyzer.py`
- `analytics/geo_waste_analyzer.py`
- `analytics/size_coverage_analyzer.py`
- `analytics/pretargeting_recommender.py`

### 1.3 Blind spots that remain structural

- No live sealed-auction competitor prices.
- No full bidder-internal no-bid reason stream.
- Post-click/post-install outcomes are mostly absent unless added externally.
- Buyer intent can be intentionally different from top-line conversion (for compliant lead-gen and audience-building strategies).

### 1.4 Phase 0 Closure Notes (Completed)

Phase 0 hardening is implemented in production code paths:

1. Quality-signals ingestion is fully routed and persisted to `rtb_quality`.
2. Bidstream optional dimensions (`platform`, `environment`, `transaction_type`) are persisted instead of dropped.
3. Missingness semantics baseline now uses `NULL` for absent source columns and preserves true measured zeroes.
4. Data-health readiness checks expose report completeness, `rtb_quality` freshness, and bidstream-dimension coverage via `/system/data-health`.

**Residual risk that still requires operations discipline:** freshness and coverage can still degrade if source CSV delivery stalls. This is now observable (stateful readiness signals + canary smoke gates), not silent.

---

## 2. Phase 0 — Foundation Hardening (Completed)

**In plain English:** The trust layer for optimizer inputs is in place; continue operating it with explicit gates.

### 2.1 Data pipeline fixes

**Why this matters:** Every recommendation the optimizer makes is only as good as the data feeding it. If we're missing fraud data, dropping device-type info, or confusing "zero" with "unknown," the optimizer will make bad recommendations — and the advertiser loses money following bad advice.

1. **Quality-signals import path completed.** Dedicated quality/fraud CSV rows now land in `rtb_quality`.

2. **Device/environment/deal-type persistence completed.** Bidstream imports preserve those dimensions.

3. **"Zero" vs "unknown" semantics completed.**
   - If Google's report says "0 clicks" → store `0` (this is a real measurement — zero clicks were recorded)
   - If the clicks column isn't in the report at all → store nothing / mark as absent (this means "we have no data for this field")
   - This prevents the optimizer from punishing segments where we simply lack data

4. **Lineage + readiness visibility added.** Data-health API and UI expose readiness state, coverage, and freshness.

### 2.2 Reliability and observability

1. **Automated checks that data arrives correctly (implemented):**
   - Does the quality-signals CSV actually land in the right database table?
   - Are device/environment fields actually saved (not silently dropped)?
   - Does a missing column result in "no data" (not `0`)?

2. **Dashboard health indicators (implemented):**
   - Is the fraud/quality data fresh? (If it's 5 days old, tell the user)
   - What percentage of rows have device-type data? (If only 30%, flag it)
   - Are all 5 report types imported for each seat, each day?

### 2.3 Deliverables

**In plain English:** Hardening is complete when, for every number the optimizer uses to make a recommendation, we can answer three questions. This baseline is now in place:

- **"Is this a real zero?"** — Yes, Google measured it and it was zero. (Example: a publisher really got zero clicks. That's actionable — consider blocking it.)
- **"Is this a real non-zero value?"** — Yes, Google measured it and here's the number. (Example: this geo got 12,000 impressions at $1.40 CPM. That's solid data to optimize on.)
- **"Do we actually not know?"** — The data wasn't in the report. (Example: we don't have viewability data for this publisher. The optimizer should NOT treat this as "0% viewable" — it should say "viewability: no data" and reduce its confidence in any recommendation about this publisher.)

This matters because an optimizer that treats "no data" as "zero" will wrongly recommend blocking segments that might actually be performing well — we just haven't measured them yet.

---

## 3. The Economics: What We Know vs. What We Assume

### 3.1 We have NO advertiser revenue data

Cat-Scan sees what Google tells us in CSV reports: impressions, clicks, spend. We never see the advertiser's actual revenue, profit margins, or conversion rates. Everything about "value" is inferred.

### 3.2 Assumed-Value Model

Since we can't see real revenue, we construct an **Assumed-Value** indicator from signals we do have:

| Signal | What we observe | What it implies | Confidence |
|---|---|---|---|
| **Daily spend level** | $20/day vs $10,000/day | Higher spend = advertiser sees enough value to keep investing. A rational business doesn't burn $10K/day on ads that don't work. | Medium — could be a new campaign in testing, or an irrational buyer |
| **Spend trend** | Increasing week-over-week | Advertiser is scaling — strong signal they're profitable or at least see growth potential | Medium-High |
| **Spend trend** | Decreasing week-over-week | Advertiser may be cutting losses or seasonally adjusting | Medium |
| **Win rate** | 25% vs 2% | Higher win rate = bidder is pricing aggressively = advertiser values this inventory | Medium |
| **Bid rate** | Bidder bids on 80% of requests vs 5% | High bid rate = bidder's internal model sees value in most traffic Google Authorized Buyers sends | Medium |
| **CTR** | 2% vs 0.01% | See explanation below | Medium |
| **Sustained spending** | Active for 6+ months | Long-running = advertiser has found a sustainable unit economics model | High |

**About CTR and "gaming":**

CTR (Click-Through Rate) measures how often users click on the ad. A 2% CTR means 2 out of every 100 people who saw the ad clicked it. Higher CTR generally means the ad is relevant to the audience and placed well.

However, CTR can be artificially inflated in ways that don't reflect real user interest:
- **Misleading creatives:** An ad that says "You won a prize! Click here!" will get high CTR, but those clicks are low quality — users click out of curiosity, not genuine intent.
- **Accidental clicks:** Certain ad placements (like a tiny "X" close button that's hard to hit on mobile) cause users to click the ad by mistake. The publisher gets paid for the click, the advertiser pays for it, but no one actually wanted to engage.
- **Click farms / bot traffic:** Automated scripts or low-paid workers clicking ads to generate revenue for the publisher.

So when we see high CTR, we can't blindly assume "great ad." We use it as one signal among many, and we cross-reference it with other indicators (is viewability also high? Is the IVT rate low? Does the publisher have a pattern of suspiciously high CTR across ALL advertisers?).

**For Cat-Scan's purposes:** CTR influences the Assumed-Value score, but with lower weight than spend or win rate, precisely because it can be unreliable. When CTR is high AND other signals are healthy (low fraud, good viewability, sustained spend), it's a strong positive. When CTR is high but other signals are weak, it's a red flag.

**What Assumed-Value is NOT:**
- It is not actual revenue. We don't know if the advertiser makes $0.50 or $50 per conversion.
- It is not ROAS. We can't calculate return on ad spend without knowing what the ad spend returns.
- It does not account for the advertiser's other costs (product, fulfillment, support).

**Assumed-Value formula (proxy):**

```
Assumed_Value_Score = weighted_sum(
  spend_level_tier        x 0.25   (bucketed: <$100/d, $100-1K, $1K-10K, $10K+)
  spend_trend_7d          x 0.20   (growing/stable/declining)
  bid_rate_pct            x 0.15   (how often the bidder chooses to bid)
  win_rate_pct            x 0.15   (how aggressively the bidder prices)
  ctr_pct                 x 0.10   (user engagement, used cautiously - see above)
  account_age_months      x 0.10   (longevity = sustained value)
  viewability_pct         x 0.05   (ad was actually seen)
)
```

This gives us a 0-to-1 score that says: "Based on observable behavior, this advertiser **probably** finds value in this traffic." It's the best we can do without conversion data (Phase 1) or MMP data (Phase 2).

### 3.3 Total Cost of Operation Model

The advertiser's actual profit isn't just "revenue minus ad spend." There are infrastructure costs that eat into the bottom line. Cat-Scan should help the advertiser understand the **all-in cost** of running their RTB operation.

**What Cat-Scan needs from the user (one-time setup):**

We keep this simple. We don't ask for cost-per-million-bid-requests — most advertisers and agencies won't know that number and won't spend time calculating it. We ask for one number they do know:

| Input | Why | Example |
|---|---|---|
| `monthly_hosting_cost` | The total monthly cost of running the bidder, servers, databases, and any analytics tools — one round figure | $3,000/month |

That's it. From this single number plus the data we already have, Cat-Scan can derive:

```
TOTAL COST OF RTB OPERATION

1. MEDIA COST (what you pay Google for impressions won)
   We have this from: rtb_daily.spend_micros

2. INFRASTRUCTURE COST (what it costs to run the operation)
   User provides: monthly_hosting_cost
   This covers: bidder servers, databases, analytics, Cat-Scan, etc.
   Derived per-impression: monthly_hosting_cost / monthly_impressions

3. ALL-IN CPM = (media_spend + infra_share) / impressions x 1000
   This is the REAL cost per thousand impressions - not just
   what you paid Google, but what it actually cost you to win
   and serve those impressions including your own infrastructure.

4. OPPORTUNITY COST (the main target - see below)
   QPS allocated to low-value segments that could have gone
   to high-value segments. This is where the real savings are.
```

**The main target is not cost savings — it's getting more good impressions.**

Modern bidders are cheap to run. Colocated servers, optimized code, efficient infrastructure — the processing cost per bid request is negligible in 2026. The real waste isn't server costs. The real waste is:

> "Config X is consuming 50,000 QPS and winning 0 impressions. That's 50,000 QPS that could have gone to Config Y, which has a 25% win rate and delivers the advertiser's best-performing geo."

The optimizer's primary goal: **shift QPS from segments that produce nothing toward segments that produce the impressions the advertiser actually wants.** Cost modeling is secondary context. Getting more of the right impressions is the point.

---

## 4. Phase 1 — Conversion Schema (The Database Foundation)

### 4.1 Why this comes first

Before we can ingest conversion data from ANY source (MMP, pixel, agency tracker, bidder), we need a universal database structure that can store all types of conversion events. This is the schema — the shape of the container. We build the container first, then figure out how to fill it.

### 4.2 The app conversion funnel — what advertisers actually pay for

When dealing with app advertisers (games, fintech, utilities) or the agencies representing them, "conversion" isn't one thing — it's a ladder of increasingly valuable events:

| Step | Event | What it means | Typical payout | Who cares |
|---|---|---|---|---|
| 1 | **Install** | User downloaded and installed the app | $0.30 - $2.00 | Everyone — cheapest, easiest to get |
| 2 | **Open / First Launch** | User actually opened the app after installing | $0.50 - $3.00 | Filters out accidental installs |
| 3 | **Tutorial Complete** | User got through the intro/demo/onboarding | $1.00 - $5.00 | Shows genuine interest |
| 4 | **Level / Milestone** | User reached a specified level or used the app meaningfully | $2.00 - $15.00 | Proves retention and engagement |
| 5 | **First Deposit / Purchase** | User spent real money in the app | $10.00 - $80.00+ | The ultimate goal — a paying customer |

**Real-world example:** A gaming advertiser pays agencies:
- Install: $0.90
- First deposit: $40.00

That's a 44x difference in value between the cheapest event and the most valuable one. An optimizer that only sees "installs" and treats them all equally is missing the point entirely. What matters is how many of those installs turn into depositing users.

**For e-commerce / web advertisers:** the ladder is similar but different events:
1. Landing page visit
2. Add to cart
3. Begin checkout
4. Purchase
5. Repeat purchase

### 4.3 Data model — universal conversion events

This schema stores conversion events from any source (MMP, pixel, agency tracker, bidder feed):

```text
conversion_events
- event_id          (unique identifier for this event)
- source_type       (where the data came from: "appsflyer" | "adjust" | "branch" |
                     "pixel" | "redtrack" | "voluum" | "bidder" | "manual_csv")
- buyer_id          (which advertiser account)
- billing_id        (which pretargeting config - links back to our RTB data)
- creative_id       (which ad creative was shown)
- event_type        (what happened - see standardized list below)
- event_name        (source's own name: "af_purchase", "level_achieved", etc.)
- event_value       (money amount if applicable - e.g., $40 for first deposit)
- currency          (USD / EUR / etc.)
- country           (user's country)
- platform          (iOS / Android / Web)
- app_id            (bundle ID / package name)
- publisher_id      (where the ad was shown)
- campaign_id       (MMP or agency campaign ID)
- click_id          (links back to the click that led here)
- impression_id     (links back to the impression)
- attribution_type  (last_click | view_through | organic)
- is_retargeting    (was this a returning user, not new?)
- click_ts          (when the user clicked the ad)
- event_ts          (when the conversion happened)
- latency_seconds   (time between click and conversion)
- fraud_status      (clean | suspected | confirmed_fraud)
- raw_payload       (the full original data from the source, for debugging)
- created_at        (when we stored this record)

Standardized event_type values:
- install
- open
- registration
- tutorial_complete
- level_achieved
- first_purchase
- first_deposit
- purchase
- subscription
- add_to_cart
- checkout
- custom (for anything else - event_name has the specifics)
```

### 4.4 Daily aggregates for optimization

```text
conversion_aggregates_daily
- agg_date
- buyer_id
- billing_id        (pretargeting config - the key optimization lever)
- country
- publisher_id
- creative_id
- app_id
- source_type       (where the conversion data came from)
- event_type        (install / deposit / purchase / etc.)
- event_count       (how many conversions of this type)
- event_value_total (total monetary value)
- impressions       (joined from rtb_daily)
- clicks            (joined from rtb_daily)
- spend_usd         (joined from rtb_daily)
- cost_per_event    (spend / event_count - the CPA)
- event_rate_pct    (event_count / clicks - conversion rate)
- created_at
```

This is the foundation. Once this schema exists, we can fill it from any source.

---

## 5. Phase 2 — Connecting Conversion Data Sources

### 5.1 The reality: most app advertisers already use an MMP

Advertisers running app-install campaigns almost always use AppsFlyer, Adjust, or Branch. These platforms track the full funnel from install through to deposit/purchase. They already have the data we need — we just need to connect to it.

This is the primary integration path because:
- The data already exists (no new tracking to set up)
- It includes professional fraud detection
- It covers the full event ladder (install through to deposit)
- MMPs provide APIs specifically designed for this kind of integration

### 5.2 Primary: MMP integration (AppsFlyer, Adjust, Branch)

**How it works:**

1. Advertiser configures their MMP to send "postbacks" to Cat-Scan. A postback is a server-to-server message that says: "The click with ID abc123 resulted in an install, and later a $40 deposit."
2. Cat-Scan receives the postback, normalizes it into our universal `conversion_events` schema, and stores it.
3. The optimizer can now see: "Pretargeting config X in country PH generates installs at $0.90 but deposits at $40 — that's a 44:1 return. Config Y generates installs at $0.50 but zero deposits — that's worthless."

**Inbound endpoints:**

```
POST /conversions/appsflyer/postback   - receives AppsFlyer S2S postbacks
POST /conversions/adjust/callback      - receives Adjust callbacks
POST /conversions/branch/webhook       - receives Branch webhooks
```

Each normalizes the provider-specific format into our `conversion_events` table.

### 5.3 Secondary: Agency tracking platforms (Redtrack, Voluum, custom)

Many agencies use their own tracking platforms. These work similarly to MMPs but with different data formats:

```
POST /conversions/generic/postback     - accepts a standardized JSON payload
POST /conversions/csv/upload           - accepts CSV upload of conversion data
```

The generic endpoint accepts a simple JSON format that any agency tracker can be configured to send. The CSV upload is for agencies that prefer batch imports.

### 5.4 Tertiary: Our own pixel (optional, for web-only advertisers)

For advertisers who don't use an MMP or agency tracker (typically web/e-commerce, not app), we can offer a lightweight pixel:

```
GET /pixel/conversion?click_id=X&type=purchase&value=29.99
```

This is the simplest possible integration — a URL the advertiser places on their thank-you page. But it's limited:
- Only works on web (not in-app)
- No built-in fraud detection
- Single-event only (no funnel tracking)
- Requires cookie-based attribution (degraded by privacy changes)

**Our recommendation:** Focus engineering effort on MMP integrations. The pixel is a nice-to-have for web advertisers, not the primary path.

### 5.5 What a bidder could feed us (and what to expect)

**The reality of bidders:** Most bidders have been optimized to cost as little as possible. They process bid requests, make bid/no-bid decisions, and dump logs. They typically have very little API capability built in. Asking customers to develop new bidder features is possible, but not fast.

**If a bidder COULD feed us data, here's what would be valuable — ranked from most to least useful:**

| Priority | Data | Why it's valuable | How hard to add |
|---|---|---|---|
| 1 (gold) | **Bid price per request** | We'd know what you're willing to pay per segment — the strongest signal of perceived value | Medium — bidder already knows this, just needs to export it |
| 2 (gold) | **No-bid reasons** | Why did the bidder decline? (floor too high, budget exhausted, frequency cap, user already seen) | Medium — most bidders log this internally |
| 3 (silver) | **Internal value score** | What did the bidder's own model score this request at? | Easy if they have a model, N/A if they don't |
| 4 (silver) | **Budget utilization** | How much of the daily/campaign budget was spent? How much remains? | Easy — bidders track this |
| 5 (bronze) | **Frequency data** | How many times has this user seen this ad? | Medium — requires user ID matching |
| 6 (bronze) | **Auction clearing prices** | What was the second-highest bid? (i.e., the actual price paid) | Hard — only available from win notifications |

**Realistic integration path for bidder data:**

Most bidders will start with a daily CSV or JSON dump of aggregated data:

```
POST /bidder-feed/batch    - accepts daily batch of bid-level data
POST /bidder-feed/stream   - accepts real-time bid events (for advanced bidders)
```

Schema for bidder feed:

```text
bidder_feed_events
- feed_id
- buyer_id
- billing_id
- country
- publisher_id
- app_id
- creative_size
- platform
- feed_date
- bid_requests_received  (how many requests the bidder saw)
- bids_submitted         (how many it chose to bid on)
- no_bid_reasons         (counts by reason, e.g., {"floor_too_high": 4200, "budget_exhausted": 800})
- avg_bid_price_cpm      (average bid price in CPM)
- budget_remaining_pct   (how much budget is left)
- internal_value_score   (bidder's own quality score, if available)
- source_type            ("bidder_api" | "bidder_csv")
- raw_payload            (full original data)
- created_at
```

**What to expect realistically:** Most customers will start with items 1-2 (bid prices and no-bid reasons) via a daily CSV export. Items 3-6 are aspirational and depend on the bidder's sophistication.

---

## 6. Phase 3 — BYOM (Bring Your Own Model)

### 6.1 Why this comes last

BYOM is most powerful when there's real conversion data to optimize against (from Phase 2). Without conversions, the model can only optimize on proxy metrics (CPM, CTR, win rate). With conversions, it can optimize on what actually matters: cost per deposit, install-to-deposit ratio, ROAS.

### 6.2 Concept

**In plain English:** Cat-Scan collects the data, compiles the reports, and presents the tools. The customer's AI decides what to do with it.

We provide:
- A structured data export (the "feature vector") for each traffic segment
- An API where the customer's model sends back scores
- A recommendation engine that turns those scores into pretargeting changes
- A human approval step before anything is applied

### 6.3 Data model (control and scoring)

```text
optimization_models
- model_id
- buyer_id
- name                    ("Q1 APAC Install Model v2")
- description
- model_type              (api | rules | csv)
- endpoint_url            (where to send data for scoring)
- auth_header_encrypted
- input_schema            (what data the model expects)
- output_schema           (what format scores come back in)
- is_active
- created_at / updated_at

segment_scores
- score_id
- model_id
- buyer_id
- billing_id
- country
- publisher_id
- app_id
- creative_size
- platform
- environment
- hour
- score_date
- value_score (0..1)
- confidence (0..1)
- reason_codes
- raw_response
- created_at

qps_allocation_proposals
- proposal_id
- model_id
- buyer_id
- billing_id
- current_qps
- proposed_qps
- delta_qps
- rationale
- projected_impact
- status (draft | approved | applied | rejected)
- created_at / applied_at
```

### 6.4 Built-in fallback (no AI needed)

For customers without a data science team, provide a simple rules-based model:
- Rank by: win rate, cost per conversion (when available), CTR, viewability
- Penalize: high fraud rate, high bid filtering, zero traffic configs
- Safety: minimum QPS floor, maximum change per cycle, sample-size requirements

### 6.5 Example BYOM prompts for customers

The goal: show the customer one or two example prompts they can customize and plug into their own AI (which has access to Cat-Scan's API). The AI queries Cat-Scan data and produces recommendations. We provide the toolbox — they drive.

**Example 1: App install campaign in Southeast Asia**

```
You are an optimization model for an app-install campaign on Google Authorized Buyers.

OBJECTIVE: Maximize first-deposit conversions in the Philippines and Indonesia,
while keeping cost-per-install below $1.20.

DATA SOURCE: Query Cat-Scan API at https://api.scan.rtb.cat
- GET /analytics/rtb-funnel/configs?days=14      - config-level funnel metrics
- GET /conversions/aggregates?days=14&event_type=first_deposit  - deposit data
- GET /conversions/aggregates?days=14&event_type=install        - install data
- GET /analytics/publisher-efficiency?days=14    - publisher waste ranking

CONTEXT:
- We have seen good deposit rates on publishers in the gaming category.
- Our app is similar to [COMPETITOR APP] - target similar user demographics.
- Current best-performing configs: billing_id 157331516553 (25% win rate),
  billing_id 72245759413 (24.9% win rate).
- Three configs show zero traffic - flag for review or removal.

WHEN DECIDING ON EFFICIENCY, CONSIDER:
1. Deposit-to-install ratio (most important - an install without a deposit
   is nearly worthless at $0.90 vs $40 payout)
2. Cost per deposit (target: under $45)
3. Publisher fraud rate (reject publishers with IVT > 5%)
4. Geographic deposit concentration (which countries produce depositing users?)
5. Time-of-day patterns (are deposits concentrated in certain hours?)

OUTPUT FORMAT:
For each pretargeting config, recommend:
- Keep / Increase QPS / Decrease QPS / Pause
- Specific QPS number (current -> proposed)
- Reason (one sentence)
- Confidence level (high / medium / low)
- What data is missing that would improve this recommendation
```

**Example 2: Brand awareness campaign (no conversion data)**

```
You are an optimization model for a display brand awareness campaign.

OBJECTIVE: Maximize viewable impressions in Brazil, Mexico, and Argentina,
while keeping CPM below $2.50 and ensuring >60% viewability.

DATA SOURCE: Query Cat-Scan API at https://api.scan.rtb.cat
- GET /analytics/rtb-funnel/configs?days=7
- GET /analytics/geo-waste?days=7
- GET /analytics/publisher-efficiency?days=7

WHEN DECIDING ON EFFICIENCY, CONSIDER:
1. Viewability rate (most important - an unseen impression has zero brand value)
2. CPM (lower is better, but not at the expense of viewability)
3. Publisher quality (avoid publishers with IVT > 3%)
4. Creative size coverage (are we missing high-traffic sizes?)
5. Frequency (estimated - are we over-serving the same users?)

OUTPUT: Recommend pretargeting config changes with QPS reallocation rationale.
Flag any configs where our data quality is too low to make confident recommendations.
```

**Example 3: Lead generation campaign (sweepstakes / insurance quotes / finance)**

```
You are an optimization model for a lead generation campaign on Google Authorized Buyers.

OBJECTIVE: Maximize qualified leads (form submissions with valid contact info)
across Saudi Arabia, UAE, Egypt, and South Africa, while keeping cost-per-lead
below $8.00.

DATA SOURCE: Query Cat-Scan API at https://api.scan.rtb.cat
- GET /analytics/rtb-funnel/configs?days=14      - config-level funnel metrics
- GET /conversions/aggregates?days=14&event_type=registration  - form submissions
- GET /conversions/aggregates?days=14&event_type=custom&event_name=qualified_lead
  - leads that passed validation (real phone number, real email)
- GET /analytics/publisher-efficiency?days=14    - publisher waste ranking
- GET /analytics/geo-waste?days=14               - geographic performance

CONTEXT:
- We run sweepstakes-style landing pages that collect name, phone, and email.
- Raw form submissions are cheap ($1-3) but most are junk (fake info, bots,
  people who just want the prize and will never answer the phone).
- A "qualified lead" is one where the call center successfully reached the
  person and they showed genuine interest. These are worth $25-60 to us.
- Typical ratio: 100 form submissions -> 15-20 qualified leads (15-20% quality rate).
- Quality rate varies enormously by publisher and geo. Some publishers deliver
  40% qualified leads, others deliver 2% (mostly bots filling forms).

IMPORTANT - BEWARE OF MISLEADING METRICS:
- High CTR on a sweepstakes campaign is expected (everyone wants to "win").
  Do NOT treat high CTR as a positive signal by itself.
- High form-submission volume is NOT the goal. A publisher that delivers
  500 submissions/day at 2% quality rate is WORSE than one delivering
  50 submissions/day at 40% quality rate.
- The ONLY metric that matters is cost per QUALIFIED lead.

WHEN DECIDING ON EFFICIENCY, CONSIDER:
1. Qualified-lead rate (qualified_leads / registrations) - this is the
   single most important number. It separates real inventory from junk.
2. Cost per qualified lead (target: under $8.00)
3. Geographic quality patterns (some countries have higher bot/fake-info rates)
4. Publisher quality tier - build a ranked list:
   - Tier 1: >30% quality rate, scale these up
   - Tier 2: 15-30% quality rate, maintain
   - Tier 3: <15% quality rate, reduce or pause
   - Tier 4: <5% quality rate, block
5. Time-of-day patterns (leads submitted at 3am local time are almost
   always bots - weight daytime leads higher)
6. Device patterns (desktop leads in MENA often have higher quality
   than mobile - validate this from the data)

OUTPUT FORMAT:
For each pretargeting config, recommend:
- Keep / Increase QPS / Decrease QPS / Pause
- Specific QPS number (current -> proposed)
- Reason (one sentence)
- Publisher block list (publishers in Tier 4 that should be excluded)
- Confidence level (high / medium / low)
- What data is missing that would improve this recommendation

ALSO PROVIDE:
- Top 5 publishers by qualified-lead rate (these are your gold — protect them)
- Bottom 5 publishers by qualified-lead rate (candidates for blocking)
- Any geos where quality rate is below 10% (candidates for exclusion)
```

**The key insight:** Cat-Scan doesn't need to BE the AI. It needs to be the best possible data source for whatever AI the customer chooses to use. We collect, compile, and present. They decide.

---

## 7. CSV & Data Additions Needed (per METRICS_GUIDE.md)

### 7.1 What Google CSVs we should request that we don't currently

| Report/Dimension | Currently imported? | Value if added |
|---|---|---|
| **Deal ID / Deal Name** | Column exists in `rtb_daily` but no analyzer uses it | Distinguishes private marketplace deals (usually higher quality, fixed price) from open auction. Could reveal that PMP deals have 5x better win rate. |
| **Hour-of-day in all reports** | Available in bidstream, not always in performance detail | Enables dayparting: "Your best hours are 14:00-18:00 UTC in PH. Shift QPS to those hours." |
| **Advertiser dimension** | Column exists but unused | For multi-advertiser seats, isolates performance by advertiser |
| **Video completion quartiles** | Columns exist in `rtb_daily` (video_starts through video_completions) | For video campaigns: completion rate is a key quality signal. 50%+ VCR = good placement. |

### 7.2 What we should compute from existing data but don't surface

| Metric | Formula | Why it matters |
|---|---|---|
| **Assumed-Value per QPS** | Assumed_Value_Score x daily_spend / allocated_qps | Answers: "Is this QPS allocation earning its keep?" |
| **QPS Efficiency** | Impressions / Bid Requests | Answers: "What fraction of traffic I request do I actually use?" |
| **Effective CPM** | (media_spend + infra_share) / impressions x 1000 | Answers: "What does an impression REALLY cost me?" |
| **Config overlap score** | Geo/publisher intersection between billing_ids | Answers: "Are two of my configs bidding against each other for the same traffic?" |
| **Hourly concentration** | Distribution of hourly bid_requests | Answers: "Is my traffic spread across the day or spiked in a few hours?" |

### 7.3 What we need from conversion sources (new data, not from Google CSVs)

| Data | Source | Why |
|---|---|---|
| **Event type + value** | MMP / pixel / agency tracker | The core conversion signal. Without this, everything is proxy. |
| **Attribution type** | MMP | Last-click vs view-through. A view-through conversion is worth less confidence than a click-through one. |
| **Fraud verdict** | MMP | Professional fraud detection on the conversion itself, not just the impression. |
| **Cohort LTV** | MMP (d1, d7, d30 reports) | An install worth $0.90 today might be worth $40 in deposits over 30 days. Without LTV, we optimize for the wrong thing. |

---

## 8. Gap Analysis vs. METRICS_GUIDE.md (Updated)

| Topic | Status | Reconciled note |
|---|---|---|
| `inefficiency_signals` references | Stale/inconsistent | Align guide with current recommendation tables and workflows |
| Assumed-Value per QPS | Implemented (proxy) | Exposed via optimizer economics APIs/UI as assumed-value context (still proxy, not revenue) |
| QPS Efficiency (impressions / bid_requests) | Implemented | Exposed via optimizer economics efficiency endpoints/UI |
| Confidence scoring in UI | Partial | Surface confidence and evidence in recommendation UX |
| Hourly patterns | Backend available | Add dayparting UI/actions |
| Deal/PMP dimensions | Underused | Add analyzers and recommendation paths |
| Dedicated quality-signals ingestion | Completed | Unified import path is live; freshness/availability surfaced in readiness API + UI |
| Total Cost of Operation | Implemented baseline | Monthly hosting cost setup + Effective CPM calculations available |
| Conversion event types | Implemented baseline | Universal `conversion_events` + `conversion_aggregates_daily` schema and APIs are live |
| MMP integration | In progress (platform-complete, rollout-pending) | AppsFlyer/Adjust/Branch + generic/agency/pixel/CSV connectors shipped; production validation remains per environment/customer |

---

## 9. Implementation Priority (Reconciled)

### Phase 0 (completed): Foundation hardening

- `rtb_quality` ingestion path completed.
- Bidstream dimension persistence completed.
- Missing-vs-zero baseline semantics completed.
- Effective CPM context added with monthly hosting cost setup.
- Data-quality/readiness indicators added to API + dashboard, with canary smoke gates.

### Phase 1 (implemented baseline): Conversion schema

- `conversion_events` and `conversion_aggregates_daily` schema is live.
- Event taxonomy + normalizers are implemented.
- Aggregation job and read APIs are operational.
- Remaining work: production-volume validation, data-retention tuning, and connector-specific quality guardrails.

### Phase 2 (implemented baseline, rollout in progress): Connect conversion data sources

- AppsFlyer S2S postback receiver + normalizer implemented.
- Adjust callback receiver + normalizer implemented.
- Branch webhook receiver + normalizer implemented.
- Generic postback endpoint implemented.
- Redtrack/Voluum alias routes implemented.
- CSV upload ingestion implemented.
- Lightweight web conversion pixel implemented.
- Conversion readiness endpoint + UI surfacing + strict canary gating implemented.
- Remaining work: customer-by-customer production certification and sustained SLO checks.

### Phase 3 (2-3 weeks): BYOM model platform

- Model registry and scoring jobs.
- Proposal generation and approval workflow.
- Rules-based fallback model.
- Example BYOM prompt templates for customers.
- Assumed-Value scoring as default model (upgraded to conversion-based scoring when data is available).

### Phase 4 (in progress): QPS page load and table hydration performance

- Delivered slice (2026-03-01):
  - removed startup N+1 detail fan-out by lazy-loading pretargeting detail only for expanded/QPS-edit rows,
  - reduced initial render work by mounting `ConfigBreakdownPanel` only for the expanded row,
  - removed unused `/analytics/qps-summary` startup fetch from QPS Home to trim initial API fan-out,
  - added startup timing instrumentation to expose `time_to_first_table_row`, `time_to_table_hydrated`, and key API latencies on `window.__CATSCAN_QPS_LOAD_METRICS`,
  - added optional canary startup API latency budgets (`make v1-canary-qps-load-latency`) for `/settings/endpoints`, `/settings/pretargeting`, `/analytics/home/configs`, and `/analytics/home/endpoint-efficiency`,
  - hardened backend pretargeting query paths (`DISTINCT ON` list dedupe, `EXISTS` history billing filter, bounded pending-change ordering) and added migration `058_pretargeting_query_path_indexes.sql` for composite indexes aligned to those access paths.
  - persisted QPS screen-level load telemetry via `POST /system/ui-metrics/page-load` with percentile reporting from `GET /system/ui-metrics/page-load/summary` (migration `059_ui_page_load_metrics.sql`).
  - surfaced buyer-scoped QPS page-load SLO summary in Settings -> System (sample count, p50/p95 first-row + hydrated, latest samples, and target-status badge against p95 <= 6s/8s thresholds).
  - expanded that System SLO panel with API latency rollups (sample count + p50/p95 per API path over the last 24h) so operators can pinpoint recurring endpoint bottlenecks, not only single-sample spikes.
  - added selectable SLO lookback windows (24h/72h/7d) in System -> QPS Page-Load SLO panel for broader trend inspection.
  - aligned frontend summary client with backend rollup controls by wiring `api_rollup_limit` in `/system/ui-metrics/page-load/summary` requests.
  - added bucketed latency trends (hourly/multi-hour p95 series) to summary API + System panel for at-a-glance regression tracking over the selected window.
  - extended QPS telemetry capture into post-expansion dependent calls by measuring `/settings/pretargeting/:billing_id/detail`, `/settings/pretargeting/history`, and `/settings/pretargeting/snapshots`, and persistently posting those API latency samples after initial page hydration.
  - removed `/analytics/rtb-funnel` from startup critical path by deferring it until after pretargeting table hydration, preserving buyer-filter messaging without blocking first table readiness.
  - upgraded pretargeting list rendering to chunked infinite loading (first 60 rows, then +120 rows as scroll approaches sentinel) to keep DOM/render cost bounded on very large buyer seats.
  - memoized QPS Home config transformation/sort pipeline to reduce repeated CPU work during rerenders on large config lists.
  - fixed QPS telemetry cycle resets so buyer/day context changes start a fresh measurement window (new start mark, cleared latencies, fresh first-row/hydrated sample post), improving persisted SLO sample accuracy.
  - introduced optimistic seat readiness (fire buyer-scoped queries while seat list is still loading) with 403-aware retry suppression, reducing startup wait for users with valid cached buyer context while avoiding stale-seat retry storms.
  - removed `/analytics/home/endpoint-efficiency` from startup critical path by deferring it until pretargeting table hydration.
  - added optional canary SLO verification for recorded UI telemetry (`make v1-canary-qps-page-slo`) with p95 first-row and hydrated latency thresholds.
  - enhanced QPS page SLO canary with optional strict API-rollup gating (`CATSCAN_CANARY_QPS_PAGE_REQUIRE_API_ROLLUP=1`) to enforce per-endpoint p95 budgets from `/system/ui-metrics/page-load/summary`.
  - added `make v1-canary-qps-page-slo-strict` convenience target to run the strict rollup-enforced QPS SLO gate in one command.
  - added API contract coverage for summary rollup query controls (`api_rollup_limit`) in `tests/test_system_ui_metrics_api.py`.
  - hardened canary SLO contract checks to require `time_buckets` payload presence/non-empty behavior when QPS page samples exist.

- Add end-to-end timing instrumentation for QPS Optimizer page:
  - page-level timing marks (navigation -> first table row -> full table hydration),
  - API-level latency for `/settings/endpoints`, `/settings/pretargeting`, and dependent history/snapshot calls.
- Reduce startup API critical-path depth:
  - parallelize independent fetches,
  - keep progressive rendering so endpoint card does not block table hydration.
- Harden backend query paths used by initial QPS screen load:
  - profile and optimize slow pretargeting/history reads,
  - ensure appropriate indexes and bounded query shapes (limit/window filters).
- Define and monitor a screen-level SLO for this page:
  - target `time_to_first_table_row`: p50 <= 2.5s, p95 <= 6s,
  - target `time_to_table_hydrated`: p50 <= 4s, p95 <= 8s.
- Add canary performance assertion/reporting for this screen before GA.

---

## 10. Success Metrics

| Metric | Baseline | Target |
|---|---|---|
| Optimizer input completeness | Phase 0 baseline in place; freshness still operationally variable | >95% feature completeness for active seats |
| Recommendation confidence quality | Mixed (can't distinguish "bad" from "no data") | Confidence-calibrated actions with explicit evidence and data-availability flags |
| Conversion data availability | Zero — no conversion events stored | At least 1 MMP integrated per active customer with app campaigns |
| BYOM adoption | N/A | Customer can paste an example prompt, point their AI at Cat-Scan API, and get actionable recommendations within 30 minutes of setup |
| QPS reallocation quality | Manual guesswork | Data-driven proposals that shift QPS toward higher-converting segments |
| Time to actionable recommendation | Daily batch | Sub-daily where conversion signals exist |
| Advertiser value visibility | Proxy-heavy (Assumed-Value) | Outcome-centric (CPA per event type, deposit rate, LTV where integrated) |
| QPS screen table readiness latency | Variable; prolonged pending/skeleton states observed on reload | `time_to_first_table_row` p95 <= 6s and `time_to_table_hydrated` p95 <= 8s for canary buyers |

---

## 11. Evidence Anchors (v0.6 state)

- `importers/unified_importer.py` includes explicit `rtb_quality` routing + `import_to_rtb_quality(...)`.
- `importers/unified_importer.py` persists bidstream optional dimensions (`platform`, `environment`, `transaction_type`).
- `services/data_health_service.py` computes optimizer-readiness checks for completeness/freshness/dimension coverage.
- `api/routers/system.py` exposes readiness via `GET /system/data-health`.
- `api/routers/conversions.py` exposes conversion readiness via `GET /conversions/readiness`.
- `api/routers/conversions.py` exposes webhook security posture via `GET /conversions/security/status` (non-secret operational state).
- `services/conversion_readiness.py` centralizes readiness state logic; `tests/test_conversion_readiness.py` covers state transitions.
- `tests/test_import_foundation_contracts.py`, `tests/test_data_health_service.py`, and `tests/test_system_data_health_api.py` cover core Phase 0 behaviors.
- `scripts/v1_canary_smoke.py` and `scripts/run_v1_canary_smoke.sh` provide operational canary checks (including strict conversion-readiness/pixel gates); root `make` targets wrap execution.
- `Makefile` provides `v1-conversion-regression` and `v1-gate` for local/CI regression coverage.

---

This document is the reconciled working plan and should supersede prior versions.
