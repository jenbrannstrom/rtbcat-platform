# RTB.cat Platform

**Privacy-first, self-hosted RTB Creative Intelligence & Waste Analysis**

> 🔒 **All data stays in YOUR infrastructure** - Open source modules you install and run yourself.

**Status:** Phase 5 Complete | Phase 6-8 In Progress

---

## 🎯 What is RTB.cat?

RTB.cat is a **modular platform** for DSPs and performance bidders to:
1. Manage creatives from Google Authorized Buyers (and other SSPs)
2. Analyze RTB waste and bandwidth optimization opportunities
3. Cluster campaigns intelligently with AI
4. Run everything **privately in your own AWS/infrastructure**

### 🔐 Privacy-First Architecture

Unlike SaaS platforms, RTB.cat runs **entirely in your infrastructure:**
```
┌─────────────────────────────────────────────────────────┐
│              YOUR AWS ACCOUNT / PRIVATE VPC              │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────────────────────────────────┐             │
│  │   RTBcat Creative Intel Module         │             │
│  │   (Python Package - Open Source)       │             │
│  │   • pip install rtbcat-creative-intel  │             │
│  │   • Runs locally on your EC2/ECS       │             │
│  │   • Stores data in YOUR database       │             │
│  └────────────────────────────────────────┘             │
│                      ▲                                   │
│                      │                                   │
│  ┌────────────────────────────────────────┐             │
│  │   Web Dashboard (Static Export)        │             │
│  │   • Upload to YOUR S3 bucket            │             │
│  │   • Serve from YOUR CloudFront          │             │
│  │   • 100% client-side, zero external     │             │
│  │     calls except to YOUR local API      │             │
│  └────────────────────────────────────────┘             │
│                                                          │
│  ┌────────────────────────────────────────┐             │
│  │   YOUR Database (RDS/SQLite)            │             │
│  │   • All creative data stays here        │             │
│  │   • NEVER transmitted to RTB.cat        │             │
│  └────────────────────────────────────────┘             │
│                                                          │
└─────────────────────────────────────────────────────────┘
                          │
                          │ (Your API calls only)
                          ▼
              ┌──────────────────────────┐
              │  Google Authorized       │
              │  Buyers API              │
              └──────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│              RTB.CAT (Company)                           │
│         ZERO ACCESS TO YOUR DATA                         │
├─────────────────────────────────────────────────────────┤
│  • Distributes open-source modules (GitHub)              │
│  • Distributes web UI static builds                      │
│  • Provides documentation & support                      │
│  • NO data collection                                    │
│  • NO telemetry or tracking                              │
│  • NO SaaS backend                                       │
└─────────────────────────────────────────────────────────┘
```

**Why this matters:**
✅ You control the data  
✅ Auditable open source code  
✅ Air-gap capable (works offline except Google API)  
✅ Compliance-ready (GDPR, SOC2, your policies)  
✅ No vendor lock-in  
✅ Network analysis proves zero data exfiltration  

---

## 📦 Components

### 1. Creative Intelligence Module (`/creative-intelligence`)
**Python package - Open Source (MIT License)**

Self-hosted creative management and waste analysis engine.

**Install:**
```bash
pip install rtbcat-creative-intel
```

**Features:**
- Fetch creatives from Google Authorized Buyers API
- SQLite or PostgreSQL storage
- Multi-seat (buyer account) support
- RTB waste analysis engine
- Size normalization (2000+ sizes → ~18 IAB standards)
- VAST XML parsing for video dimensions
- REST API for programmatic access
- CLI interface for all operations

**Key Capabilities:**
- 🔍 Analyze what sizes/formats you CAN bid on vs what you're ASKED for
- 💰 Calculate QPS savings from blocking wasted traffic
- 🤖 AI-powered campaign clustering (Claude, Gemini, or rule-based)
- 📊 Actionable recommendations (block in pretargeting, add creatives, etc.)

**Data Storage:**
- Default: SQLite (single file, portable)
- Production: PostgreSQL/RDS (your instance)
- ALL data stays in YOUR infrastructure

### 2. CAT_SCAN (`/cat-scan`)
**Rust RTB analyzer - Open Source**

High-performance RTB request analyzer.

- Sits between SSP and Bidder
- Logs and analyzes bid requests in real-time
- Detects waste patterns
- Generates format/segment reports
- <50ms latency impact

### 3. Web Dashboard (`/dashboard`)
**Next.js static export - Open Source**

Beautiful UI that you upload to YOUR S3 bucket.

**Deploy:**
```bash
npm run build
aws s3 sync out/ s3://your-bucket/dashboard/
```

**Pages:**
- `/` - Home with quick actions
- `/creatives` - Creative browser with filters & virtual scrolling
- `/waste-analysis` - RTB waste visualization
- `/campaigns` - AI-clustered campaign management
- `/settings` - Configuration

**Privacy Features:**
- Pure static HTML/CSS/JS files
- NO external API calls except to YOUR backend
- NO tracking scripts or analytics
- NO CDN dependencies (everything bundled)
- Client-side only (no server-side rendering)

---

## 🚀 Quick Start

### Option 1: Local Development (Laptop)
```bash
# 1. Install Creative Intelligence module
cd creative-intelligence
pip install -e .

# 2. Initialize database and config
rtbcat init --database sqlite --path ~/.rtbcat/creatives.db

# 3. Configure Google credentials
rtbcat configure --google-creds /path/to/service-account.json

# 4. Start API server
rtbcat serve --host 0.0.0.0 --port 8000

# 5. Start Dashboard (separate terminal)
cd dashboard
npm install
npm run dev

# Access:
# - Dashboard: http://localhost:3000
# - API Docs: http://localhost:8000/docs
```

### Option 2: AWS Deployment (Production)
```bash
# 1. Use Terraform/CDK to deploy to your AWS
terraform apply -var="vpc_id=vpc-12345" -var="google_creds_secret=arn:..."

# 2. Upload Web UI to your S3
npm run build
aws s3 sync out/ s3://your-company-creative-intel/ --acl private

# 3. Access via your CloudFront distribution
https://creative-intel.your-domain.com
```

---

## 📋 Platform Progress & Roadmap

### ✅ Completed Phases (Production Ready)

| Phase | Description | Status | Details |
|-------|-------------|--------|---------|
| **1** | Creative Management | ✅ Complete | Google API integration, parsing, storage |
| **2** | Size Normalization | ✅ Complete | 2000+ sizes → 18 IAB standards |
| **3** | Multi-Seat Support | ✅ Complete | Multiple buyer accounts under one bidder |
| **4** | Waste Analysis Engine | ✅ Complete | Gap detection, QPS savings calculation |
| **5** | Dashboard UI | ✅ Complete | React 19, Tailwind, responsive design |
| **5.5** | Performance Optimization | ✅ Complete | Virtual scrolling, slim mode (26x faster) |

### 🔄 Current Phase (In Development)

| Phase | Description | Status | ETA |
|-------|-------------|--------|-----|
| **6** | **Smart Link Intelligence** | 🔄 In Progress | Week 1 |
| **6.1** | Google Auth Buyers links | 🔄 Active | |
| **6.2** | Destination URL parsing | 🔄 Active | |
| **6.3** | App store enrichment (background) | 📋 Planned | |
| **6.4** | Attribution platform detection | 📋 Planned | |

**Phase 6 Features:**
- Parse complex destination URL chains (AppsFlyer → DoubleClick → App Store)
- Intelligent categorization (attribution links, trackers, final destinations)
- Tooltips explaining each link type
- Background job to fetch app store titles (non-blocking)
- Database schema update for enriched metadata

### 🎯 Upcoming Phases (Privacy-First Refactor)

| Phase | Description | Status | ETA |
|-------|-------------|--------|-----|
| **7** | **Modularization & Privacy** | 📋 Ready | Week 2 |
| **7.1** | Extract backend into pip package | 📋 Planned | |
| **7.2** | CLI interface (rtbcat commands) | 📋 Planned | |
| **7.3** | Static web UI export (no server) | 📋 Planned | |
| **7.4** | Terraform/CDK deployment modules | 📋 Planned | |
| **7.5** | Network audit documentation | 📋 Planned | |

**Phase 7 Goals:**
- Make entire platform pip-installable: `pip install rtbcat-creative-intel`
- Zero dependency on RTB.cat servers (provable via network monitoring)
- One-command AWS deployment to client's account
- Open source all components (MIT license)
- Air-gap capable (works offline except Google API)

| Phase | Description | Status | ETA |
|-------|-------------|--------|-----|
| **8** | **AI Campaign Clustering** | 📋 Designed | Week 3 |
| **8.1** | Multi-provider AI (Claude, Gemini, rule-based) | 📋 Planned | |
| **8.2** | Campaign clustering endpoint | 📋 Planned | |
| **8.3** | Frontend "Cluster" button | 📋 Planned | |
| **8.4** | Campaign editing & management | 📋 Planned | |

**Phase 8 Features:**
- Automatically group 652+ creatives into 10-20 campaigns
- Separate by language (en_us ≠ pt_br)
- Use AI for intelligent grouping (or rule-based fallback)
- Cost-effective (Gemini free tier or Claude $0.35/run)

### 🔮 Future Phases

| Phase | Description | Priority |
|-------|-------------|----------|
| **9** | Real Traffic Integration | High |
| | • CAT_SCAN live data feed | |
| | • BigQuery/S3 traffic import | |
| | • Real-time waste detection | |
| **10** | Pretargeting Automation | Medium |
| | • One-click blocking in Google API | |
| | • Auto-update pretargeting configs | |
| | • A/B testing for changes | |
| **11** | Historical Analytics | Medium |
| | • Trend analysis over time | |
| | • Waste reduction tracking | |
| | • ROI calculation | |
| **12** | Advanced Features | Low |
| | • Alerting & notifications | |
| | • Slack/email integration | |
| | • Multi-user access control | |

---

## 🏗️ Technical Architecture

### Full System Diagram
```
┌─────────────────────────────────────────────────────────┐
│                  CLIENT'S INFRASTRUCTURE                 │
│               (Everything runs here)                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────┐     ┌──────────────┐                  │
│  │  Fake SSP    │────▶│  CAT_SCAN    │                  │
│  │  (Testing)   │     │  (Rust)      │                  │
│  └──────────────┘     └──────┬───────┘                  │
│                              │                           │
│                              ▼                           │
│                       ┌──────────────┐                   │
│                       │  Creative    │                   │
│                       │  Intelligence│◀─────────┐        │
│                       │  Module      │          │        │
│                       │  (Python)    │          │        │
│                       └──────┬───────┘          │        │
│                              │                  │        │
│                              ▼                  │        │
│                       ┌──────────────┐          │        │
│                       │  PostgreSQL  │          │        │
│                       │  or SQLite   │          │        │
│                       └──────────────┘          │        │
│                              ▲                  │        │
│                              │                  │        │
│                              │                  │        │
│                       ┌──────────────┐          │        │
│                       │  Dashboard   │──────────┘        │
│                       │  (Static UI) │                   │
│                       │  on S3       │                   │
│                       └──────────────┘                   │
│                                                          │
└─────────────────────────────────────────────────────────┘
                              │
                              │ Client's API Key
                              ▼
                   ┌────────────────────┐
                   │  Google Authorized │
                   │  Buyers API        │
                   └────────────────────┘
```

---

## 🔌 API Endpoints

### Creative Intelligence API (port 8000)

**System:**
- `GET /health` - Health check
- `GET /stats` - Aggregate statistics
- `GET /sizes` - Available creative sizes

**Creatives:**
- `GET /creatives?slim=true` - List creatives (slim mode, 26x faster)
- `GET /creatives/{id}` - Get single creative with full details
- `GET /creatives/cluster` - Get AI-clustered campaign suggestions

**Campaigns:**
- `GET /campaigns` - List campaigns
- `GET /campaigns/{id}` - Get campaign details
- `POST /campaigns/cluster` - Trigger AI clustering

**Buyer Seats:**
- `GET /seats` - List buyer accounts
- `GET /seats/{buyer_id}` - Get specific seat
- `POST /seats/discover` - Discover seats from Google API
- `POST /seats/{buyer_id}/sync` - Sync creatives for seat

**Analytics:**
- `GET /analytics/waste` - Waste analysis report
- `GET /analytics/size-coverage` - Size coverage data
- `POST /analytics/import-traffic` - Import RTB traffic data
- `POST /analytics/generate-mock-traffic` - Generate test data

**Collection:**
- `POST /collect` - Fetch creatives from Google API
- `POST /collect/sync` - Sync and update existing creatives

---

## 💾 Database Schema

**Tables:**
- `creatives` - Creative metadata, dimensions, format, buyer_id, **enriched URLs**
- `campaigns` - AI-clustered campaign groups
- `buyer_seats` - Multi-seat buyer account tracking
- `rtb_traffic` - RTB request logs for waste analysis
- `clusters` - Campaign clustering results

**New in Phase 6:**
- `creatives.destination_urls_parsed` - JSON field with smart URL breakdown
- `creatives.app_store_title` - Enriched app name (background job)
- `creatives.google_buyers_url` - Direct link to Google UI
- `creatives.primary_destination` - Final landing page/app store

---

## 🛠️ Tech Stack

| Component | Technology | License |
|-----------|------------|---------|
| Backend Module | Python 3.12, FastAPI | MIT |
| CLI Interface | Typer, Rich | MIT |
| Database | SQLite / PostgreSQL | - |
| Web Dashboard | Next.js 16, React 19 | MIT |
| Styling | Tailwind CSS | MIT |
| RTB Analyzer | Rust | MIT |
| Charts | Recharts | MIT |
| Data Fetching | TanStack React Query | MIT |
| Virtual Scrolling | @tanstack/react-virtual | MIT |

**All open source. Zero proprietary components.**

---

## 📊 Size Normalization

Reduces 2000+ creative sizes to ~18 IAB standard categories:

**IAB Standards:**
- 300x250 (Medium Rectangle)
- 728x90 (Leaderboard)
- 320x50 (Mobile Banner)
- 160x600 (Wide Skyscraper)
- 300x600 (Half Page)
- 970x250 (Billboard)
- 468x60 (Banner)
- 234x60 (Half Banner)
- 120x600 (Skyscraper)
- 336x280 (Large Rectangle)
- 180x150 (Rectangle)
- 300x1050 (Portrait)
- 970x90 (Super Leaderboard)
- 88x31 (Micro Bar)
- 120x90 (Button 1)
- 120x60 (Button 2)
- 125x125 (Square Button)
- 250x250 (Square)

**Video Formats (by aspect ratio):**
- Video 16:9 (Horizontal)
- Video 9:16 (Vertical)
- Video 1:1 (Square)
- Video 4:5 (Portrait)

**Special Cases:**
- Adaptive/Fluid (0 dimension)
- Adaptive/Responsive (1x1)

---

## 🔐 Privacy & Security

### Prove Your Data Stays Private

**1. Code Audit:**
```bash
# Search for any external calls
git clone https://github.com/rtbcat/creative-intel
grep -r "rtb.cat" .      # Result: Zero hits
grep -r "telemetry" .    # Result: Zero hits
grep -r "analytics" .    # Result: Zero hits
```

**2. Network Monitoring:**
```bash
# Monitor all outbound connections
tcpdump -i any -w traffic.pcap

# Run the module
rtbcat serve

# Analyze traffic
wireshark traffic.pcap

# You'll see ONLY:
# ✓ googleapis.com (your Google API calls)
# ✓ localhost:8000 (your browser to your API)
# ✗ NO traffic to rtb.cat servers
```

**3. Air-Gap Test:**
```bash
# Download module offline
pip download rtbcat-creative-intel -d ./packages

# Transfer to air-gapped server
# Install without internet
pip install --no-index --find-links=./packages rtbcat-creative-intel

# Works 100% offline (except Google API which YOU control)
```

### Compliance-Ready

- ✅ **GDPR** - All data in your EU region
- ✅ **SOC2** - Runs in your audited infrastructure
- ✅ **CCPA** - No third-party data sharing
- ✅ **Data Residency** - You choose the AWS region
- ✅ **Audit Logs** - All in your CloudWatch
- ✅ **Encryption** - Your KMS keys

---

## 📚 Documentation

- [Creative Intelligence Handover v5](docs/RTBcat_Platform_Handover_v5.md)
- [CAT_SCAN Handover](docs/CAT_SCAN_HANDOVER.md)
- [Privacy Architecture](docs/PRIVACY.md) *(coming in Phase 7)*
- [Deployment Guide](docs/DEPLOYMENT.md) *(coming in Phase 7)*
- [Network Audit Guide](docs/NETWORK_AUDIT.md) *(coming in Phase 7)*

### Component READMEs:
- [Creative Intelligence Module](creative-intelligence/README.md)
- [CAT_SCAN](cat-scan/README.md)
- [Dashboard](dashboard/README.md)

---

## 💰 Pricing Model

| Edition | Price | What's Included |
|---------|-------|-----------------|
| **Community** | **FREE** | Full features, MIT license, community support (GitHub issues) |
| **Professional** | **$2,499/year** | Priority email/Slack support, installation assistance |
| **Enterprise** | **Custom** | Custom features, SLA, phone support, training, dedicated engineer |

**Support Contracts (Optional):**
- Basic: $500/month (email support, 48h response)
- Premium: $2,000/month (Slack + phone support, 4h response)
- Enterprise: $5,000/month (dedicated Slack channel, 1h response, custom features)

**Professional Services:**
- Setup & deployment: $5,000-15,000
- Custom integrations: $10,000-50,000
- Training: $2,000/day
- Module bundles (Creative Intel + FCFS Gateway + RTB Fabric): Custom pricing

**No per-seat fees. No usage limits. No data lock-in.**

---

## 🤝 Contributing

We welcome contributions! This is open source (MIT License).

**Ways to contribute:**
- Report bugs (GitHub issues)
- Submit feature requests
- Contribute code (pull requests)
- Improve documentation
- Share usage examples

**Development setup:**
```bash
git clone https://github.com/rtbcat/creative-intel
cd creative-intel
pip install -e ".[dev]"
pytest tests/
```

---

## 📞 Support & Community

**Free Support:**
- GitHub Issues: https://github.com/rtbcat/creative-intel/issues
- Documentation: https://docs.rtb.cat
- Community Discord: https://discord.gg/rtbcat

**Paid Support:**
- Email: support@rtb.cat
- Enterprise: enterprise@rtb.cat

**Developer:** Jen (jen@rtb.cat)  
**Website:** https://rtb.cat  
**Status Page:** https://status.rtb.cat

---

## 📜 License

**MIT License** - Use freely, modify, distribute, even commercially.

See [LICENSE](LICENSE) file for details.

---

## 🎉 Get Started

### Quick Start (5 minutes):
```bash
# Install
pip install rtbcat-creative-intel

# Initialize
rtbcat init

# Configure Google API
rtbcat configure --google-creds creds.json

# Start API
rtbcat serve

# Access dashboard
open http://localhost:8000/docs
```

### Production Deployment (30 minutes):
```bash
# Clone repo
git clone https://github.com/rtbcat/creative-intel

# Use Terraform
cd terraform/
terraform init
terraform apply

# Upload UI to your S3
cd ../dashboard
npm run build
aws s3 sync out/ s3://your-bucket/
```

**Your data. Your infrastructure. Your control.** 🔒

---

**Last Updated:** November 30, 2025  
**Version:** 6.0 (Phase 6 in progress)  
**Status:** Production-ready core + Privacy refactor planned