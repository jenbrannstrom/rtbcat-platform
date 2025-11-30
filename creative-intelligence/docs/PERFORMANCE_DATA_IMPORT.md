# Performance Data Import Guide

RTBcat Creative Intelligence supports importing performance metrics (impressions, clicks, spend) from external sources via CSV file or JSON API.

## CSV Format

### Required Columns

| Column | Type | Description |
|--------|------|-------------|
| `creative_id` | String | Creative ID (must exist in database) |
| `date` | Date | Date in YYYY-MM-DD format |
| `impressions` | Integer | Number of impressions (>= 0) |
| `clicks` | Integer | Number of clicks (>= 0 and <= impressions) |
| `spend` | Decimal | Spend in USD (>= 0), e.g., `125.50` |

### Optional Columns

| Column | Type | Description |
|--------|------|-------------|
| `geography` | String | ISO 3166-1 alpha-2 country code (e.g., `US`, `BR`, `IE`) |
| `device_type` | String | `MOBILE`, `DESKTOP`, `TABLET`, `CTV`, or `UNKNOWN` |
| `hour` | Integer | Hour 0-23 for hourly granularity data |
| `placement` | String | Site/app placement identifier |
| `campaign_id` | String | Campaign ID for grouping |

### Example CSV

```csv
creative_id,date,impressions,clicks,spend,geography,device_type
79783,2025-11-29,10000,250,125.50,BR,MOBILE
79783,2025-11-29,5000,100,80.00,BR,DESKTOP
79783,2025-11-28,12000,300,150.00,BR,MOBILE
144634,2025-11-29,50000,800,200.00,US,MOBILE
144634,2025-11-29,30000,450,135.00,US,DESKTOP
```

## Import Methods

### 1. CSV File Upload (Recommended for Bulk Data)

```bash
curl -X POST http://localhost:8000/performance/import-csv \
  -F "file=@performance_data.csv"
```

Response:
```json
{
  "status": "completed",
  "imported": 5,
  "skipped": 0,
  "errors": []
}
```

### 2. JSON API (Recommended for Integrations)

```bash
curl -X POST http://localhost:8000/performance/import \
  -H "Content-Type: application/json" \
  -d '{
    "metrics": [
      {
        "creative_id": "79783",
        "metric_date": "2025-11-29",
        "impressions": 10000,
        "clicks": 250,
        "spend_micros": 125500000,
        "geography": "BR",
        "device_type": "MOBILE"
      }
    ]
  }'
```

**Note:** JSON API uses `spend_micros` (1,000,000 = $1.00), while CSV uses USD decimal.

## Querying Performance Data

### Get Creative Performance Summary

```bash
curl "http://localhost:8000/performance/creative/79783?days=30"
```

Response:
```json
{
  "total_impressions": 27000,
  "total_clicks": 550,
  "total_spend_micros": 355500000,
  "avg_cpm_micros": 13166,
  "avg_cpc_micros": 646363,
  "ctr_percent": 2.04,
  "days_with_data": 2,
  "earliest_date": "2025-11-28",
  "latest_date": "2025-11-29"
}
```

### List Performance Metrics with Filters

```bash
# All metrics for a creative
curl "http://localhost:8000/performance/metrics?creative_id=79783"

# Filter by date range
curl "http://localhost:8000/performance/metrics?start_date=2025-11-28&end_date=2025-11-29"

# Filter by geography
curl "http://localhost:8000/performance/metrics?geography=US"

# Filter by device type
curl "http://localhost:8000/performance/metrics?device_type=MOBILE"
```

## Data Sources

### From Your Bidder
Export spend/click/impression data from your bidder's reporting system and convert to CSV format.

### From Google Authorized Buyers
Limited performance data available via Authorized Buyers API (partial impressions only).

### From BigQuery (Enterprise)
Set up scheduled export from your data warehouse:

```sql
SELECT
  creative_id,
  DATE(timestamp) as date,
  SUM(impressions) as impressions,
  SUM(clicks) as clicks,
  SUM(spend) as spend,
  geo_country as geography,
  device_category as device_type
FROM `your_project.rtb_data.bid_responses`
WHERE timestamp >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
GROUP BY creative_id, DATE(timestamp), geo_country, device_category
```

## Validation Rules

The system validates all imported data:

| Rule | Description |
|------|-------------|
| ✓ `creative_id` exists | Creative must be in database |
| ✓ Date not future | Dates cannot be in the future |
| ✓ `clicks <= impressions` | Clicks cannot exceed impressions |
| ✓ Non-negative values | `spend`, `clicks`, `impressions` >= 0 |
| ✓ Valid geography | Must be 2-letter ISO code |
| ✓ Valid device_type | Must be MOBILE, DESKTOP, TABLET, CTV, or UNKNOWN |
| ✓ Valid hour | If provided, must be 0-23 |

Validation errors are reported in the import response.

## Duplicate Handling

If you import the same data twice (same `creative_id`, `date`, `geography`, `device_type`, `placement`):
- Existing record is **UPDATED** with new values
- No duplicate records created
- This enables safe re-imports and incremental updates

## Internal Data Format

Performance data is stored internally using **micros** for currency:
- 1,000,000 micros = $1.00 USD
- This avoids floating-point precision issues
- Matches Google Ads API conventions

The CSV import automatically converts USD decimals to micros.

## Performance Tips

- **Batch imports**: CSV import handles batching automatically
- **Initial load**: For large datasets (100k+ rows), import may take 1-2 minutes
- **Indexes**: Database indexes are created for fast queries
- **Retention**: Use `/performance/cleanup` endpoint to remove old data

## Cleanup / Retention

Delete old performance data to manage database size:

```bash
# Keep only last 90 days (default)
curl -X DELETE "http://localhost:8000/performance/cleanup"

# Keep last 30 days
curl -X DELETE "http://localhost:8000/performance/cleanup?days_to_keep=30"
```

## Campaign Cache Refresh

After importing performance data, refresh campaign aggregates:

```bash
curl -X POST "http://localhost:8000/performance/campaign/{campaign_id}/refresh-cache"
```

This updates cached values like `spend_7d`, `spend_30d`, `avg_cpm`, etc. for faster dashboard queries.

## Troubleshooting

### "CSV missing required columns"
Ensure your CSV has headers: `creative_id,date,impressions,clicks,spend`

### "Invalid date format"
Use YYYY-MM-DD format (e.g., `2025-11-29`)

### "Clicks cannot exceed impressions"
Check your data export - clicks should always be <= impressions

### "Invalid geography code"
Use 2-letter ISO 3166-1 codes (e.g., `US`, `BR`, `IE`)

### "creative_id not found"
Ensure the creative exists in the database. Run a creative sync first.

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/performance/import-csv` | POST | Import CSV file |
| `/performance/import` | POST | Import JSON metrics |
| `/performance/creative/{id}` | GET | Get creative summary |
| `/performance/metrics` | GET | List metrics with filters |
| `/performance/campaign/{id}/refresh-cache` | POST | Refresh campaign cache |
| `/performance/cleanup` | DELETE | Remove old data |
