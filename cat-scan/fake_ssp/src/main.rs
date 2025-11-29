use std::{
    env,
    fs::OpenOptions,
    io::Write,
    time::{SystemTime, UNIX_EPOCH},
};

use anyhow::{Context, Result};
use aws_sdk_s3::Client as S3Client;
use reqwest::Client;
use serde_json::{json, Value};
use tokio::time::{sleep, Duration};

enum LogDestination {
    LocalFile(std::fs::File),
    S3 {
        client: S3Client,
        bucket: String,
        prefix: String,
        buffer: Vec<String>,
    },
}

impl LogDestination {
    async fn new_from_env() -> Result<Self> {
        let destination_type = env::var("LOG_DESTINATION").unwrap_or_else(|_| "local".to_string());

        match destination_type.as_str() {
            "s3" => {
                let bucket = env::var("S3_BUCKET")
                    .context("S3_BUCKET environment variable required when LOG_DESTINATION=s3")?;
                let prefix = env::var("S3_PREFIX").unwrap_or_default();

                println!("Initializing S3 client...");
                let config = aws_config::defaults(aws_config::BehaviorVersion::latest())
                    .load()
                    .await;
                let client = S3Client::new(&config);

                println!("  S3 bucket: {}", bucket);
                println!("  S3 prefix: {}", prefix);

                Ok(LogDestination::S3 {
                    client,
                    bucket,
                    prefix,
                    buffer: Vec::new(),
                })
            }
            "local" | _ => {
                let log_file_path =
                    env::var("LOG_FILE").unwrap_or_else(|_| "fake_ssp_logs.jsonl".to_string());

                println!("Using local file logging");
                println!("  Log file: {}", log_file_path);

                let file = OpenOptions::new()
                    .create(true)
                    .append(true)
                    .open(&log_file_path)
                    .with_context(|| format!("Failed to open log file: {}", log_file_path))?;

                Ok(LogDestination::LocalFile(file))
            }
        }
    }

    async fn write_log(&mut self, log_line: String) -> Result<()> {
        match self {
            LogDestination::LocalFile(file) => {
                writeln!(file, "{}", log_line)?;
                Ok(())
            }
            LogDestination::S3 { buffer, .. } => {
                buffer.push(log_line);

                // Flush buffer every 50 lines or when buffer gets too large
                if buffer.len() >= 50 {
                    self.flush().await?;
                }
                Ok(())
            }
        }
    }

    async fn flush(&mut self) -> Result<()> {
        match self {
            LogDestination::LocalFile(file) => {
                file.flush()?;
                Ok(())
            }
            LogDestination::S3 {
                client,
                bucket,
                prefix,
                buffer,
            } => {
                if buffer.is_empty() {
                    return Ok(());
                }

                let timestamp = SystemTime::now()
                    .duration_since(UNIX_EPOCH)?
                    .as_millis();

                let key = if prefix.is_empty() {
                    format!("fake_ssp_logs_{}.jsonl", timestamp)
                } else {
                    format!("{}/fake_ssp_logs_{}.jsonl", prefix.trim_end_matches('/'), timestamp)
                };

                let content = buffer.join("\n") + "\n";

                println!("Flushing {} log lines to s3://{}/{}", buffer.len(), bucket, key);

                client
                    .put_object()
                    .bucket(bucket.as_str())
                    .key(&key)
                    .body(content.into_bytes().into())
                    .content_type("application/x-ndjson")
                    .send()
                    .await
                    .with_context(|| format!("Failed to write to S3: s3://{}/{}", bucket, key))?;

                buffer.clear();
                Ok(())
            }
        }
    }
}

/// Simple fake SSP / publisher:
/// - Cycles through a few banner sizes.
/// - Sends OpenRTB-ish requests to fake_bidder.
/// - Logs request + response to JSONL file or S3.
///
/// Environment variables:
/// - BIDDER_ENDPOINT: URL of bidder (default: http://127.0.0.1:3000/bid)
/// - LOG_DESTINATION: "local" or "s3" (default: local)
/// - LOG_FILE: Path to log file when using local (default: fake_ssp_logs.jsonl)
/// - S3_BUCKET: S3 bucket name when using s3 destination (required for s3)
/// - S3_PREFIX: S3 prefix for log files when using s3 destination (optional)
#[tokio::main]
async fn main() -> Result<()> {
    // Configuration from environment
    let bidder_endpoint =
        env::var("BIDDER_ENDPOINT").unwrap_or_else(|_| "http://127.0.0.1:3000/bid".to_string());

    println!("fake_ssp starting...");
    println!("  Bidder endpoint: {}", bidder_endpoint);

    // Initialize log destination
    let mut log_dest = LogDestination::new_from_env().await?;

    // HTTP client
    let client = Client::new();

    // A few example formats to cycle through
    let formats: &[(u32, u32)] = &[(300, 250), (320, 50), (160, 600), (728, 90)];

    // Publishers and segments for realistic testing
    let publishers: &[(&str, &str)] = &[
        ("pub-news", "news.example.com"),
        ("pub-sports", "sports.example.com"),
        ("pub-tech", "tech.example.com"),
    ];

    let segments: &[&str] = &["automotive", "travel", "finance", "entertainment"];

    let mut format_idx = 0usize;
    let mut pub_idx = 0usize;
    let mut seg_idx = 0usize;

    // Send a bunch of requests then exit
    // (You can bump this number or later change to a "loop { ... }")
    let num_requests = 200;
    println!("Generating {} bid requests...", num_requests);

    for i in 0..num_requests {
        let (w, h) = formats[format_idx];
        format_idx = (format_idx + 1) % formats.len();

        let (pub_id, pub_domain) = publishers[pub_idx];
        pub_idx = (pub_idx + 1) % publishers.len();

        let segment = segments[seg_idx];
        seg_idx = (seg_idx + 1) % segments.len();

        // Minimal OpenRTB-like request with publisher and segment info
        let request = json!({
            "id": format!("req-{}x{}-{}", w, h, i),
            "source": {
                "ssp": "fake_ssp"
            },
            "site": {
                "publisher": {
                    "id": pub_id
                },
                "domain": pub_domain
            },
            "user": {
                "data": [{
                    "segment": [{
                        "id": segment
                    }]
                }]
            },
            "imp": [{
                "id": "1",
                "banner": {
                    "w": w,
                    "h": h
                }
            }]
        });

        // Current timestamp in ms
        let ts_ms = SystemTime::now().duration_since(UNIX_EPOCH)?.as_millis() as u64;

        // Call fake_bidder
        let response: Value = match client
            .post(&bidder_endpoint)
            .json(&request)
            .send()
            .await
        {
            Ok(resp) => match resp.json::<Value>().await {
                Ok(json) => json,
                Err(_) => json!({}), // bad JSON -> treat as empty response
            },
            Err(_) => json!({}), // network error -> empty response
        };

        // Single log record
        let log_line = json!({
            "ts_ms": ts_ms,
            "request": request,
            "response": response,
        });

        // Write log line
        log_dest
            .write_log(log_line.to_string())
            .await
            .context("Failed to write log line")?;

        // Progress indicator every 50 requests
        if (i + 1) % 50 == 0 {
            println!("  Generated {} requests...", i + 1);
        }

        // Small pause so we don't hammer localhost
        sleep(Duration::from_millis(100)).await;
    }

    // Final flush to ensure all logs are written
    println!("Flushing remaining logs...");
    log_dest.flush().await?;

    println!("Done! Generated {} requests.", num_requests);

    Ok(())
}
