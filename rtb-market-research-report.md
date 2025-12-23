# RTB Product Opportunity Research Report: Cat-Scan Market Validation

**Date:** December 22, 2025

## Executive Summary

**Key Finding: The QPS Optimization market is too small to build a sustainable business on.**

Evidence across Reddit, LinkedIn, Google, and **two major Slack communities (13,000+ combined members)** shows minimal market activity for independent RTB bidders and QPS optimization specifically.

**Critical Discovery:** Even the AdOps Slack #programmatic channel (8,058 members) that explicitly mentions "QPS" in its description contains **zero discussions** about QPS optimization for bidders—all discussions are publisher-side (GAM, header bidding, fill rates).

Adjacent markets—particularly **DV360/Google Ads tooling**—show significantly higher engagement and pain points.

---

## Part 1: QPS Optimization Market Validation

### Reddit (r/adops) Research

| Search Term | Results | Key Finding |
|-------------|---------|-------------|
| "QPS" | ~20 posts | Very low engagement (2-3 votes typical) |
| "pretargeting" | 0 results | No discussion at all |
| "authorized buyers" | Few posts | Low engagement |

**Most relevant post found:**
- "Google Adx is limiting our QPS" (3y ago, 3 votes, 2 comments)
- Describes exact Cat-Scan pain point: DSP limited to 1,000 QPS, catch-22 situation
- **But only 3 votes and 2 comments = very small community**

### LinkedIn Job Search

| Search Query | Results | Analysis |
|--------------|---------|----------|
| "authorized buyers RTB" | **0 jobs** | CRITICAL: No market signal |
| "DSP programmatic engineer" | 500+ | ALL hardware DSP (Digital Signal Processing), not advertising |
| "programmatic advertising bidding" | 2000+ | Mostly PPC/Google Ads roles; only 1 RTB infrastructure role found |

**Verdict:** Zero jobs for RTB infrastructure suggests the market of independent bidders is extremely small.

### Google Authorized Buyers Documentation
- Visited developers.google.com/authorized-buyers/rtb/start
- Large vendor list exists but vendors are established SSPs/DSPs, not independent bidders

---

## Part 2: Adjacent Market Opportunities

### 2E. DV360/Google Ads Tooling - HIGHEST POTENTIAL

**Reddit search "DV360 frustration" showed SIGNIFICANTLY higher engagement:**

| Post Title | Engagement |
|------------|------------|
| "Massive issues with Reporting in DV360" | 5 votes, 9 comments |
| "DV360 Spending Inconsistencies" | 11 comments |
| "40% Discrepancy between GA to DV360" | 14 comments |
| "Need a DV360 expert help" | 8 votes, 12 comments |

**Recurring pain points:**
- Reporting problems and discrepancies
- Campaign complexity
- Integration with GA4
- Spending inconsistencies

**Market size:** Thousands of agencies and advertisers use DV360.

### 2D. Cross-Platform Reporting

| Post Title | Engagement |
|------------|------------|
| "How do I track ROI without manually compiling reports?" | 5 votes, 14 comments (recent) |
| "Rev share from all SSP partners" | 18 votes, 16 comments |
| "Cross-device attribution" | 8 votes, 11 comments |

**Existing competition:** Funnel.io, Supermetrics, etc. (heavily funded).

### 2A. Creative Trafficking/Management

| Post Title | Engagement |
|------------|------------|
| "Is trafficking hard?" | 1 vote, 19 comments |
| "Best Software for Ad Trafficking" | 5 votes, 16 comments |
| "Trafficking Automation Tool for Various Ad Servers?" | 7 votes, 8 comments |

**Insight:** Interest in automation exists; manual processes remain common.

### 2B. Campaign Pacing/Budget Management

| Post Title | Engagement |
|------------|------------|
| "Need to build my own pacing report" | 4 votes, 6 comments (12y old) |
| "The Trade Desk - Pulling Pacing Reports" | 4 votes, 2 comments |
| "Pacing Automation Recommendations" | 1 vote, 0 comments |

**Verdict:** Low engagement. DSPs have built-in pacing; not urgent pain.

### 2C. Blocklist Management

| Post Title | Engagement |
|------------|------------|
| "Anyone Willing To Share A DSP Site Blocklist?" | 5 votes, 11 comments |
| "Categories exclusion in DV360" | 2 votes, 1 comment |

**Verdict:** Moderate interest but small market.

---

## Part 3: Open Source Distribution Channels

### GitHub Adtech Ecosystem
- **Prebid.js** - Dominant open source adtech project
- **Ad-papers** (4.4k stars) - Academic papers on computational advertising
- **OpenAdServer** - Mentioned on Reddit (17 votes, 16 comments, 22d ago)

### Hacker News Adtech Discussions

| Project | Points | Comments | Notes |
|---------|--------|----------|-------|
| Jitsu (YC S20) - Open-source Segment alternative | 265 | 110 | Founder from GetIntent (ad-tech) |
| Nous - Agent framework | 155 | 37 | From TrafficGuard (ad-tech company) |
| IAB Taxonomy Mapper | 3 | 0 | Adtech-specific, low interest |

**Critical insight:** Open source projects from adtech backgrounds succeed on HN when solving **BROADER problems** (data collection, automation), not adtech-specific problems.

---

## Part 4: Slack Community Research

### AdTechGod Community Slack - BUY-SIDE FOCUS

**Community Size:** ~4,000 members per major channel

| Channel | Members | Focus |
|---------|---------|-------|
| atg-lobby-mentorship | 4,218 | Main lobby |
| media-buying-by-adlibdsp | 3,930 | Media buying (sponsored by AdLib DSP) |
| ctv-by-innovid | 3,789 | CTV/Connected TV |
| ai-by-openads | 3,744 | AI in advertising |
| mobile | 3,553 | Mobile advertising |
| adtech-martech-podcasts | 3,372 | Podcasts/promotion |
| retail-media-by-kevel | 3,221 | Retail Media |
| measurement | 3,202 | Measurement/Attribution |

**Key Observations:**
- Heavily **BUY-SIDE focused** (advertisers, agencies, brands)
- Many channels **sponsored by vendors** (Mediaocean, Kevel, Admiral, AdLib)
- **NO channels** dedicated to DSP/RTB infrastructure
- **NO discussions** about QPS optimization, pretargeting, or RTB infrastructure
- Topics: AI-generated ads, CTV, mobile, retail media, measurement
- Notable members: Brian O'Kelley (AppNexus founder) active in AI channel

### AdOps Slack (Reddit AdOps) - PUBLISHER/SUPPLY-SIDE FOCUS

**Community Size:** ~9,000 members per major channel (MUCH LARGER)

| Channel | Members | Description |
|---------|---------|-------------|
| general | 9,354 | Team-wide communication |
| adtech | 9,321 | General adtech |
| careerhelp | 9,160 | Career help |
| dfp | 9,028 | Google Ad Manager (GAM) issues |
| headerbidding | 8,852 | Header bidding for pubs/exchanges |
| random | 8,111 | General chat |
| **programmatic** | **8,058** | **"RTB, SSP, DSP, QPS, CPM, etc."** |
| conferences | 7,595 | Conference logistics |
| publishers | 2,067 | Publisher-focused discussions |
| **buyside** | **1,319** | Buy-side (MUCH SMALLER) |
| headerbidding-dev | 1,148 | Header bidding developers |

**Key Observations:**
- Clearly **PUBLISHER-FOCUSED** (supply-side)
- #programmatic channel mentions "QPS" in description BUT discussions are about:
  - GAM monetization and fill rates
  - Amazon APS account issues/cancellations
  - Header bidding setup
  - DSP migration (Xandr → Amazon DSP)
  - MCM (Multiple Customer Management)
- **NO discussions** specifically about QPS optimization for bidders
- The "QPS" in channel description refers to **publisher-side concerns** (receiving bid requests), not DSP-side optimization
- #buyside channel has only 1,319 members vs 9,000+ for publisher channels

### Critical Insight from Slack Research

**The #programmatic channel (8,058 members) explicitly mentions "RTB, SSP, DSP, QPS" but:**

1. Discussions are publisher-focused (supply-side)
2. No evidence of independent RTB bidders discussing QPS optimization
3. Community is about publishers working with SSPs and header bidding
4. Even "buyside" channel is 7x smaller than publisher channels
5. Recent discussions: Xandr deprecation, Amazon APS issues, GAM fill rates

**This confirms: The adtech community is dominated by:**
- **Publishers (supply-side):** GAM, header bidding, SSP connections
- **Media buyers (demand-side):** Using DSPs like DV360, TTD, Amazon DSP - **NOT building their own**

---

## Part 5: DV360 Deep Dive - Pain Points & Tooling Gap Analysis

### DV360 Pain Points Summary

#### 1. UI Complexity & Learning Curve
- Steep learning curve, especially for beginners
- Unintuitive interface for campaign management
- Creative management is unstructured
- Poor documentation availability publicly

#### 2. Reporting & Data Discrepancies
- **GA4 integration issues**: Post-click vs post-view tracking causes 10-40% discrepancies
- Reports hang/fail for days (reported in Google forums)
- Attribution model mismatches between platforms
- UTM code conflicts causing inflated session counts

#### 3. Pacing & Budget Problems
- Overspend on first days due to "learning" phase
- Underspend when KPI targets are too aggressive
- Flight ASAP pacing removed in Nov 2024 - forced migration to Flight Ahead
- Budget allocation between line items requires constant rebalancing

#### 4. Delivery & Targeting Issues
- Line items not spending due to:
  - Frequency caps too low
  - Creative approval delays (24+ hours)
  - Reach below 20k cookies
- Google Active View conflicts with bid optimization
- Audience targeting has limited reach on non-AdX inventory

#### 5. Access & Cost Barriers
- **$50,000-$100,000 minimum monthly spend** required
- Platform fees 10-15% of media spend (often opaque)
- Not accessible to small businesses or individual affiliates

### Existing DV360 Solutions

#### Official Google Tools

| Tool | What It Does | Limitations |
|------|--------------|-------------|
| Structured Data Files (SDF) | Bulk edit via CSV files | Manual process, error-prone |
| DV360 API | Programmatic campaign management | Requires engineering resources |
| dv360-automation (GitHub) | Code snippets for API | Workshop examples, not production-ready |
| dv360-bidbyweather (GitHub) | Weather-based bid adjustments | Single use case, Apps Script |

#### Third-Party Data Connectors (Reporting Only)

| Tool | DV360 Support | Limitations |
|------|---------------|-------------|
| Funnel.io | 500+ connectors including DV360 | Reporting only, no campaign management |
| Supermetrics | 120+ connectors | Reporting only, no campaign management |
| Improvado | Enterprise data pipeline | Expensive, reporting only |

#### DSP Alternatives (Not Tools)
- **The Trade Desk** - More transparent pricing, UID2.0, broader CTV/audio access
- **Amazon DSP** - E-commerce focused, rich shopper data
- **Eskimi** - Self-service alternative with lower minimums

### Gap Analysis - What's MISSING

**Critical Finding: Existing tools solve REPORTING (getting data OUT), but NOT operations (managing campaigns).**

| Need | Existing Solutions | Gap Status |
|------|-------------------|------------|
| Pull DV360 data into dashboards | Funnel, Supermetrics, Improvado | ✅ Solved |
| Bulk edit campaigns via spreadsheet | Google SDF | ⚠️ Exists but clunky |
| Automated pacing alerts | None | ❌ **Gap** |
| Cross-platform budget optimization | None | ❌ **Gap** |
| Automated QA/validation before launch | None (DIY only) | ❌ **Gap** |
| Creative approval tracking | None | ❌ **Gap** |
| Anomaly detection (spend issues) | None | ❌ **Gap** |
| Simplified campaign templating | None | ❌ **Gap** |

### Specific Unmet Needs

#### 1. Pacing Monitoring & Alerts
- No tool proactively alerts when line items are over/underspending
- Manual checking required daily
- Overpacing is a known, documented issue with no automated solution

#### 2. Pre-Launch QA Automation
- Common mistakes include wrong targeting, wrong budgets, wrong frequency caps
- No validation tool exists before campaigns go live
- Agencies rely on manual checklists

#### 3. Multi-DSP Campaign Management
- Agencies use DV360 + TTD + Amazon DSP simultaneously
- No unified interface for managing across platforms
- Manual reconciliation required

#### 4. Simplified Campaign Templating
- Creating similar campaigns is repetitive
- SDF is powerful but complex (CSV editing)
- No user-friendly "campaign cloning" tool with guardrails

### Why This Gap Exists

1. **Google's incentive**: Keep users in DV360 UI = more time on platform
2. **API complexity**: DV360 API requires significant engineering investment
3. **Fragmented market**: Agencies build internal tools, don't productize them
4. **Enterprise focus**: Existing vendors (Funnel, Supermetrics) focus on reporting, not operations

### Recommended Product Opportunity: **DV360 Pacing Monitor**

**Why this is the best first product:**
1. **Clear pain point** - Overspend/underspend mentioned repeatedly in forums
2. **Technically feasible** - Bid Manager API provides pacing data
3. **No direct competition** - Nobody has built this
4. **Low barrier to MVP** - Read-only, alerting only
5. **Land-and-expand** - Start with alerts, expand to automation

**Potential Features:**
- Daily pacing email/Slack alerts
- Dashboard showing all line items with pacing status
- Anomaly detection (sudden spend changes)
- Budget forecast based on current pacing
- Integration with Google Sheets for simple setup

---

## Final Rankings by Opportunity

| Rank | Opportunity | Evidence Strength | Market Size | Competition | Expertise Fit | Overall Score |
|------|-------------|-------------------|-------------|-------------|---------------|---------------|
| **1** | **DV360/Google Ads Tooling** | Strong | Large | Low-Medium | Good | ★★★★★ |
| 2 | Cross-Platform Reporting | Moderate | Large | **HIGH** | Medium | ★★★ |
| 3 | Creative Trafficking | Moderate | Medium | Medium | Medium | ★★★ |
| 4 | Campaign Pacing | Low | Medium | Low | Good | ★★ |
| 5 | Blocklist Management | Low-Moderate | Small-Medium | Low | Good | ★★ |
| **6** | **QPS Optimization (Cat-Scan)** | Weak | **VERY SMALL** | Low | Excellent | ★ |

---

## Recommendations

### Primary Recommendation: Pivot to DV360/Google Ads Tooling

**Why:**
1. **Significantly higher pain point evidence** - Multiple Reddit posts with 10+ comments about specific frustrations
2. **Larger addressable market** - Thousands of agencies vs. dozens of independent bidders
3. **Good expertise fit** - RTB/programmatic background applies to understanding DV360 data flows
4. **Lower competition** - Google's native tools are clunky; third-party ecosystem is immature

### If Pursuing Open Source:
- Solve problems **broader than adtech** (data pipelines, automation)
- Follow Jitsu model: adtech expertise → open source data tool → HN success
- Don't release adtech-specific tools (IAB Taxonomy Mapper got 3 points)

### What NOT to Do:
- Don't build for the QPS optimization market alone
- The independent RTB bidder market is too small (zero LinkedIn jobs, minimal Reddit engagement)
- Cat-Scan solves a real problem for those who have it, but there aren't enough of them

---

## Sources

**Reddit r/adops:**
- https://www.reddit.com/r/adops/search/?q=QPS
- https://www.reddit.com/r/adops/search/?q=DV360+frustration
- https://www.reddit.com/r/adops/search/?q=creative+trafficking
- https://www.reddit.com/r/adops/search/?q=campaign+pacing
- https://www.reddit.com/r/adops/search/?q=blocklist

**LinkedIn:** Job search for "authorized buyers RTB", "programmatic advertising bidding"

**GitHub:** Prebid.js, OpenAdServer

**Hacker News:** hn.algolia.com search for "adtech open source"

**Google:** developers.google.com/authorized-buyers/rtb/start

**Slack Communities:**
- AdTechGod Community Slack - Channels: #ai-by-openads, #media-buying-by-adlibdsp, #ctv-by-innovid, #mobile, #retail-media-by-kevel, #measurement
- AdOps Slack (Reddit AdOps) - Channels: #programmatic, #headerbidding, #dfp, #buyside, #publishers, #headerbidding-dev

**DV360 Research:**
- Google DV360 Bulk Tools: https://developers.google.com/display-video/bulk-tools
- DV360 Automation GitHub: https://github.com/google/dv360-automation
- DV360 API Apps Script Samples: https://github.com/google-marketing-solutions/dv360-api-appsscript-samples
- Funnel.io DV360 Connector: https://funnel.io/all-data-sources/dv-360
- Improvado DV360 Guide: https://improvado.io/blog/what-is-dv360
- Adswerve DV360 Troubleshooting: https://adswerve.com/blog/why-is-my-line-item-not-spending-a-dv360-troubleshooting-guide
- Adswerve Common DV360 Mistakes: https://adswerve.com/blog/top-10-mistakes-marketers-make-in-googles-display-video-360
- DV360 vs Trade Desk Comparison: https://improvado.io/blog/dv360-vs-the-trade-desk
- DV360 Pacing Documentation: https://support.google.com/displayvideo/answer/3114676
- Flight ASAP Pacing Removal: https://ppc.land/dv360-flight-asap-pacing-to-be-removed-in-november-2024/
