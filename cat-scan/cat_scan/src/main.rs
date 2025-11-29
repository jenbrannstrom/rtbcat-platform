use std::{
    cmp::Ordering,
    collections::BTreeMap,
    env,
    fs::File,
    io::{BufRead, BufReader, Cursor},
};

use anyhow::{bail, Context, Result};
use aws_sdk_s3::Client as S3Client;
use serde::Deserialize;
use serde_json::Value;

/// One log line from fake_ssp_logs.jsonl.
#[derive(Deserialize)]
struct LogRecord {
    request: Value,
    #[serde(default)]
    response: Value,
    #[serde(default)]
    ts_ms: Option<u64>,
}

#[derive(Debug, Default, PartialEq, Clone)]
struct FormatStats {
    requests: u64,
    bids: u64,
    sum_bid_price: f64,
}

/// Stats for time-based analysis (per minute bucket)
#[derive(Debug, Default)]
struct TimeStats {
    requests: u64,
    bids: u64,
    sum_bid_price: f64,
    min_ts: u64,
    max_ts: u64,
}

/// Key for publisher aggregation
#[derive(Debug, Clone, Ord, PartialOrd, Eq, PartialEq)]
struct PublisherKey {
    ssp: String,
    publisher_id: String,
}

/// Key for segment aggregation
#[derive(Debug, Clone, Ord, PartialOrd, Eq, PartialEq)]
struct SegmentKey {
    ssp: String,
    segment: String,
}

/// Canonical size families - maps raw sizes to standard IAB sizes
fn canonical_size(w: u32, h: u32) -> (u32, u32) {
    // Common IAB standard sizes and their tolerance ranges
    let standards: &[((u32, u32), (u32, u32), (u32, u32))] = &[
        // (canonical, min, max)
        ((300, 250), (290, 240), (310, 260)),   // Medium Rectangle
        ((320, 50), (310, 45), (330, 55)),      // Mobile Leaderboard
        ((320, 100), (310, 90), (330, 110)),    // Large Mobile Banner
        ((728, 90), (718, 85), (738, 95)),      // Leaderboard
        ((160, 600), (150, 590), (170, 610)),   // Wide Skyscraper
        ((300, 600), (290, 590), (310, 610)),   // Half Page
        ((970, 250), (960, 240), (980, 260)),   // Billboard
        ((970, 90), (960, 85), (980, 95)),      // Large Leaderboard
        ((468, 60), (458, 55), (478, 65)),      // Full Banner
        ((120, 600), (110, 590), (130, 610)),   // Skyscraper
        ((250, 250), (240, 240), (260, 260)),   // Square
        ((336, 280), (326, 270), (346, 290)),   // Large Rectangle
        ((180, 150), (170, 140), (190, 160)),   // Rectangle
        ((300, 100), (290, 90), (310, 110)),    // 3:1 Rectangle
        ((320, 480), (310, 470), (330, 490)),   // Mobile Interstitial
        ((480, 320), (470, 310), (490, 330)),   // Mobile Interstitial Landscape
        ((1024, 768), (1014, 758), (1034, 778)), // Tablet Interstitial
        ((768, 1024), (758, 1014), (778, 1034)), // Tablet Interstitial Portrait
    ];

    for &(canonical, (min_w, min_h), (max_w, max_h)) in standards {
        if w >= min_w && w <= max_w && h >= min_h && h <= max_h {
            return canonical;
        }
    }

    // Not a standard size - return as-is (will be flagged as non-standard)
    (w, h)
}

/// Check if a size is a standard IAB size
fn is_standard_size(w: u32, h: u32) -> bool {
    let canonical = canonical_size(w, h);
    // If canonical matches common standards, it's standard
    let standards: &[(u32, u32)] = &[
        (300, 250), (320, 50), (320, 100), (728, 90), (160, 600),
        (300, 600), (970, 250), (970, 90), (468, 60), (120, 600),
        (250, 250), (336, 280), (180, 150), (300, 100), (320, 480),
        (480, 320), (1024, 768), (768, 1024),
    ];
    standards.contains(&canonical)
}

/// Global stats container with multiple aggregation views
#[derive(Debug, Default)]
struct GlobalStats {
    /// Raw format stats (original w,h)
    by_raw_format: BTreeMap<(u32, u32), FormatStats>,

    /// Canonical size bucket stats
    by_canonical_format: BTreeMap<(u32, u32), FormatStats>,

    /// Per-publisher stats
    by_publisher: BTreeMap<PublisherKey, FormatStats>,

    /// Per-segment stats
    by_segment: BTreeMap<SegmentKey, FormatStats>,

    /// Per-SSP/source stats
    by_ssp: BTreeMap<String, FormatStats>,

    /// Time-based stats (per minute bucket)
    time_stats: BTreeMap<u64, TimeStats>,
}

/// Problem formats identified during analysis
#[derive(Debug, serde::Serialize)]
struct ProblemFormat {
    w: u32,
    h: u32,
    requests: u64,
    bids: u64,
    bid_rate: f64,
    problem_type: String,
}

impl GlobalStats {
    fn new() -> Self {
        Self::default()
    }
}

#[derive(Debug, Clone, Copy)]
enum SortBy {
    Format,
    RequestsDesc,
    BidRateDesc,
}

#[derive(Debug)]
struct Config {
    input_path: String,
    min_requests: u64,
    sort_by: SortBy,
    html_out: Option<String>,
    out_dir: Option<String>,
    time_analysis: bool,
    segment_stats: bool,
}

#[derive(serde::Serialize, Clone)]
struct FormatSummary {
    w: u32,
    h: u32,
    requests: u64,
    bids: u64,
    bid_rate: f64,
    avg_bid_price: f64,
}

#[derive(serde::Serialize)]
struct PublisherSummary {
    ssp: String,
    publisher_id: String,
    requests: u64,
    bids: u64,
    bid_rate: f64,
    avg_bid_price: f64,
}

#[derive(serde::Serialize)]
struct SegmentSummary {
    ssp: String,
    segment: String,
    requests: u64,
    bids: u64,
    bid_rate: f64,
    avg_bid_price: f64,
}

#[derive(serde::Serialize)]
struct SspSummary {
    ssp: String,
    requests: u64,
    bids: u64,
    bid_rate: f64,
    avg_bid_price: f64,
}

/// Complete report data for HTML generation
#[derive(serde::Serialize)]
struct HtmlReportData {
    source: String,
    total_requests: u64,
    total_publishers: u64,
    total_raw_formats: u64,
    total_canonical_formats: u64,
    min_requests_filter: u64,
    formats: Vec<FormatSummary>,
    publishers: Vec<PublisherSummary>,
    segments: Vec<SegmentSummary>,
    ssps: Vec<SspSummary>,
    problems: Vec<ProblemFormat>,
}

fn parse_args() -> Result<Config> {
    let mut args = env::args().skip(1);
    let input_path = match args.next() {
        Some(p) => p,
        None => bail!(
            "Usage: cat_scan <path_or_s3_uri> [OPTIONS]\n\n\
             Options:\n  \
             --min-requests N           Only show formats with >= N requests\n  \
             --sort-by format|requests|bid_rate\n  \
             --out DIR                  Output directory for CSV and HTML files\n  \
             --html-out PATH            Generate HTML report at PATH (deprecated, use --out)\n  \
             --time-analysis            Show bid rate trends over time\n  \
             --segment-stats            Show per-publisher and per-segment stats\n\n\
             Examples:\n  \
             cat_scan fake_ssp_logs.jsonl --out ./reports\n  \
             cat_scan s3://bucket/logs.jsonl --out ./reports\n  \
             cat_scan logs.jsonl --time-analysis --segment-stats"
        ),
    };

    let mut min_requests: u64 = 0;
    let mut sort_by = SortBy::Format;
    let mut html_out: Option<String> = None;
    let mut out_dir: Option<String> = None;
    let mut time_analysis = false;
    let mut segment_stats = false;

    let rest: Vec<String> = args.collect();
    let mut i = 0;
    while i < rest.len() {
        match rest[i].as_str() {
            "--min-requests" => {
                let value = rest
                    .get(i + 1)
                    .context("--min-requests requires a numeric value")?;
                min_requests = value
                    .parse::<u64>()
                    .context("invalid value for --min-requests")?;
                i += 2;
            }
            "--sort-by" => {
                let value = rest
                    .get(i + 1)
                    .context("--sort-by requires one of: format|requests|bid_rate")?;
                sort_by = match value.as_str() {
                    "format" => SortBy::Format,
                    "requests" => SortBy::RequestsDesc,
                    "bid_rate" => SortBy::BidRateDesc,
                    other => bail!(
                        "unknown sort key '{other}', expected one of: format|requests|bid_rate"
                    ),
                };
                i += 2;
            }
            "--html-out" => {
                let value = rest
                    .get(i + 1)
                    .context("--html-out requires a file path")?;
                html_out = Some(value.clone());
                i += 2;
            }
            "--out" => {
                let value = rest
                    .get(i + 1)
                    .context("--out requires a directory path")?;
                out_dir = Some(value.clone());
                i += 2;
            }
            "--time-analysis" => {
                time_analysis = true;
                i += 1;
            }
            "--segment-stats" => {
                segment_stats = true;
                i += 1;
            }
            other => bail!("Unknown argument: {other}"),
        }
    }

    Ok(Config {
        input_path,
        min_requests,
        sort_by,
        html_out,
        out_dir,
        time_analysis,
        segment_stats,
    })
}

/// Process a single log record and update all GlobalStats views
fn process_record_global(record: &LogRecord, global: &mut GlobalStats) {
    // Extract (w, h) from request.imp[0].banner.{w,h}
    let w = record.request["imp"][0]["banner"]["w"]
        .as_u64()
        .unwrap_or(0) as u32;
    let h = record.request["imp"][0]["banner"]["h"]
        .as_u64()
        .unwrap_or(0) as u32;

    if w == 0 || h == 0 {
        return;
    }

    // Check for bid
    let has_bid = record
        .response
        .get("seatbid")
        .and_then(|v| v.as_array())
        .map(|arr| !arr.is_empty())
        .unwrap_or(false);

    let bid_price = if has_bid {
        record
            .response
            .get("seatbid")
            .and_then(|v| v.as_array())
            .and_then(|arr| arr.first())
            .and_then(|sb| sb.get("bid"))
            .and_then(|bids| bids.as_array())
            .and_then(|bids_arr| bids_arr.first())
            .and_then(|b| b.get("price"))
            .and_then(|p| p.as_f64())
            .unwrap_or(0.0)
    } else {
        0.0
    };

    // Helper to update FormatStats
    let update_stats = |entry: &mut FormatStats| {
        entry.requests += 1;
        if has_bid {
            entry.bids += 1;
            entry.sum_bid_price += bid_price;
        }
    };

    // 1. Raw format stats
    update_stats(global.by_raw_format.entry((w, h)).or_default());

    // 2. Canonical format stats
    let canonical = canonical_size(w, h);
    update_stats(global.by_canonical_format.entry(canonical).or_default());

    // 3. Extract SSP (from request.source.ssp or similar)
    let ssp = record
        .request
        .get("source")
        .and_then(|s| s.get("ssp"))
        .and_then(|v| v.as_str())
        .unwrap_or("")
        .to_string();

    // Update SSP stats
    if !ssp.is_empty() {
        update_stats(global.by_ssp.entry(ssp.clone()).or_default());
    }

    // 4. Publisher stats
    if let Some(pub_id) = record
        .request
        .get("site")
        .and_then(|s| s.get("publisher"))
        .and_then(|p| p.get("id"))
        .and_then(|id| id.as_str())
    {
        let key = PublisherKey {
            ssp: ssp.clone(),
            publisher_id: pub_id.to_string(),
        };
        update_stats(global.by_publisher.entry(key).or_default());
    }

    // 5. Segment stats
    if let Some(seg_id) = record
        .request
        .get("user")
        .and_then(|u| u.get("data"))
        .and_then(|d| d.as_array())
        .and_then(|arr| arr.first())
        .and_then(|data| data.get("segment"))
        .and_then(|s| s.as_array())
        .and_then(|arr| arr.first())
        .and_then(|seg| seg.get("id"))
        .and_then(|id| id.as_str())
    {
        let key = SegmentKey {
            ssp: ssp.clone(),
            segment: seg_id.to_string(),
        };
        update_stats(global.by_segment.entry(key).or_default());
    }

    // 6. Time-based stats
    if let Some(ts_ms) = record.ts_ms {
        let minute_bucket = ts_ms / 60000;
        let entry = global.time_stats.entry(minute_bucket).or_default();
        entry.requests += 1;

        if entry.min_ts == 0 || ts_ms < entry.min_ts {
            entry.min_ts = ts_ms;
        }
        if ts_ms > entry.max_ts {
            entry.max_ts = ts_ms;
        }

        if has_bid {
            entry.bids += 1;
            entry.sum_bid_price += bid_price;
        }
    }
}

/// Parse an S3 URI like s3://bucket/key into (bucket, key)
fn parse_s3_uri(uri: &str) -> Option<(String, String)> {
    let stripped = uri.strip_prefix("s3://")?;
    let (bucket, key) = stripped.split_once('/')?;
    Some((bucket.to_string(), key.to_string()))
}

/// Download an object from S3 and return its contents as bytes
async fn download_from_s3(client: &S3Client, bucket: &str, key: &str) -> Result<Vec<u8>> {
    let resp = client
        .get_object()
        .bucket(bucket)
        .key(key)
        .send()
        .await
        .with_context(|| format!("Failed to download s3://{bucket}/{key}"))?;

    let bytes = resp
        .body
        .collect()
        .await
        .with_context(|| "Failed to read S3 object body")?
        .into_bytes()
        .to_vec();

    Ok(bytes)
}

/// Process lines from a reader and aggregate into GlobalStats
fn process_lines_global<R: BufRead>(reader: R, global: &mut GlobalStats) -> Result<()> {
    for (line_no, line) in reader.lines().enumerate() {
        let line = line.with_context(|| format!("Failed to read line {}", line_no + 1))?;
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }

        let record: LogRecord = serde_json::from_str(trimmed)
            .with_context(|| format!("Failed to parse JSON on line {}", line_no + 1))?;

        process_record_global(&record, global);
    }
    Ok(())
}

/// Identify problem formats from the stats
fn find_problem_formats(global: &GlobalStats, min_volume_threshold: u64) -> Vec<ProblemFormat> {
    let mut problems = Vec::new();

    for (&(w, h), stats) in &global.by_raw_format {
        let rate = if stats.requests == 0 {
            0.0
        } else {
            stats.bids as f64 / stats.requests as f64
        };

        // Problem: Zero-bid formats with significant volume
        if stats.bids == 0 && stats.requests >= min_volume_threshold {
            problems.push(ProblemFormat {
                w,
                h,
                requests: stats.requests,
                bids: stats.bids,
                bid_rate: rate,
                problem_type: "zero_bids".to_string(),
            });
            continue;
        }

        // Problem: Non-standard sizes with meaningful volume
        if !is_standard_size(w, h) && stats.requests >= min_volume_threshold {
            problems.push(ProblemFormat {
                w,
                h,
                requests: stats.requests,
                bids: stats.bids,
                bid_rate: rate,
                problem_type: "non_standard".to_string(),
            });
            continue;
        }

        // Problem: Very low bid rate (< 1%) with significant volume
        if rate < 0.01 && stats.requests >= min_volume_threshold && stats.bids > 0 {
            problems.push(ProblemFormat {
                w,
                h,
                requests: stats.requests,
                bids: stats.bids,
                bid_rate: rate,
                problem_type: "low_bid_rate".to_string(),
            });
        }
    }

    // Sort by requests descending
    problems.sort_by(|a, b| b.requests.cmp(&a.requests));
    problems
}

fn bid_rate(stat: &FormatStats) -> f64 {
    if stat.requests == 0 {
        0.0
    } else {
        stat.bids as f64 / stat.requests as f64
    }
}

fn avg_bid_price(stat: &FormatStats) -> f64 {
    if stat.bids == 0 {
        0.0
    } else {
        stat.sum_bid_price / stat.bids as f64
    }
}

fn write_html_report_full(path: &str, report: &HtmlReportData) -> Result<()> {
    let json_data = serde_json::to_string(report)
        .context("Failed to serialize report to JSON")?;

    let html = format!(
        r#"<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cat Scan Report</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        h1 {{ color: #333; margin-bottom: 10px; }}
        .meta {{ color: #666; margin-bottom: 20px; font-size: 14px; }}

        /* Summary Dashboard */
        .summary-dashboard {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 25px; }}
        .metric-card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); text-align: center; }}
        .metric-card.alert {{ border-left: 4px solid #dc3545; }}
        .metric-card.warning {{ border-left: 4px solid #ffc107; }}
        .metric-card.success {{ border-left: 4px solid #28a745; }}
        .metric-value {{ font-size: 2rem; font-weight: 700; color: #333; }}
        .metric-label {{ font-size: 0.85rem; color: #666; margin-top: 5px; text-transform: uppercase; letter-spacing: 0.5px; }}
        .metric-detail {{ font-size: 0.8rem; color: #999; margin-top: 3px; }}

        /* Stop Listening Section */
        .stop-listening {{ background: #fff5f5; border: 1px solid #ffcccc; border-radius: 8px; padding: 20px; margin-bottom: 25px; }}
        .stop-listening h3 {{ color: #dc3545; margin: 0 0 15px 0; font-size: 1rem; display: flex; align-items: center; gap: 8px; }}
        .stop-listening-list {{ display: flex; flex-wrap: wrap; gap: 10px; }}
        .stop-item {{ background: white; border: 1px solid #ffcccc; border-radius: 6px; padding: 10px 15px; display: flex; flex-direction: column; min-width: 140px; cursor: pointer; transition: all 0.2s; }}
        .stop-item:hover {{ border-color: #dc3545; box-shadow: 0 2px 8px rgba(220,53,69,0.2); }}
        .stop-item .format {{ font-weight: 600; color: #333; }}
        .stop-item .waste {{ font-size: 0.85rem; color: #dc3545; }}
        .stop-item .action {{ font-size: 0.75rem; color: #666; margin-top: 4px; }}

        .tabs {{ display: flex; gap: 5px; margin-bottom: 20px; flex-wrap: wrap; }}
        .tab {{ padding: 10px 20px; background: white; border: none; border-radius: 8px 8px 0 0; cursor: pointer; font-size: 14px; transition: all 0.2s; }}
        .tab:hover {{ background: #e9ecef; }}
        .tab.active {{ background: #4a90a4; color: white; }}
        .tab .tab-count {{ background: rgba(0,0,0,0.1); padding: 2px 6px; border-radius: 10px; font-size: 11px; margin-left: 5px; }}
        .tab.active .tab-count {{ background: rgba(255,255,255,0.2); }}
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
        .controls {{ background: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); display: flex; flex-wrap: wrap; gap: 15px; align-items: center; }}
        .controls label {{ display: flex; align-items: center; gap: 8px; }}
        .controls input {{ padding: 5px 10px; border: 1px solid #ddd; border-radius: 4px; width: 80px; }}
        .controls input[type="text"] {{ width: 200px; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #4a90a4; color: white; cursor: pointer; user-select: none; }}
        th:hover {{ background: #3d7a8c; }}
        th.sorted-asc::after {{ content: " ▲"; }}
        th.sorted-desc::after {{ content: " ▼"; }}
        tr {{ transition: background 0.15s; }}
        tr:hover {{ background: #f0f7fa; }}
        tr.clickable {{ cursor: pointer; }}
        tr.clickable:hover {{ background: #e3f2fd; }}
        .no-bid {{ color: #999; }}
        .high-bid-rate {{ color: #28a745; font-weight: bold; }}
        .low-bid-rate {{ color: #dc3545; }}
        .problem {{ color: #dc3545; }}
        .summary {{ margin-top: 20px; padding: 15px; background: white; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .badge {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; margin-left: 5px; }}
        .badge-warning {{ background: #fff3cd; color: #856404; }}
        .badge-danger {{ background: #f8d7da; color: #721c24; }}
        .badge-success {{ background: #d4edda; color: #155724; }}
        .badge-stop {{ background: #dc3545; color: white; font-weight: 600; }}
        .header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }}
        .header a {{ text-decoration: none; }}
        .logo {{ height: 60px; }}
        .header-text h1 {{ margin: 0; }}

        /* Drill-down panel */
        .drill-down {{ display: none; background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
        .drill-down.active {{ display: block; }}
        .drill-down h4 {{ margin: 0 0 15px 0; color: #333; display: flex; justify-content: space-between; align-items: center; }}
        .drill-down .close-btn {{ background: none; border: none; font-size: 1.2rem; cursor: pointer; color: #666; }}
        .drill-down .close-btn:hover {{ color: #333; }}
        .drill-down-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; }}
        .drill-down-section {{ background: white; padding: 15px; border-radius: 6px; }}
        .drill-down-section h5 {{ margin: 0 0 10px 0; font-size: 0.9rem; color: #666; }}
        .mini-table {{ font-size: 0.85rem; }}
        .mini-table td {{ padding: 6px 10px; }}

        /* Volume bar */
        .volume-bar {{ width: 60px; height: 8px; background: #e9ecef; border-radius: 4px; display: inline-block; vertical-align: middle; margin-left: 8px; }}
        .volume-bar-fill {{ height: 100%; background: #4a90a4; border-radius: 4px; }}

        footer {{ margin-top: 40px; padding: 20px; text-align: center; color: #666; font-size: 12px; border-top: 1px solid #ddd; }}
        footer a {{ color: #4a90a4; text-decoration: none; }}
        footer a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Cat Scan Report</h1>
            <a href="https://rtb.cat" target="_blank">
                <img src="data:image/svg+xml;base64,{logo_base64}" alt="RTB Cat Logo" class="logo">
            </a>
        </div>
        <div class="meta">
            Source: {source} | Formats: {total_canonical} canonical ({total_raw} raw) | Publishers: {total_publishers}
        </div>

        <!-- Summary Dashboard -->
        <div class="summary-dashboard" id="summaryDashboard"></div>

        <!-- Stop Listening Recommendations -->
        <div class="stop-listening" id="stopListening" style="display: none;">
            <h3><span style="font-size: 1.2rem;">&#9888;</span> Stop Listening - Wasted QPS</h3>
            <div class="stop-listening-list" id="stopListeningList"></div>
        </div>

        <div class="tabs">
            <button class="tab active" data-tab="formats">Formats <span class="tab-count" id="formatsCount">0</span></button>
            <button class="tab" data-tab="publishers">Publishers <span class="tab-count" id="publishersCount">0</span></button>
            <button class="tab" data-tab="segments">Segments <span class="tab-count" id="segmentsCount">0</span></button>
            <button class="tab" data-tab="ssps">SSPs <span class="tab-count" id="sspsCount">0</span></button>
            <button class="tab" data-tab="problems">Problems <span class="tab-count" id="problemsCount">0</span></button>
        </div>

        <!-- Drill-down panel -->
        <div class="drill-down" id="drillDown">
            <h4>
                <span id="drillDownTitle">Details</span>
                <button class="close-btn" onclick="closeDrillDown()">&times;</button>
            </h4>
            <div class="drill-down-grid" id="drillDownContent"></div>
        </div>

        <div id="formats" class="tab-content active">
            <div class="controls">
                <label>Min Requests: <input type="number" id="minRequests" value="{min_requests}" min="0"></label>
                <label>Min Bid Rate: <input type="number" id="minBidRate" value="0" min="0" max="100" step="1">%</label>
                <label>Search: <input type="text" id="formatSearch" placeholder="e.g. 300x250"></label>
            </div>
            <table id="formatsTable">
                <thead><tr>
                    <th data-col="format" data-sort="format">Format</th>
                    <th data-col="requests" data-sort="requests">Requests</th>
                    <th data-col="bids" data-sort="bids">Bids</th>
                    <th data-col="bid_rate" data-sort="bid_rate">Bid Rate</th>
                    <th data-col="avg_bid_price" data-sort="avg_bid_price">Avg Price</th>
                    <th>Status</th>
                </tr></thead>
                <tbody></tbody>
            </table>
            <div class="summary" id="formatsSummary"></div>
        </div>

        <div id="publishers" class="tab-content">
            <div class="controls">
                <label>Search: <input type="text" id="publisherSearch" placeholder="Publisher ID..."></label>
            </div>
            <table id="publishersTable">
                <thead><tr>
                    <th data-sort="publisher_id">Publisher</th>
                    <th data-sort="ssp">SSP</th>
                    <th data-sort="requests">Requests</th>
                    <th data-sort="bids">Bids</th>
                    <th data-sort="bid_rate">Bid Rate</th>
                    <th data-sort="avg_bid_price">Avg Price</th>
                    <th>Status</th>
                </tr></thead>
                <tbody></tbody>
            </table>
        </div>

        <div id="segments" class="tab-content">
            <table id="segmentsTable">
                <thead><tr>
                    <th>Segment</th>
                    <th>SSP</th>
                    <th>Requests</th>
                    <th>Bids</th>
                    <th>Bid Rate</th>
                    <th>Avg Price</th>
                </tr></thead>
                <tbody></tbody>
            </table>
        </div>

        <div id="ssps" class="tab-content">
            <table id="sspsTable">
                <thead><tr>
                    <th data-sort="ssp">SSP</th>
                    <th data-sort="requests">Requests</th>
                    <th data-sort="bids">Bids</th>
                    <th data-sort="bid_rate">Bid Rate</th>
                    <th data-sort="avg_bid_price">Avg Price</th>
                    <th>Status</th>
                </tr></thead>
                <tbody></tbody>
            </table>
        </div>

        <div id="problems" class="tab-content">
            <table id="problemsTable">
                <thead><tr>
                    <th>Format</th>
                    <th>Requests</th>
                    <th>Bids</th>
                    <th>Bid Rate</th>
                    <th>Problem Type</th>
                    <th>Action</th>
                </tr></thead>
                <tbody></tbody>
            </table>
        </div>
    </div>
    <script>
        const REPORT = {json_data};
        let currentSort = {{ col: 'requests', dir: 'desc' }};
        let maxRequests = Math.max(...REPORT.formats.map(f => f.requests), 1);

        // Calculate summary metrics
        function calculateSummary() {{
            const totalReq = REPORT.formats.reduce((sum, f) => sum + f.requests, 0);
            const totalBids = REPORT.formats.reduce((sum, f) => sum + f.bids, 0);
            const bidRate = totalReq > 0 ? (totalBids / totalReq) : 0;

            const zeroBidFormats = REPORT.formats.filter(f => f.bids === 0);
            const wastedRequests = zeroBidFormats.reduce((sum, f) => sum + f.requests, 0);
            const wastePercent = totalReq > 0 ? (wastedRequests / totalReq) : 0;

            const problemCount = REPORT.problems.length;
            const healthyFormats = REPORT.formats.filter(f => f.bid_rate >= 0.1).length;

            return {{ totalReq, totalBids, bidRate, wastedRequests, wastePercent, problemCount, healthyFormats, zeroBidFormats }};
        }}

        // Render summary dashboard
        function renderSummary() {{
            const s = calculateSummary();
            const dashboard = document.getElementById('summaryDashboard');

            const bidRateClass = s.bidRate >= 0.3 ? 'success' : (s.bidRate >= 0.1 ? '' : 'warning');
            const wasteClass = s.wastePercent > 0.3 ? 'alert' : (s.wastePercent > 0.1 ? 'warning' : '');
            const problemClass = s.problemCount > 5 ? 'alert' : (s.problemCount > 0 ? 'warning' : 'success');

            dashboard.innerHTML = `
                <div class="metric-card">
                    <div class="metric-value">${{s.totalReq.toLocaleString()}}</div>
                    <div class="metric-label">Total Requests</div>
                    <div class="metric-detail">${{s.totalBids.toLocaleString()}} bids placed</div>
                </div>
                <div class="metric-card ${{bidRateClass}}">
                    <div class="metric-value">${{(s.bidRate * 100).toFixed(1)}}%</div>
                    <div class="metric-label">Bid Rate</div>
                    <div class="metric-detail">${{s.healthyFormats}} healthy formats</div>
                </div>
                <div class="metric-card ${{wasteClass}}">
                    <div class="metric-value">${{(s.wastePercent * 100).toFixed(1)}}%</div>
                    <div class="metric-label">Wasted Traffic</div>
                    <div class="metric-detail">${{s.wastedRequests.toLocaleString()}} requests, 0 bids</div>
                </div>
                <div class="metric-card ${{problemClass}}">
                    <div class="metric-value">${{s.problemCount}}</div>
                    <div class="metric-label">Problem Formats</div>
                    <div class="metric-detail">Needs attention</div>
                </div>
            `;

            // Stop listening recommendations
            if (s.zeroBidFormats.length > 0) {{
                const stopSection = document.getElementById('stopListening');
                const stopList = document.getElementById('stopListeningList');

                // Sort by requests descending (biggest waste first)
                const sorted = [...s.zeroBidFormats].sort((a, b) => b.requests - a.requests).slice(0, 8);

                stopList.innerHTML = sorted.map(f => `
                    <div class="stop-item" onclick="drillDownFormat(${{f.w}}, ${{f.h}})">
                        <span class="format">${{f.w}}x${{f.h}}</span>
                        <span class="waste">${{f.requests.toLocaleString()}} wasted req</span>
                        <span class="action">Click to investigate &rarr;</span>
                    </div>
                `).join('');

                stopSection.style.display = 'block';
            }}
        }}

        // Tab switching
        document.querySelectorAll('.tab').forEach(tab => {{
            tab.addEventListener('click', () => {{
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(tab.dataset.tab).classList.add('active');
                closeDrillDown();
            }});
        }});

        // Get status badge
        function getStatusBadge(bidRate, requests) {{
            if (bidRate === 0 && requests > 10) return '<span class="badge badge-stop">STOP</span>';
            if (bidRate < 0.05 && requests > 10) return '<span class="badge badge-danger">Low</span>';
            if (bidRate < 0.2) return '<span class="badge badge-warning">Review</span>';
            if (bidRate >= 0.5) return '<span class="badge badge-success">Good</span>';
            return '';
        }}

        // Volume bar HTML
        function volumeBar(requests) {{
            const pct = Math.min(100, (requests / maxRequests) * 100);
            return `<span class="volume-bar"><span class="volume-bar-fill" style="width:${{pct}}%"></span></span>`;
        }}

        // Render formats table
        function renderFormats() {{
            const minReq = parseInt(document.getElementById('minRequests').value) || 0;
            const minRate = (parseFloat(document.getElementById('minBidRate').value) || 0) / 100;
            const search = document.getElementById('formatSearch').value.toLowerCase();

            let filtered = REPORT.formats.filter(r =>
                r.requests >= minReq &&
                r.bid_rate >= minRate &&
                (search === '' || `${{r.w}}x${{r.h}}`.includes(search))
            );

            // Sort
            filtered.sort((a, b) => {{
                let aVal, bVal;
                switch(currentSort.col) {{
                    case 'format': aVal = a.w * 10000 + a.h; bVal = b.w * 10000 + b.h; break;
                    case 'requests': aVal = a.requests; bVal = b.requests; break;
                    case 'bids': aVal = a.bids; bVal = b.bids; break;
                    case 'bid_rate': aVal = a.bid_rate; bVal = b.bid_rate; break;
                    case 'avg_bid_price': aVal = a.avg_bid_price; bVal = b.avg_bid_price; break;
                    default: aVal = a.requests; bVal = b.requests;
                }}
                return currentSort.dir === 'asc' ? aVal - bVal : bVal - aVal;
            }});

            const tbody = document.querySelector('#formatsTable tbody');
            tbody.innerHTML = '';
            let totalReq = 0, totalBids = 0;

            filtered.forEach(r => {{
                totalReq += r.requests;
                totalBids += r.bids;
                const tr = document.createElement('tr');
                tr.className = 'clickable';
                tr.onclick = () => drillDownFormat(r.w, r.h);
                const rateClass = r.bid_rate === 0 ? 'no-bid' : (r.bid_rate >= 0.5 ? 'high-bid-rate' : (r.bid_rate < 0.05 ? 'low-bid-rate' : ''));
                tr.innerHTML = `
                    <td><strong>${{r.w}}x${{r.h}}</strong></td>
                    <td>${{r.requests.toLocaleString()}}${{volumeBar(r.requests)}}</td>
                    <td>${{r.bids.toLocaleString()}}</td>
                    <td class="${{rateClass}}">${{(r.bid_rate * 100).toFixed(2)}}%</td>
                    <td>${{r.avg_bid_price.toFixed(4)}}</td>
                    <td>${{getStatusBadge(r.bid_rate, r.requests)}}</td>
                `;
                tbody.appendChild(tr);
            }});

            const overallRate = totalReq > 0 ? (totalBids / totalReq * 100).toFixed(2) : '0.00';
            document.getElementById('formatsSummary').innerHTML = `<strong>Showing:</strong> ${{filtered.length}} formats, ${{totalReq.toLocaleString()}} requests, ${{totalBids.toLocaleString()}} bids (${{overallRate}}% bid rate)`;
            document.getElementById('formatsCount').textContent = REPORT.formats.length;
        }}

        // Drill down into a format - show which publishers/SSPs send it
        function drillDownFormat(w, h) {{
            const format = `${{w}}x${{h}}`;
            document.getElementById('drillDownTitle').textContent = `Format: ${{format}}`;

            // Find related publishers (we don't have format-per-publisher data yet, so show all)
            const content = document.getElementById('drillDownContent');
            const formatData = REPORT.formats.find(f => f.w === w && f.h === h);

            content.innerHTML = `
                <div class="drill-down-section">
                    <h5>Format Details</h5>
                    <table class="mini-table">
                        <tr><td>Requests</td><td><strong>${{formatData?.requests.toLocaleString() || 0}}</strong></td></tr>
                        <tr><td>Bids</td><td><strong>${{formatData?.bids.toLocaleString() || 0}}</strong></td></tr>
                        <tr><td>Bid Rate</td><td><strong>${{((formatData?.bid_rate || 0) * 100).toFixed(2)}}%</strong></td></tr>
                        <tr><td>Avg Price</td><td><strong>${{formatData?.avg_bid_price.toFixed(4) || '0.0000'}}</strong></td></tr>
                    </table>
                </div>
                <div class="drill-down-section">
                    <h5>Recommendation</h5>
                    ${{formatData?.bid_rate === 0 ?
                        '<p style="color:#dc3545"><strong>Stop listening</strong> to this format. You receive traffic but never bid, wasting QPS and potentially hurting your SSP algo score.</p>' :
                        formatData?.bid_rate < 0.05 ?
                        '<p style="color:#856404"><strong>Review</strong> this format. Very low bid rate may indicate targeting issues or price mismatch.</p>' :
                        '<p style="color:#155724">This format is <strong>performing well</strong>.</p>'
                    }}
                </div>
                <div class="drill-down-section">
                    <h5>SSPs sending this format</h5>
                    <p style="color:#666; font-size:0.85rem;">Top SSPs by volume (all formats):</p>
                    <table class="mini-table">
                        ${{REPORT.ssps.slice(0, 5).map(s => `<tr><td>${{s.ssp}}</td><td>${{s.requests.toLocaleString()}}</td><td>${{(s.bid_rate * 100).toFixed(1)}}%</td></tr>`).join('')}}
                    </table>
                </div>
            `;

            document.getElementById('drillDown').classList.add('active');
        }}

        // Drill down into publisher
        function drillDownPublisher(pubId, ssp) {{
            document.getElementById('drillDownTitle').textContent = `Publisher: ${{pubId}}`;
            const pub = REPORT.publishers.find(p => p.publisher_id === pubId && p.ssp === ssp);

            const content = document.getElementById('drillDownContent');
            content.innerHTML = `
                <div class="drill-down-section">
                    <h5>Publisher Details</h5>
                    <table class="mini-table">
                        <tr><td>Publisher ID</td><td><strong>${{pub?.publisher_id || pubId}}</strong></td></tr>
                        <tr><td>SSP</td><td><strong>${{pub?.ssp || ssp || '-'}}</strong></td></tr>
                        <tr><td>Requests</td><td><strong>${{pub?.requests.toLocaleString() || 0}}</strong></td></tr>
                        <tr><td>Bids</td><td><strong>${{pub?.bids.toLocaleString() || 0}}</strong></td></tr>
                        <tr><td>Bid Rate</td><td><strong>${{((pub?.bid_rate || 0) * 100).toFixed(2)}}%</strong></td></tr>
                    </table>
                </div>
                <div class="drill-down-section">
                    <h5>Recommendation</h5>
                    ${{pub?.bid_rate === 0 ?
                        '<p style="color:#dc3545"><strong>Consider removing</strong> this publisher from your targeting. Zero bids placed despite receiving traffic.</p>' :
                        pub?.bid_rate < 0.05 ?
                        '<p style="color:#856404"><strong>Investigate</strong> why bid rate is low. Check formats, floors, or targeting rules.</p>' :
                        '<p style="color:#155724">This publisher is <strong>performing normally</strong>.</p>'
                    }}
                </div>
            `;

            document.getElementById('drillDown').classList.add('active');
        }}

        function closeDrillDown() {{
            document.getElementById('drillDown').classList.remove('active');
        }}

        // Render publishers table
        function renderPublishers() {{
            const search = document.getElementById('publisherSearch')?.value.toLowerCase() || '';
            const tbody = document.querySelector('#publishersTable tbody');
            tbody.innerHTML = '';

            let filtered = REPORT.publishers.filter(r =>
                search === '' || r.publisher_id.toLowerCase().includes(search) || (r.ssp || '').toLowerCase().includes(search)
            );

            filtered.forEach(r => {{
                const tr = document.createElement('tr');
                tr.className = 'clickable';
                tr.onclick = () => drillDownPublisher(r.publisher_id, r.ssp);
                const rateClass = r.bid_rate === 0 ? 'no-bid' : (r.bid_rate < 0.05 ? 'low-bid-rate' : '');
                tr.innerHTML = `
                    <td><strong>${{r.publisher_id}}</strong></td>
                    <td>${{r.ssp || '-'}}</td>
                    <td>${{r.requests.toLocaleString()}}</td>
                    <td>${{r.bids.toLocaleString()}}</td>
                    <td class="${{rateClass}}">${{(r.bid_rate * 100).toFixed(2)}}%</td>
                    <td>${{r.avg_bid_price.toFixed(4)}}</td>
                    <td>${{getStatusBadge(r.bid_rate, r.requests)}}</td>
                `;
                tbody.appendChild(tr);
            }});
            document.getElementById('publishersCount').textContent = REPORT.publishers.length;
        }}

        // Render segments table
        function renderSegments() {{
            const tbody = document.querySelector('#segmentsTable tbody');
            tbody.innerHTML = '';
            REPORT.segments.forEach(r => {{
                const tr = document.createElement('tr');
                tr.innerHTML = `<td>${{r.segment}}</td><td>${{r.ssp || '-'}}</td><td>${{r.requests.toLocaleString()}}</td><td>${{r.bids.toLocaleString()}}</td><td>${{(r.bid_rate * 100).toFixed(2)}}%</td><td>${{r.avg_bid_price.toFixed(4)}}</td>`;
                tbody.appendChild(tr);
            }});
            document.getElementById('segmentsCount').textContent = REPORT.segments.length;
        }}

        // Render SSPs table
        function renderSsps() {{
            const tbody = document.querySelector('#sspsTable tbody');
            tbody.innerHTML = '';
            REPORT.ssps.forEach(r => {{
                const tr = document.createElement('tr');
                tr.className = 'clickable';
                const rateClass = r.bid_rate === 0 ? 'no-bid' : (r.bid_rate < 0.05 ? 'low-bid-rate' : '');
                tr.innerHTML = `
                    <td><strong>${{r.ssp}}</strong></td>
                    <td>${{r.requests.toLocaleString()}}</td>
                    <td>${{r.bids.toLocaleString()}}</td>
                    <td class="${{rateClass}}">${{(r.bid_rate * 100).toFixed(2)}}%</td>
                    <td>${{r.avg_bid_price.toFixed(4)}}</td>
                    <td>${{getStatusBadge(r.bid_rate, r.requests)}}</td>
                `;
                tbody.appendChild(tr);
            }});
            document.getElementById('sspsCount').textContent = REPORT.ssps.length;
        }}

        // Render problems table
        function renderProblems() {{
            const tbody = document.querySelector('#problemsTable tbody');
            tbody.innerHTML = '';
            REPORT.problems.forEach(r => {{
                const tr = document.createElement('tr');
                tr.className = 'clickable';
                tr.onclick = () => drillDownFormat(r.w, r.h);
                const typeLabel = r.problem_type === 'zero_bids' ? '<span class="badge badge-danger">Zero Bids</span>' :
                                  r.problem_type === 'non_standard' ? '<span class="badge badge-warning">Non-Standard</span>' :
                                  '<span class="badge badge-warning">Low Bid Rate</span>';
                const action = r.problem_type === 'zero_bids' ? 'Stop listening' : 'Review targeting';
                tr.innerHTML = `
                    <td><strong>${{r.w}}x${{r.h}}</strong></td>
                    <td>${{r.requests.toLocaleString()}}</td>
                    <td>${{r.bids.toLocaleString()}}</td>
                    <td class="problem">${{(r.bid_rate * 100).toFixed(2)}}%</td>
                    <td>${{typeLabel}}</td>
                    <td style="color:#4a90a4; cursor:pointer;">${{action}} &rarr;</td>
                `;
                tbody.appendChild(tr);
            }});
            document.getElementById('problemsCount').textContent = REPORT.problems.length;
        }}

        // Column sorting
        document.querySelectorAll('th[data-sort]').forEach(th => {{
            th.addEventListener('click', () => {{
                const col = th.dataset.sort;
                if (currentSort.col === col) {{
                    currentSort.dir = currentSort.dir === 'asc' ? 'desc' : 'asc';
                }} else {{
                    currentSort.col = col;
                    currentSort.dir = 'desc';
                }}
                renderFormats();
                renderPublishers();
                renderSsps();
            }});
        }});

        // Initialize
        document.getElementById('minRequests').addEventListener('input', renderFormats);
        document.getElementById('minBidRate').addEventListener('input', renderFormats);
        document.getElementById('formatSearch').addEventListener('input', renderFormats);
        document.getElementById('publisherSearch')?.addEventListener('input', renderPublishers);

        renderSummary();
        renderFormats();
        renderPublishers();
        renderSegments();
        renderSsps();
        renderProblems();
    </script>
    <footer>
        <p>Generated by <a href="https://rtb.cat" target="_blank">Cat Scan</a> - RTB Analytics Tool</p>
        <p>Created by <a href="https://www.linkedin.com/in/jenbrannstrom/" target="_blank">Jen Brannstrom</a></p>
    </footer>
</body>
</html>"#,
        json_data = json_data,
        source = report.source,
        total_canonical = report.total_canonical_formats,
        total_raw = report.total_raw_formats,
        total_publishers = report.total_publishers,
        min_requests = report.min_requests_filter,
        logo_base64 = include_str!("../../rtbCatLogo-horizontal.svg.b64")
    );

    std::fs::write(path, html)
        .with_context(|| format!("Failed to write HTML report to {}", path))?;

    Ok(())
}

#[tokio::main]
async fn main() -> Result<()> {
    let config = parse_args()?;

    // Use GlobalStats for all aggregation
    let mut global = GlobalStats::new();

    // Read from S3 or local file
    if let Some((bucket, key)) = parse_s3_uri(&config.input_path) {
        let aws_conf = aws_config::defaults(aws_config::BehaviorVersion::latest())
            .load()
            .await;
        let client = S3Client::new(&aws_conf);

        let bytes = download_from_s3(&client, &bucket, &key).await?;
        let reader = BufReader::new(Cursor::new(bytes));
        process_lines_global(reader, &mut global)?;
    } else {
        let file = File::open(&config.input_path)
            .with_context(|| format!("Failed to open log file: {}", config.input_path))?;
        let reader = BufReader::new(file);
        process_lines_global(reader, &mut global)?;
    }

    // Use canonical format stats for main output (reduces 2000+ rows to manageable set)
    // Move into a Vec for filtering & sorting
    let mut rows: Vec<((u32, u32), FormatStats)> = global
        .by_canonical_format
        .iter()
        .map(|(&k, v)| (k, v.clone()))
        .collect();

    // Min-requests filter
    if config.min_requests > 0 {
        rows.retain(|(_, s)| s.requests >= config.min_requests);
    }

    // Sorting
    match config.sort_by {
        SortBy::Format => {
            // already sorted by (w,h) from BTreeMap
        }
        SortBy::RequestsDesc => {
            rows.sort_by(|a, b| {
                b.1.requests
                    .cmp(&a.1.requests)
                    .then_with(|| a.0.cmp(&b.0))
            });
        }
        SortBy::BidRateDesc => {
            rows.sort_by(|a, b| {
                let ar = bid_rate(&a.1);
                let br = bid_rate(&b.1);

                br.partial_cmp(&ar)
                    .unwrap_or(Ordering::Equal)
                    .then_with(|| a.0.cmp(&b.0))
            });
        }
    }

    // Build summaries for both CSV and HTML
    let summaries: Vec<FormatSummary> = rows
        .iter()
        .map(|((w, h), stat)| FormatSummary {
            w: *w,
            h: *h,
            requests: stat.requests,
            bids: stat.bids,
            bid_rate: bid_rate(stat),
            avg_bid_price: avg_bid_price(stat),
        })
        .collect();

    // Output handling: --out directory or stdout
    if let Some(out_dir) = &config.out_dir {
        // Create output directory if it doesn't exist
        std::fs::create_dir_all(out_dir)
            .with_context(|| format!("Failed to create output directory: {}", out_dir))?;

        // Write format_stats.csv
        let format_csv_path = format!("{}/format_stats.csv", out_dir);
        let mut format_csv = std::fs::File::create(&format_csv_path)
            .with_context(|| format!("Failed to create {}", format_csv_path))?;
        use std::io::Write;
        writeln!(format_csv, "w,h,requests,bids,bid_rate,avg_bid_price")?;
        for s in &summaries {
            writeln!(
                format_csv,
                "{},{},{},{},{:.4},{:.4}",
                s.w, s.h, s.requests, s.bids, s.bid_rate, s.avg_bid_price
            )?;
        }
        eprintln!("Format stats written to: {}", format_csv_path);

        // Write segment_stats.csv (publisher + segment data)
        let segment_csv_path = format!("{}/segment_stats.csv", out_dir);
        let mut segment_csv = std::fs::File::create(&segment_csv_path)
            .with_context(|| format!("Failed to create {}", segment_csv_path))?;

        // Publisher section
        writeln!(segment_csv, "# Publishers")?;
        writeln!(segment_csv, "type,id,ssp,requests,bids,bid_rate,avg_bid_price")?;
        let mut pub_vec: Vec<_> = global.by_publisher.iter().collect();
        pub_vec.sort_by(|a, b| b.1.requests.cmp(&a.1.requests));
        for (key, stats) in &pub_vec {
            writeln!(
                segment_csv,
                "publisher,{},{},{},{},{:.4},{:.4}",
                key.publisher_id,
                key.ssp,
                stats.requests,
                stats.bids,
                bid_rate(stats),
                avg_bid_price(stats)
            )?;
        }

        // Segment section
        writeln!(segment_csv, "\n# Segments")?;
        let mut seg_vec: Vec<_> = global.by_segment.iter().collect();
        seg_vec.sort_by(|a, b| b.1.requests.cmp(&a.1.requests));
        for (key, stats) in &seg_vec {
            writeln!(
                segment_csv,
                "segment,{},{},{},{},{:.4},{:.4}",
                key.segment,
                key.ssp,
                stats.requests,
                stats.bids,
                bid_rate(stats),
                avg_bid_price(stats)
            )?;
        }
        eprintln!("Segment stats written to: {}", segment_csv_path);

        // Write HTML report to out_dir
        let html_path = format!("{}/report.html", out_dir);

        // Build full report data
        let total_requests: u64 = global.by_raw_format.values().map(|s| s.requests).sum();

        // Build publisher summaries
        let mut publishers: Vec<PublisherSummary> = global
            .by_publisher
            .iter()
            .map(|(key, stats)| PublisherSummary {
                ssp: key.ssp.clone(),
                publisher_id: key.publisher_id.clone(),
                requests: stats.requests,
                bids: stats.bids,
                bid_rate: bid_rate(stats),
                avg_bid_price: avg_bid_price(stats),
            })
            .collect();
        publishers.sort_by(|a, b| b.requests.cmp(&a.requests));

        // Build segment summaries
        let mut segments: Vec<SegmentSummary> = global
            .by_segment
            .iter()
            .map(|(key, stats)| SegmentSummary {
                ssp: key.ssp.clone(),
                segment: key.segment.clone(),
                requests: stats.requests,
                bids: stats.bids,
                bid_rate: bid_rate(stats),
                avg_bid_price: avg_bid_price(stats),
            })
            .collect();
        segments.sort_by(|a, b| b.requests.cmp(&a.requests));

        // Build SSP summaries
        let mut ssps: Vec<SspSummary> = global
            .by_ssp
            .iter()
            .map(|(ssp, stats)| SspSummary {
                ssp: ssp.clone(),
                requests: stats.requests,
                bids: stats.bids,
                bid_rate: bid_rate(stats),
                avg_bid_price: avg_bid_price(stats),
            })
            .collect();
        ssps.sort_by(|a, b| b.requests.cmp(&a.requests));

        // Get problem formats
        let problems = find_problem_formats(&global, config.min_requests.max(10));

        let report = HtmlReportData {
            source: config.input_path.clone(),
            total_requests,
            total_publishers: global.by_publisher.len() as u64,
            total_raw_formats: global.by_raw_format.len() as u64,
            total_canonical_formats: global.by_canonical_format.len() as u64,
            min_requests_filter: config.min_requests,
            formats: summaries.clone(),
            publishers,
            segments,
            ssps,
            problems,
        };

        write_html_report_full(&html_path, &report)?;
        eprintln!("HTML report written to: {}", html_path);
    } else {
        // Print CSV to stdout (default behavior)
        println!("w,h,requests,bids,bid_rate,avg_bid_price");
        for s in &summaries {
            println!(
                "{},{},{},{},{:.4},{:.4}",
                s.w, s.h, s.requests, s.bids, s.bid_rate, s.avg_bid_price
            );
        }
    }

    // Generate HTML report if requested via --html-out (legacy, deprecated)
    if let Some(html_path) = &config.html_out {
        // Build full report data
        let total_requests: u64 = global.by_raw_format.values().map(|s| s.requests).sum();

        // Build publisher summaries
        let mut publishers: Vec<PublisherSummary> = global
            .by_publisher
            .iter()
            .map(|(key, stats)| PublisherSummary {
                ssp: key.ssp.clone(),
                publisher_id: key.publisher_id.clone(),
                requests: stats.requests,
                bids: stats.bids,
                bid_rate: bid_rate(stats),
                avg_bid_price: avg_bid_price(stats),
            })
            .collect();
        publishers.sort_by(|a, b| b.requests.cmp(&a.requests));

        // Build segment summaries
        let mut segments: Vec<SegmentSummary> = global
            .by_segment
            .iter()
            .map(|(key, stats)| SegmentSummary {
                ssp: key.ssp.clone(),
                segment: key.segment.clone(),
                requests: stats.requests,
                bids: stats.bids,
                bid_rate: bid_rate(stats),
                avg_bid_price: avg_bid_price(stats),
            })
            .collect();
        segments.sort_by(|a, b| b.requests.cmp(&a.requests));

        // Build SSP summaries
        let mut ssps: Vec<SspSummary> = global
            .by_ssp
            .iter()
            .map(|(ssp, stats)| SspSummary {
                ssp: ssp.clone(),
                requests: stats.requests,
                bids: stats.bids,
                bid_rate: bid_rate(stats),
                avg_bid_price: avg_bid_price(stats),
            })
            .collect();
        ssps.sort_by(|a, b| b.requests.cmp(&a.requests));

        // Get problem formats
        let problems = find_problem_formats(&global, config.min_requests.max(10));

        let report = HtmlReportData {
            source: config.input_path.clone(),
            total_requests,
            total_publishers: global.by_publisher.len() as u64,
            total_raw_formats: global.by_raw_format.len() as u64,
            total_canonical_formats: global.by_canonical_format.len() as u64,
            min_requests_filter: config.min_requests,
            formats: summaries.clone(),
            publishers,
            segments,
            ssps,
            problems,
        };

        write_html_report_full(html_path, &report)?;
        eprintln!("HTML report written to: {}", html_path);
    }

    // Time-based analysis
    if config.time_analysis && !global.time_stats.is_empty() {
        eprintln!("\n=== Time-based Analysis ===");
        eprintln!("minute_bucket,requests,bids,bid_rate,avg_bid_price");

        for (bucket, stats) in &global.time_stats {
            let rate = if stats.requests == 0 {
                0.0
            } else {
                stats.bids as f64 / stats.requests as f64
            };
            let avg_price = if stats.bids == 0 {
                0.0
            } else {
                stats.sum_bid_price / stats.bids as f64
            };
            eprintln!(
                "{},{},{},{:.4},{:.4}",
                bucket, stats.requests, stats.bids, rate, avg_price
            );
        }

        // Summary stats
        let total_reqs: u64 = global.time_stats.values().map(|s| s.requests).sum();
        let total_bids: u64 = global.time_stats.values().map(|s| s.bids).sum();
        let overall_rate = if total_reqs == 0 {
            0.0
        } else {
            total_bids as f64 / total_reqs as f64
        };

        // Time range
        let min_ts = global.time_stats.values().map(|s| s.min_ts).min().unwrap_or(0);
        let max_ts = global.time_stats.values().map(|s| s.max_ts).max().unwrap_or(0);
        let duration_ms = max_ts.saturating_sub(min_ts);
        let duration_sec = duration_ms as f64 / 1000.0;

        eprintln!(
            "\nTime range: {}ms ({:.2}s), {} buckets, overall bid rate: {:.2}%",
            duration_ms,
            duration_sec,
            global.time_stats.len(),
            overall_rate * 100.0
        );
    }

    // Segment-based analysis
    if config.segment_stats {
        // Publisher stats
        if !global.by_publisher.is_empty() {
            eprintln!("\n=== Publisher Stats ===");
            eprintln!("publisher,requests,bids,bid_rate,avg_bid_price");

            let mut pub_vec: Vec<_> = global.by_publisher.iter().collect();
            pub_vec.sort_by(|a, b| b.1.requests.cmp(&a.1.requests));

            for (key, stats) in pub_vec {
                let rate = if stats.requests == 0 {
                    0.0
                } else {
                    stats.bids as f64 / stats.requests as f64
                };
                let avg_price = if stats.bids == 0 {
                    0.0
                } else {
                    stats.sum_bid_price / stats.bids as f64
                };
                eprintln!(
                    "{},{},{},{:.4},{:.4}",
                    key.publisher_id, stats.requests, stats.bids, rate, avg_price
                );
            }
        }

        // Segment stats
        if !global.by_segment.is_empty() {
            eprintln!("\n=== Segment Stats ===");
            eprintln!("segment,requests,bids,bid_rate,avg_bid_price");

            let mut seg_vec: Vec<_> = global.by_segment.iter().collect();
            seg_vec.sort_by(|a, b| b.1.requests.cmp(&a.1.requests));

            for (key, stats) in seg_vec {
                let rate = if stats.requests == 0 {
                    0.0
                } else {
                    stats.bids as f64 / stats.requests as f64
                };
                let avg_price = if stats.bids == 0 {
                    0.0
                } else {
                    stats.sum_bid_price / stats.bids as f64
                };
                eprintln!(
                    "{},{},{},{:.4},{:.4}",
                    key.segment, stats.requests, stats.bids, rate, avg_price
                );
            }
        }

        // SSP stats
        if !global.by_ssp.is_empty() {
            eprintln!("\n=== SSP Stats ===");
            eprintln!("ssp,requests,bids,bid_rate,avg_bid_price");

            let mut ssp_vec: Vec<_> = global.by_ssp.iter().collect();
            ssp_vec.sort_by(|a, b| b.1.requests.cmp(&a.1.requests));

            for (ssp, stats) in ssp_vec {
                let rate = if stats.requests == 0 {
                    0.0
                } else {
                    stats.bids as f64 / stats.requests as f64
                };
                let avg_price = if stats.bids == 0 {
                    0.0
                } else {
                    stats.sum_bid_price / stats.bids as f64
                };
                eprintln!(
                    "{},{},{},{:.4},{:.4}",
                    ssp, stats.requests, stats.bids, rate, avg_price
                );
            }
        }

        // Problem formats
        let problems = find_problem_formats(&global, config.min_requests.max(10));
        if !problems.is_empty() {
            eprintln!("\n=== Problem Formats ===");
            eprintln!("w,h,requests,bids,bid_rate,problem_type");

            for p in &problems {
                eprintln!(
                    "{},{},{},{},{:.4},{}",
                    p.w, p.h, p.requests, p.bids, p.bid_rate, p.problem_type
                );
            }
        }
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Test helper: process a single log record and update the stats map
    fn process_record(record: &LogRecord, stats: &mut BTreeMap<(u32, u32), FormatStats>) {
        let w = record.request["imp"][0]["banner"]["w"]
            .as_u64()
            .unwrap_or(0) as u32;
        let h = record.request["imp"][0]["banner"]["h"]
            .as_u64()
            .unwrap_or(0) as u32;

        if w == 0 || h == 0 {
            return;
        }

        let entry = stats.entry((w, h)).or_default();
        entry.requests += 1;

        if let Some(seatbids) = record
            .response
            .get("seatbid")
            .and_then(|v| v.as_array())
        {
            if !seatbids.is_empty() {
                entry.bids += 1;

                if let Some(price) = seatbids
                    .get(0)
                    .and_then(|sb| sb.get("bid"))
                    .and_then(|bids| bids.as_array())
                    .and_then(|bids_arr| bids_arr.get(0))
                    .and_then(|b| b.get("price"))
                    .and_then(|p| p.as_f64())
                {
                    entry.sum_bid_price += price;
                }
            }
        }
    }

    fn make_record(w: u32, h: u32, with_bid: bool, price: f64) -> LogRecord {
        let request = serde_json::json!({
            "imp": [{
                "banner": {
                    "w": w,
                    "h": h
                }
            }]
        });

        let response = if with_bid {
            serde_json::json!({
                "seatbid": [{
                    "bid": [{
                        "price": price
                    }]
                }]
            })
        } else {
            serde_json::json!({
                "seatbid": []
            })
        };

        LogRecord {
            request,
            response,
            ts_ms: None,
        }
    }

    #[test]
    fn test_single_bid() {
        let mut stats = BTreeMap::new();
        let record = make_record(300, 250, true, 0.5);

        process_record(&record, &mut stats);

        assert_eq!(stats.len(), 1);
        let s = stats.get(&(300, 250)).unwrap();
        assert_eq!(
            *s,
            FormatStats {
                requests: 1,
                bids: 1,
                sum_bid_price: 0.5
            }
        );
        assert!((bid_rate(s) - 1.0).abs() < 1e-9);
        assert!((avg_bid_price(s) - 0.5).abs() < 1e-9);
    }

    #[test]
    fn test_single_no_bid() {
        let mut stats = BTreeMap::new();
        let record = make_record(320, 50, false, 0.0);

        process_record(&record, &mut stats);

        assert_eq!(stats.len(), 1);
        let s = stats.get(&(320, 50)).unwrap();
        assert_eq!(
            *s,
            FormatStats {
                requests: 1,
                bids: 0,
                sum_bid_price: 0.0
            }
        );
        assert!((bid_rate(s) - 0.0).abs() < 1e-9);
        assert!((avg_bid_price(s) - 0.0).abs() < 1e-9);
    }

    #[test]
    fn test_multiple_formats() {
        let mut stats = BTreeMap::new();

        // 3 requests for 300x250, 2 bids with prices 0.5 and 1.0
        process_record(&make_record(300, 250, true, 0.5), &mut stats);
        process_record(&make_record(300, 250, true, 1.0), &mut stats);
        process_record(&make_record(300, 250, false, 0.0), &mut stats);

        // 1 request for 160x600, no bid
        process_record(&make_record(160, 600, false, 0.0), &mut stats);

        let s_300 = stats.get(&(300, 250)).unwrap();
        assert_eq!(
            *s_300,
            FormatStats {
                requests: 3,
                bids: 2,
                sum_bid_price: 1.5
            }
        );
        assert!((bid_rate(s_300) - (2.0 / 3.0)).abs() < 1e-9);
        assert!((avg_bid_price(s_300) - 0.75).abs() < 1e-9);

        let s_160 = stats.get(&(160, 600)).unwrap();
        assert_eq!(
            *s_160,
            FormatStats {
                requests: 1,
                bids: 0,
                sum_bid_price: 0.0
            }
        );
    }

    #[test]
    fn test_malformed_record_skipped() {
        let mut stats: BTreeMap<(u32, u32), FormatStats> = BTreeMap::new();

        // Record with w=0 should be skipped entirely
        let bad_record = LogRecord {
            request: serde_json::json!({
                "imp": [{
                    "banner": {"w": 0, "h": 250}
                }]
            }),
            response: serde_json::json!({}),
            ts_ms: None,
        };

        process_record(&bad_record, &mut stats);

        assert_eq!(stats.len(), 0);
    }

    #[test]
    fn test_canonical_size_bucketing() {
        // Test that slightly off sizes map to canonical
        assert_eq!(canonical_size(298, 250), (300, 250));
        assert_eq!(canonical_size(301, 246), (300, 250));
        assert_eq!(canonical_size(300, 250), (300, 250));

        // Test other standard sizes
        assert_eq!(canonical_size(320, 50), (320, 50));
        assert_eq!(canonical_size(728, 90), (728, 90));
        assert_eq!(canonical_size(160, 600), (160, 600));

        // Non-standard sizes should return as-is
        assert_eq!(canonical_size(123, 456), (123, 456));
        assert_eq!(canonical_size(999, 888), (999, 888));
    }

    #[test]
    fn test_is_standard_size() {
        assert!(is_standard_size(300, 250));
        assert!(is_standard_size(320, 50));
        assert!(is_standard_size(728, 90));

        // Slightly off sizes that map to canonical should be standard
        assert!(is_standard_size(298, 250));

        // Non-standard sizes
        assert!(!is_standard_size(123, 456));
        assert!(!is_standard_size(999, 888));
    }

    #[test]
    fn test_global_stats_canonical_aggregation() {
        let mut global = GlobalStats::new();

        // Create records with slightly different sizes that should bucket together
        let record1 = make_record(298, 250, true, 0.5); // Should map to 300x250
        let record2 = make_record(301, 246, true, 1.0); // Should map to 300x250
        let record3 = make_record(300, 250, false, 0.0); // Exact 300x250

        process_record_global(&record1, &mut global);
        process_record_global(&record2, &mut global);
        process_record_global(&record3, &mut global);

        // Raw format stats should have 3 different sizes
        assert_eq!(global.by_raw_format.len(), 3);

        // Canonical format stats should have 1 bucket
        assert_eq!(global.by_canonical_format.len(), 1);

        let canonical_stats = global.by_canonical_format.get(&(300, 250)).unwrap();
        assert_eq!(canonical_stats.requests, 3);
        assert_eq!(canonical_stats.bids, 2);
    }

    #[test]
    fn test_problem_format_detection() {
        let mut global = GlobalStats::new();

        // Add a non-standard size with volume
        for _ in 0..20 {
            let record = make_record(123, 456, true, 0.5);
            process_record_global(&record, &mut global);
        }

        // Add a zero-bid format with volume
        for _ in 0..15 {
            let record = make_record(300, 250, false, 0.0);
            process_record_global(&record, &mut global);
        }

        let problems = find_problem_formats(&global, 10);

        // Should find both problems
        assert_eq!(problems.len(), 2);

        // Check non-standard problem
        let non_std = problems.iter().find(|p| p.w == 123).unwrap();
        assert_eq!(non_std.problem_type, "non_standard");
        assert_eq!(non_std.requests, 20);

        // Check zero-bid problem
        let zero_bid = problems.iter().find(|p| p.w == 300).unwrap();
        assert_eq!(zero_bid.problem_type, "zero_bids");
        assert_eq!(zero_bid.requests, 15);
    }
}
