# CAT_SCAN - RTB Path Explorer

RTB traffic analyzer that sits between SSP and Bidder to detect waste patterns and optimization opportunities.

## Overview

CAT_SCAN is a Rust-based RTB analyzer that helps you understand what's happening on your supply path:

- Which ad formats you **listen to but never bid on**
- Where you're hurting yourself (timeouts, below-floor bids, invalid responses)
- Publisher-specific labels that make optimization easier

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   fake_ssp   │────▶│   cat_scan   │────▶│ fake_bidder  │
│  (Publisher) │     │  (Analyzer)  │     │    (DSP)     │
└──────────────┘     └──────────────┘     └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │    Reports   │
                     │  (CSV/HTML)  │
                     └──────────────┘
```

## Components

This workspace contains three Rust crates:

### fake_ssp
Simulates a publisher/SSP sending OpenRTB 2.5 bid requests:
- Configurable banner sizes (300x250, 320x50, 160x600, etc.)
- Variable bidfloors
- Multiple placement IDs (inbox_top, missed_call, etc.)

### fake_bidder
Simulates a DSP/bidder responding to bid requests:
- Configurable bid logic
- Response delays for timeout testing
- Below-floor bid simulation

### cat_scan
The core analyzer that processes RTB logs:
- Reads request/response pairs
- Generates format waste reports
- Identifies optimization opportunities

## Quick Start

### Prerequisites
- Rust (latest stable)
- Cargo

### Build
```bash
cd cat-scan
cargo build --release
```

### Run with Docker Compose
```bash
docker-compose up
```

This starts:
- fake_ssp on port 8080
- fake_bidder on port 8081
- cat_scan analyzer

### Run Individually
```bash
# Terminal 1: Start fake bidder
cargo run -p fake_bidder

# Terminal 2: Start fake SSP
cargo run -p fake_ssp

# Terminal 3: Run analyzer
cargo run -p cat_scan
```

## Configuration

### fake_ssp
Environment variables:
- `BIDDER_URL`: Target bidder endpoint (default: `http://localhost:8081/bid`)
- `QPS`: Requests per second (default: 10)
- `LOG_PATH`: Where to write request logs

### fake_bidder
Environment variables:
- `PORT`: Listen port (default: 8081)
- `BID_RATE`: Percentage of requests to bid on (default: 0.3)
- `TIMEOUT_RATE`: Percentage of artificial timeouts (default: 0.05)

### cat_scan
Environment variables:
- `LOG_PATH`: Path to RTB logs
- `OUTPUT_PATH`: Where to write reports
- `REPORT_FORMAT`: `csv` or `html`

## Reports

CAT_SCAN generates several report types:

### Format Stats (`format_stats.csv`)
Shows bid rates by ad format:
```csv
format,requests,bids,bid_rate,waste_pct
300x250,10000,3500,0.35,0.65
320x50,8000,400,0.05,0.95
160x600,5000,50,0.01,0.99
```

### Segment Stats (`segment_stats.csv`)
Shows performance by placement:
```csv
segment,requests,bids,avg_cpm,timeout_rate
inbox_top,5000,2000,2.50,0.02
missed_call,3000,500,1.20,0.08
```

### HTML Report
Visual dashboard with charts showing:
- Format waste breakdown
- Timeout analysis
- Below-floor bid patterns

## Documentation

- [Full Documentation](../docs/CAT_SCAN_README.md)
- [Project Handover](../docs/CAT_SCAN_HANDOVER.md)

## Development

```bash
# Run tests
cargo test

# Run with debug logging
RUST_LOG=debug cargo run -p cat_scan

# Format code
cargo fmt

# Lint
cargo clippy
```

## License

Open source - see LICENSE file for details.
