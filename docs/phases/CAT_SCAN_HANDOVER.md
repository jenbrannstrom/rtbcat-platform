# Cat Scan – Engineering Handover (for VS Code AI)

_Last updated: 2025-11-26 (v0.3.0 - UX Improvements)_

This document is for any AI assistant (e.g. ChatGPT in VS Code) helping with the **Cat Scan** project.

Cat Scan is a small open-source tool that sits on a **single RTB supply path** (e.g. Truecaller → bidder) and:

- Shows which ad formats you **listen to but never bid on**
- Highlights **self-inflicted issues** (timeouts, below-floor bids, invalid responses)
- Provides simple **publisher segments** to help media buyers optimise

Long-term, Cat Scan should be easy to run **inside the user's own AWS account**, and eventually as an **AWS RTB Fabric module**, while keeping all production data private.

---

## 1. What We Have Today

### Core Components

- **fake_ssp**
  - Simulates publisher traffic with OpenRTB-style requests.
  - Includes multiple publisher IDs (3) and user segments (4).
  - Generates 4 banner formats: 300x250, 320x50, 160x600, 728x90
  - Logs requests + responses to local file OR S3 (via `LOG_DESTINATION=s3`).
  - ✅ Has Dockerfile and docker-compose support.

- **fake_bidder**
  - Mock DSP that bids **only on 300×250** impressions.
  - Verified locally and once as a **manual Fargate task**.
  - Has Dockerfile and deployment docs (fake_bidder/DEPLOY.md).

- **cat_scan** ⭐ **SIGNIFICANTLY ENHANCED IN v0.3.0**
  - Rust CLI that reads logs from **local files OR S3** (S3 support already implemented!).
  - Computes comprehensive stats by:
    - **Format** (width/height) with canonical IAB size bucketing
    - **Publisher** (multi-publisher support)
    - **Segment** (via the `--segment-stats` flag)
    - **SSP/source**
    - **Time-based** analysis (per-minute bid rate trends)
  - **NEW in v0.3.0 - Enhanced HTML Report UX:**
    - **Summary Dashboard** with 4 key metrics (Total Requests, Bid Rate, Wasted Traffic %, Problem Formats count)
    - **"Stop Listening - Wasted QPS"** section highlighting formats with zero bids
    - **Cross-tab drill-down** - click any format or publisher to see detailed breakdown
    - **Status badges** (STOP, Low, Review, Good) on all tables
    - **Volume bars** showing relative traffic per format
    - **Interactive filtering** (min requests, min bid rate, search)
    - **Sortable columns** across all tables
    - **Problem detection** (zero_bids, non_standard, low_bid_rate)
  - Outputs to `--out` directory:
    - `format_stats.csv`
    - `segment_stats.csv`
    - `report.html`
  - Has **comprehensive unit tests** for aggregation logic.
  - **Canonical size bucketing** reduces 2000+ raw sizes to ~18 IAB standards.

### Infrastructure

- **Local dev** (fully working)
  - `cargo run -p fake_bidder`
  - `cargo run -p fake_ssp`
  - `cat_scan` run against `fake_ssp_logs.jsonl` or `s3://bucket/key`
  - ✅ `docker-compose up` for full local stack
- **AWS** (✅ ready to deploy)
  - IAM user + AWS CLI configured on the dev machine.
  - All services have Dockerfiles.
  - ✅ Modular CloudFormation templates in `infra/cloudformation/`
  - ✅ EventBridge scheduling for Cat Scan runs
  - ✅ Landing page at https://rtbcat.github.io/fabric-module-1/
  - ✅ Embedded interactive demo report on landing page

---

## 2. What's Next (Roadmap)

This is the **engineering sequence** the AI should assume when proposing work.

### Immediate (Test Data & Problem Detection) - IN PROGRESS

Goal: Richer test data and expanded problem detection.

**Test data improvements needed:**
- [ ] Add more formats to fake_ssp (beyond the current 4)
- [ ] Add error simulation (timeouts, malformed responses)
- [ ] Add bid floor variation to test below-floor detection
- [ ] Add win/loss tracking (currently we only track bid/no-bid)

**Problem type expansion:**
- ✅ `zero_bids` - Format receives traffic but never gets bid on
- ✅ `non_standard` - Non-IAB format sizes
- ✅ `low_bid_rate` - Bid rate < 1% with significant volume
- [ ] `no_wins` / `low_win_rate` - Bids placed but no wins (requires win data)
- [ ] `below_floor` - Bids below bidfloor
- [ ] `timeout` - Response timeout exceeded
- [ ] `error` - Parse/protocol errors in response

**UI consideration:**
- Potentially merge Problems into Formats tab with inline status badges
- The current UX shows problems both in Summary dashboard and separate Problems tab

### Short-term (Polish & Hardening)

- [ ] Add more self-inflicted issue detection (timeouts, below-floor bids)
- [ ] Improve error handling and logging
- [ ] Add integration tests
- [ ] Public S3 bucket for CloudFormation templates (for one-click deploy)

### Long-term (RTB Fabric integration)

Goal: make Cat Scan feel like a natural **RTB Fabric module**.

- Insert AWS RTB Fabric between SSP and bidder in example architectures
- Ensure Fabric logs to S3 (or another supported sink)
- Adapt `cat_scan` to Fabric's log schema
- Package `cat_scan` as a **Fabric module** that runs inline on a link (read-only analytics)
- Provide a **Fabric-specific** "Deploy Cat Scan for RTB Fabric" flow

**Note on Fabric:** RTB Fabric is essentially a "pipe" - it passes through bid requests/responses. Error messages and win notifications would need to come from the actual SSP or be configured as part of Fabric's logging. The cat_scan tool can read whatever data Fabric logs, but Fabric doesn't generate RTB-level insights itself.

---

## 3. Repo Layout & Environment

Local project directory:

```text
~/Documents/fabric-module-1
```

This is a **Cargo workspace** with three binary crates:

```text
fabric-module-1/
  Cargo.toml        # workspace manifest
  Cargo.lock
  README.md
  CAT_SCAN_HANDOVER.md  # this file (AI handover)
  fake_ssp/         # fake publisher (SSP)
  fake_bidder/      # fake DSP/bidder
  cat_scan/         # Cat Scan CLI
  docs/             # GitHub Pages landing page + demo report
  reports/          # generated reports directory
  target/           # build artefacts
```

The user is on **Zorin OS (Ubuntu-based Linux)** with:

- Rust: `rustc 1.91.1`, `cargo 1.91.1`, `rustfmt`, `clippy`
- Build tools: `build-essential`
- Editor: **VS Code** with Rust Analyzer
- Multiple VS Code terminals:
  - One dedicated to `fake_bidder`
  - One dedicated to `fake_ssp`
  - One for `cat_scan` / AWS commands

---

## 4. Implemented Components (Details)

### 4.1 `fake_bidder`

Location: `fake_bidder/`

Purpose: a **fake bidder** that:

- Listens on `/bid` (port `3000`)
- Accepts a minimal OpenRTB-style JSON bid request
- Bids only on **300×250** impressions
- Returns an empty `seatbid` array for all other sizes (no-bid)

Tech:

- Rust + `axum` 0.7, `tokio`, `serde`, `serde_json`

Run locally:

```bash
cd ~/Documents/fabric-module-1
cargo run -p fake_bidder
```

Containerization:

- ✅ Has Dockerfile (multi-stage build with rust:1.82-slim-bookworm)
- ✅ Has buildspec.yml for AWS CodeBuild
- ✅ Has DEPLOY.md with manual deployment steps
- ✅ Has been tested as ECS Fargate task

---

### 4.2 `fake_ssp`

Location: `fake_ssp/`

Purpose: a **fake SSP / publisher** that:

- Periodically sends OpenRTB requests to `fake_bidder` with these sizes: 300×250, 320×50, 160×600, 728×90
- Includes 3 publisher IDs (`pub-news`, `pub-sports`, `pub-tech`) and 4 user segments (`automotive`, `travel`, `finance`, `entertainment`)
- Writes a simple JSONL log file, e.g. `fake_ssp_logs.jsonl`, containing records like:

  ```json
  {
    "ts_ms": 1732350000000,
    "request": { ... OpenRTB-like request with site.publisher.id and user.data.segment ... },
    "response": { ... OpenRTB-like response or {} ... }
  }
  ```

Run (in another terminal):

```bash
cd ~/Documents/fabric-module-1
cargo run -p fake_ssp
```

Environment variables:

- `BIDDER_ENDPOINT` - URL of bidder (default: `http://127.0.0.1:3000/bid`)
- `LOG_DESTINATION` - `local` or `s3` (default: `local`)
- `LOG_FILE` - Path when local (default: `fake_ssp_logs.jsonl`)
- `S3_BUCKET` - S3 bucket name when `LOG_DESTINATION=s3`
- `S3_PREFIX` - Optional prefix for S3 logs

Current limitations:

- Hard-coded to run 200 requests then exit
- Only 4 banner formats
- No error/timeout simulation
- No win notification tracking

Future work:

- Add more formats for richer test data
- Add timeout simulation (some requests sleep before responding)
- Add below-floor bid scenarios
- Optional: infinite loop mode

---

### 4.3 `cat_scan` (the main product) ⭐

Location: `cat_scan/`

Cat Scan is a **binary crate** and the main user-facing tool.

**Current capabilities (v0.3.0):**

- ✅ Reads `fake_ssp_logs.jsonl` (local file)
- ✅ Reads directly from S3 (`s3://bucket/key`)
- ✅ Aggregates by:
  - **Format** (raw width/height)
  - **Canonical format** (IAB standard size bucketing)
  - **Publisher** (multi-publisher support)
  - **Segment** (user segments)
  - **SSP** (source)
  - **Time** (per-minute buckets)
- ✅ Computes metrics:
  - Requests, bids, bid rate, avg bid price
- ✅ Detects problem formats:
  - `zero_bids` - receives traffic, never bids
  - `non_standard` - non-IAB format size
  - `low_bid_rate` - bid rate < 1% with volume
- ✅ Generates outputs:
  - `format_stats.csv`
  - `segment_stats.csv` (publishers and segments)
  - `report.html` with enhanced UX:
    - **Summary Dashboard** (4 metric cards: Total Requests, Bid Rate, Wasted Traffic, Problem Count)
    - **Stop Listening** section (wasted QPS recommendations)
    - **Formats tab** (clickable rows, drill-down, status badges, volume bars)
    - **Publishers tab** (clickable rows, drill-down)
    - **Segments tab**
    - **SSPs tab**
    - **Problems tab** (zero bids, non-standard, low bid rate)
    - Cross-tab drill-down panels
    - Search/filter controls
    - Sortable columns
- ✅ Has comprehensive unit tests (8 tests)
- ✅ Supports CLI flags:
  - `--out DIR` (recommended: outputs CSV + HTML)
  - `--min-requests N`
  - `--sort-by format|requests|bid_rate`
  - `--segment-stats` (also outputs to stderr)
  - `--time-analysis` (outputs to stderr)
  - `--html-out PATH` (legacy, deprecated)

Usage:

```bash
# Recommended: output to directory
cargo run -p cat_scan -- fake_ssp_logs.jsonl --out ./reports

# Read from S3
cargo run -p cat_scan -- s3://bucket/prefix/logs.jsonl --out ./reports

# With filtering and analysis
cargo run -p cat_scan -- logs.jsonl --min-requests 50 --segment-stats --out ./reports
```

Key code locations:
- `cat_scan/src/main.rs` - all logic in single file
  - Lines 56-101: Canonical size bucketing (IAB standards)
  - Lines 103-141: GlobalStats struct (all aggregation views)
  - Lines 475-527: Problem format detection
  - Lines 545-1121: HTML report generation (v0.3.0 UX)
  - Lines 1553-1809: Unit tests

Containerization:

- ✅ Has Dockerfile (multi-stage build)
- ✅ Part of docker-compose.yml

Future work:

- Add more problem types (no_wins, below_floor, timeout, error)
- Support streaming/continuous analysis
- Consider merging Problems into Formats tab

---

## 5. AWS & RTB Fabric Context (Current State)

### 5.1 AWS Account & CLI

- The user logs into AWS console using a **root account** (email + password), but:
  - Day-to-day AWS CLI work is done via an **IAM user**, not root.

- On the dev machine (Zorin), AWS CLI is configured:

  ```bash
  aws sts get-caller-identity
  ```

  returns an IAM user like `arn:aws:iam::<account-id>:user/jen-zorin`.

- Existing AWS resources:
  - ECR repository: `328614522524.dkr.ecr.eu-west-1.amazonaws.com/cat-scan/fake-bidder`
  - ECS cluster: `cat-scan`
  - Task definition: `fake-bidder:1`
  - Security group: `sg-0d094ee56eadfd756`
  - IAM role: `ecsTaskExecutionRole`

- ✅ CloudFormation templates in `infra/cloudformation/`:
  - Modular nested stacks (network, storage, compute, scheduling)
  - Supports new VPC or existing VPC
  - EventBridge scheduling for Cat Scan

### 5.2 RTB Fabric (future, not present yet)

- RTB Fabric is the **long-term target**:
  - Fabric gateway + link between SSP and bidder
  - Fabric logging to S3
  - Cat Scan reading Fabric logs and/or running as a Fabric module
- Today:
  - No Fabric stack is deployed for this project
  - All Cat Scan logic runs locally against `fake_ssp` logs

Assistants should **not assume** RTB Fabric already exists; treat it as a later milestone.

---

## 6. Future Deploy Flows (for real users)

This section is to guide future work on "Deploy to my AWS" experiences.

### Stage 1 – Local-only (today)

Target user:

- Developer / tinkerer
- Comfortable with `git clone` and `cargo run`

Flow:

1. Clone the repo
2. Run `fake_bidder` and `fake_ssp` locally
3. Run `cat_scan` against `fake_ssp_logs.jsonl`
4. Open generated CSV/HTML files locally

No AWS dependencies.

---

### Stage 2 – Generic AWS + S3 deploy button ✅ DONE

Target user:

- Has an AWS account
- Has **any S3-hosted RTB logs** (not necessarily Fabric)

**Implemented:**

1. ✅ Landing page at https://rtbcat.github.io/fabric-module-1/
2. ✅ "Deploy Cat Scan" button with CloudFormation Quick Create link
3. ✅ CloudFormation modular nested stacks create:
   - VPC (optional - can use existing)
   - ECR repositories for all services
   - ECS cluster with Fargate task definitions
   - S3 buckets for logs and reports
   - EventBridge schedule for Cat Scan
   - IAM roles with proper permissions
4. ✅ User configurable parameters:
   - `LogBucketName`, `ReportBucketName`
   - `ScheduleExpression` (default: hourly)
   - VPC options (create new or use existing)
5. ✅ Embedded interactive demo report on landing page

---

### Stage 3 – RTB Fabric-specific deploy (long-term)

Target user:

- Already runs **AWS RTB Fabric**
- Has production endpoints feeding into Fabric

Future Fabric-aware experience:

1. Cat Scan is documented as an **RTB Fabric analytics module**
2. Pre-flight checklist on the landing page:
   - Fabric stack is deployed and receiving traffic
   - Fabric logging to S3 is enabled (bucket + prefix known)
   - User has permissions for CloudFormation, ECS, S3, IAM
3. "Deploy Cat Scan for RTB Fabric" button (same Quick Create pattern)
4. Cat Scan reads Fabric-produced logs from S3
5. Long-term stretch: Cat Scan packaged as a **Fabric module** that runs inline on a link

---

## 7. VS Code Workflow & AI Expectations

The user typically:

1. Opens VS Code on `~/Documents/fabric-module-1`
2. Has multiple terminals:
   - Terminal A: `cargo run -p fake_bidder`
   - Terminal B: `cargo run -p fake_ssp`
   - Terminal C: `cargo run -p cat_scan -- ...` or AWS CLI
3. Uses the AI assistant inside VS Code with this handover loaded as context

For any AI assistant:

- Be explicit about **which crate and file** to edit (e.g. "Open `cat_scan/src/main.rs`")
- Provide **concrete commands** and expected outputs
- Don't assume Kubernetes or complicated infra; keep AWS steps minimal and explicit
- Treat RTB Fabric as **future work**, not something that's already wired
- **Note that cat_scan is MORE capable than initially documented** - don't suggest implementing features that already exist!
- **The target audience is senior media buyers / Ad Ops devs** - focus on optimization recommendations

---

## 8. Suggested Immediate Tasks for the AI

**Phase 1 & 2 are complete.** **Phase 2.5 (UX improvements) is also complete.**

The next priority is **improving test data** to demonstrate more problem types.

When this handover is present and the repo matches the described state, the AI should focus on:

1. **Improving fake_ssp test data generation** (current priority)

   - Add more banner formats (beyond the 4 current ones)
   - Add timeout simulation (some requests sleep)
   - Add below-floor bid scenarios
   - Add win/loss tracking (requires fake_bidder changes too)

2. **Expanding problem detection in cat_scan**

   - Add `no_wins` / `low_win_rate` detection
   - Add `below_floor` detection
   - Add `timeout` detection
   - Add `error` detection

3. **UI refinement** (optional)

   - Consider merging Problems into Formats tab with inline badges
   - Add format-per-publisher drill-down data (currently shows all publishers)

4. **RTB Fabric Integration** (next phase)

   - Research RTB Fabric log schema and integration patterns
   - Adapt `cat_scan` to read Fabric-produced logs
   - Test with real Fabric environment if available
   - Document Fabric-specific deployment flow

Keep changes incremental, well-documented, and easy to run on a modest dev machine.

---

## 9. Project Status Summary (v0.3.0)

**What's complete:**

- ✅ cat_scan reads from local files and S3
- ✅ cat_scan multi-publisher HTML reports with tabs
- ✅ cat_scan time-based analysis
- ✅ cat_scan comprehensive unit tests (8 tests)
- ✅ cat_scan canonical size bucketing (IAB standards)
- ✅ cat_scan problem format detection (zero_bids, non_standard, low_bid_rate)
- ✅ cat_scan segment and SSP analysis
- ✅ **NEW: Summary Dashboard with key metrics**
- ✅ **NEW: "Stop Listening" wasted QPS recommendations**
- ✅ **NEW: Cross-tab drill-down panels**
- ✅ **NEW: Status badges (STOP, Low, Review, Good)**
- ✅ **NEW: Volume bars on format tables**
- ✅ **NEW: Interactive filtering and search**
- ✅ Dockerfiles for all services (fake_bidder, fake_ssp, cat_scan)
- ✅ docker-compose.yml for local development
- ✅ S3 log writing for fake_ssp
- ✅ CloudFormation modular nested stacks
- ✅ Landing page with "Deploy to AWS" button
- ✅ Embedded interactive demo report on landing page
- ✅ GitHub Pages enabled

**What still needs work:**

- ❌ Richer test data (more formats, errors, timeouts, wins)
- ❌ Additional problem types (no_wins, below_floor, timeout, error)
- ❌ Format-per-publisher drill-down data
- ❌ RTB Fabric integration
- ❌ Public S3 bucket for CloudFormation templates (for one-click deploy)

**Current version:** v0.3.0 (UX Improvements Complete)
