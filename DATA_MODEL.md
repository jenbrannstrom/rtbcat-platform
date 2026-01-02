# RTBcat Platform - Data Model Documentation

This document describes the database schema for the RTBcat platform, a real-time bidding (RTB) analytics and creative management system using SQLite.

## Recent Changes

| CSV Report Type         | Target Table      |
|-------------------------|-------------------|
| Funnel (geo/publishers) | rtb_funnel        |
| Bids in Auction         | rtb_daily         |
| Bid Filtering           | rtb_bid_filtering |

---

## Table of Contents

1. [Creative Management](#creative-management)
2. [Campaign Management](#campaign-management)
3. [Service Accounts & Buyer Seats](#service-accounts--buyer-seats)
4. [RTB Performance & Analytics](#rtb-performance--analytics)
5. [Pretargeting Configuration](#pretargeting-configuration)
6. [Import & Upload Tracking](#import--upload-tracking)
7. [User Authentication & Security](#user-authentication--security)
8. [Lookup & Reference Tables](#lookup--reference-tables)

---

## Creative Management

### creatives

Stores creative assets synced from Google Authorized Buyers.

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Primary key, creative ID from Google |
| name | TEXT | Creative name |
| format | TEXT | Format type (HTML, IMAGE, VIDEO, NATIVE) |
| account_id | TEXT | Google account ID |
| buyer_id | TEXT | Buyer/seat ID |
| approval_status | TEXT | Approval status from Google |
| width | INTEGER | Width in pixels |
| height | INTEGER | Height in pixels |
| canonical_size | TEXT | Normalized size (e.g., "300x250") |
| size_category | TEXT | Size category (e.g., "medium_rectangle") |
| final_url | TEXT | Landing page URL |
| display_url | TEXT | Display URL shown in ad |
| utm_source | TEXT | UTM source parameter |
| utm_medium | TEXT | UTM medium parameter |
| utm_campaign | TEXT | UTM campaign parameter |
| utm_content | TEXT | UTM content parameter |
| utm_term | TEXT | UTM term parameter |
| advertiser_name | TEXT | Advertiser name |
| campaign_id | TEXT | FK to campaigns |
| cluster_id | TEXT | FK to clusters |
| raw_data | TEXT | Raw JSON from API |
| first_seen_at | TIMESTAMP | When first imported |
| first_import_batch_id | TEXT | First import batch ID |
| created_at | TIMESTAMP | Record creation time |
| updated_at | TIMESTAMP | Last update time |

### clusters

Groups creatives by visual/thematic similarity using AI clustering.

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Primary key |
| name | TEXT | Cluster name |
| description | TEXT | Cluster description |
| creative_count | INTEGER | Number of creatives |
| centroid | TEXT | Cluster centroid (embedding) |
| created_at | TIMESTAMP | Creation time |

### thumbnail_status

Tracks thumbnail generation status for creatives.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| creative_id | TEXT | FK to creatives (unique) |
| status | TEXT | Generation status |
| thumbnail_url | TEXT | Generated thumbnail URL |
| video_url | TEXT | Video URL if applicable |
| error_reason | TEXT | Error message if failed |
| attempted_at | TIMESTAMP | Last attempt time |
| created_at | TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | Last update time |

---

## Campaign Management

### campaigns

Google Ads campaigns linked to creatives.

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Primary key |
| name | TEXT | Campaign name |
| source | TEXT | Source (default: 'google_ads') |
| creative_count | INTEGER | Number of creatives |
| metadata | TEXT | Additional metadata (JSON) |
| spend_7d_micros | INTEGER | 7-day spend in micros |
| spend_30d_micros | INTEGER | 30-day spend in micros |
| total_impressions | INTEGER | Total impressions |
| total_clicks | INTEGER | Total clicks |
| avg_cpm_micros | INTEGER | Average CPM in micros |
| avg_cpc_micros | INTEGER | Average CPC in micros |
| perf_updated_at | TIMESTAMP | Performance data updated |
| created_at | TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | Last update time |

### ai_campaigns

AI-generated campaign groupings.

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Primary key |
| seat_id | INTEGER | FK to seats |
| name | TEXT | Campaign name |
| description | TEXT | Description |
| ai_generated | BOOLEAN | Whether AI-generated |
| ai_confidence | REAL | AI confidence score |
| clustering_method | TEXT | Clustering algorithm used |
| status | TEXT | Status (default: 'active') |
| created_at | TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | Last update time |

### creative_campaigns

Maps creatives to AI campaigns (1:1 relationship).

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| creative_id | TEXT | FK to creatives (unique) |
| campaign_id | TEXT | FK to ai_campaigns |
| manually_assigned | BOOLEAN | Manual override flag |
| assigned_at | TIMESTAMP | Assignment time |
| assigned_by | TEXT | Who assigned |

### campaign_creatives

Many-to-many junction table for campaigns and creatives.

| Column | Type | Description |
|--------|------|-------------|
| campaign_id | TEXT | FK to campaigns |
| creative_id | TEXT | FK to creatives |
| added_at | TIMESTAMP | When added |

**Primary Key:** (campaign_id, creative_id)

### campaign_daily_summary

Daily aggregated metrics for AI campaigns.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| campaign_id | TEXT | FK to ai_campaigns |
| date | DATE | Metric date |
| total_creatives | INTEGER | Total creatives |
| active_creatives | INTEGER | Active creatives |
| total_queries | INTEGER | Bid requests |
| total_impressions | INTEGER | Impressions |
| total_clicks | INTEGER | Clicks |
| total_spend | REAL | Spend in USD |
| total_video_starts | INTEGER | Video starts |
| total_video_completions | INTEGER | Video completions |
| avg_win_rate | REAL | Average win rate |
| avg_ctr | REAL | Average CTR |
| avg_cpm | REAL | Average CPM |
| unique_geos | INTEGER | Unique geographies |
| top_geo_id | INTEGER | Top performing geo |
| top_geo_spend | REAL | Spend in top geo |

**Unique Constraint:** (campaign_id, date)

---

## Service Accounts & Buyer Seats

### service_accounts

Google Cloud service accounts for API access.

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Primary key |
| client_email | TEXT | Service account email (unique) |
| project_id | TEXT | GCP project ID |
| display_name | TEXT | Display name |
| credentials_path | TEXT | Path to credentials file |
| is_active | INTEGER | Whether active |
| created_at | TIMESTAMP | Creation time |
| last_used | TIMESTAMP | Last API call time |

### buyer_seats

RTB buyer seats/accounts.

| Column | Type | Description |
|--------|------|-------------|
| buyer_id | TEXT | Primary key |
| bidder_id | TEXT | Bidder account ID |
| service_account_id | TEXT | FK to service_accounts |
| display_name | TEXT | Display name |
| active | INTEGER | Whether active |
| creative_count | INTEGER | Number of creatives |
| last_synced | TIMESTAMP | Last sync time |
| created_at | TIMESTAMP | Creation time |

**Unique Constraint:** (bidder_id, buyer_id)

### seats

Billing accounts (simplified seat reference).

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| billing_id | TEXT | Billing ID (unique) |
| account_name | TEXT | Account name |
| account_id | TEXT | Account ID |
| created_at | TIMESTAMP | Creation time |

---

## RTB Performance & Analytics

### performance_metrics

Granular performance data per creative.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| creative_id | TEXT | FK to creatives |
| campaign_id | TEXT | Campaign ID |
| metric_date | DATE | Date of metrics |
| impressions | INTEGER | Impression count |
| clicks | INTEGER | Click count |
| spend_micros | INTEGER | Spend in micros |
| cpm_micros | INTEGER | CPM in micros |
| cpc_micros | INTEGER | CPC in micros |
| geography | TEXT | Country code (ISO 3166-1) |
| device_type | TEXT | Device type |
| placement | TEXT | Placement info |
| seat_id | INTEGER | Seat ID |
| billing_id | TEXT | Billing ID |
| reached_queries | INTEGER | Bid requests reached |
| created_at | TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | Last update time |

### daily_creative_summary

Daily aggregated metrics per creative.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| seat_id | INTEGER | Seat ID |
| creative_id | TEXT | Creative ID |
| date | DATE | Metric date |
| total_queries | INTEGER | Total bid requests |
| total_impressions | INTEGER | Total impressions |
| total_clicks | INTEGER | Total clicks |
| total_spend | REAL | Total spend (USD) |
| total_video_starts | INTEGER | Video starts |
| total_video_completions | INTEGER | Video completions |
| win_rate | REAL | Win rate percentage |
| ctr | REAL | Click-through rate |
| cpm | REAL | Cost per mille |
| completion_rate | REAL | Video completion rate |
| unique_geos | INTEGER | Unique geographies |
| unique_apps | INTEGER | Unique apps |

**Unique Constraint:** (seat_id, creative_id, date)

### video_metrics

Extended video metrics linked to performance.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| performance_id | INTEGER | FK to performance_metrics (unique) |
| video_starts | INTEGER | Video start count |
| video_q1 | INTEGER | First quartile views |
| video_q2 | INTEGER | Midpoint views |
| video_q3 | INTEGER | Third quartile views |
| video_completions | INTEGER | Completion count |
| vast_errors | INTEGER | VAST error count |
| engaged_views | INTEGER | Engaged view count |

### rtb_daily

Detailed RTB metrics imported from CSV reports (Bids in Auction report).

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| metric_date | DATE | Date of metrics |
| creative_id | TEXT | Creative ID |
| billing_id | TEXT | Billing account ID |
| creative_size | TEXT | Creative dimensions |
| creative_format | TEXT | Format type |
| country | TEXT | Country code |
| platform | TEXT | Platform (WEB, APP) |
| environment | TEXT | Environment type |
| app_id | TEXT | App ID |
| app_name | TEXT | App name |
| publisher_id | TEXT | Publisher ID |
| publisher_name | TEXT | Publisher name |
| publisher_domain | TEXT | Publisher domain |
| deal_id | TEXT | Deal ID |
| deal_name | TEXT | Deal name |
| transaction_type | TEXT | Transaction type |
| advertiser | TEXT | Advertiser name |
| buyer_account_id | TEXT | Buyer account ID |
| buyer_account_name | TEXT | Buyer account name |
| bidder_id | TEXT | Bidder ID |
| hour | INTEGER | Hour (0-23) |
| reached_queries | INTEGER | Bid requests |
| impressions | INTEGER | Impressions |
| clicks | INTEGER | Clicks |
| spend_micros | INTEGER | Spend in micros |
| video_starts | INTEGER | Video starts |
| video_first_quartile | INTEGER | Q1 views |
| video_midpoint | INTEGER | Midpoint views |
| video_third_quartile | INTEGER | Q3 views |
| video_completions | INTEGER | Completions |
| vast_errors | INTEGER | VAST errors |
| engaged_views | INTEGER | Engaged views |
| active_view_measurable | INTEGER | Measurable impressions |
| active_view_viewable | INTEGER | Viewable impressions |
| gma_sdk | INTEGER | GMA SDK flag |
| buyer_sdk | INTEGER | Buyer SDK flag |
| row_hash | TEXT | Unique row hash |
| import_batch_id | TEXT | Import batch ID |
| created_at | TIMESTAMP | Creation time |

**Unique Constraint:** row_hash

### rtb_funnel

RTB funnel metrics for geo and publisher analysis (Funnel report).

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| metric_date | DATE | Date of metrics |
| hour | INTEGER | Hour (0-23, optional) |
| country | TEXT | Country code |
| buyer_account_id | TEXT | Buyer account ID |
| publisher_id | TEXT | Publisher ID |
| publisher_name | TEXT | Publisher name |
| platform | TEXT | Platform |
| environment | TEXT | Environment |
| transaction_type | TEXT | Transaction type |
| inventory_matches | INTEGER | Inventory matches |
| bid_requests | INTEGER | Bid requests sent |
| successful_responses | INTEGER | Successful responses |
| reached_queries | INTEGER | Queries reached |
| bids | INTEGER | Bids submitted |
| bids_in_auction | INTEGER | Bids in auction |
| auctions_won | INTEGER | Auctions won |
| impressions | INTEGER | Impressions served |
| clicks | INTEGER | Clicks received |
| bidder_id | TEXT | Bidder ID |
| row_hash | TEXT | Unique row hash |
| import_batch_id | TEXT | Import batch ID |
| report_type | TEXT | Report type (default: 'funnel') |
| created_at | TIMESTAMP | Creation time |

**Unique Constraint:** row_hash

### rtb_bid_filtering

Bid filtering data for optimization analysis (Bid Filtering report).

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| metric_date | DATE | Date of metrics |
| country | TEXT | Country code |
| buyer_account_id | TEXT | Buyer account ID |
| filtering_reason | TEXT | Why bid was filtered |
| creative_id | TEXT | Creative ID (optional) |
| bids | INTEGER | Number of bids |
| bids_in_auction | INTEGER | Bids that made auction |
| opportunity_cost_micros | INTEGER | Lost opportunity cost |
| bidder_id | TEXT | Bidder ID |
| row_hash | TEXT | Unique row hash |
| import_batch_id | TEXT | Import batch ID |
| created_at | TIMESTAMP | Creation time |

**Unique Constraint:** row_hash

### rtb_traffic

Traffic volume by creative size.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| buyer_id | TEXT | Buyer ID |
| canonical_size | TEXT | Normalized size |
| raw_size | TEXT | Raw size string |
| request_count | INTEGER | Request count |
| date | DATE | Date |
| created_at | TIMESTAMP | Creation time |

**Unique Constraint:** (buyer_id, canonical_size, raw_size, date)

### rtb_quality

Quality and fraud metrics per publisher.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| metric_date | DATE | Date of metrics |
| publisher_id | TEXT | Publisher ID |
| publisher_name | TEXT | Publisher name |
| country | TEXT | Country code |
| impressions | INTEGER | Total impressions |
| pre_filtered_impressions | INTEGER | Pre-filtered count |
| ivt_credited_impressions | INTEGER | IVT credited |
| billed_impressions | INTEGER | Billed impressions |
| measurable_impressions | INTEGER | Measurable count |
| viewable_impressions | INTEGER | Viewable count |
| ivt_rate_pct | REAL | IVT percentage |
| viewability_pct | REAL | Viewability percentage |
| bidder_id | TEXT | Bidder ID |
| row_hash | TEXT | Unique row hash |
| import_batch_id | TEXT | Import batch ID |
| created_at | TIMESTAMP | Creation time |

**Unique Constraint:** row_hash

---

## Pretargeting Configuration

### pretargeting_configs

Current pretargeting configurations from Google.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| bidder_id | TEXT | Bidder account ID |
| config_id | TEXT | Config ID from Google |
| billing_id | TEXT | Billing account ID |
| display_name | TEXT | Config display name |
| user_name | TEXT | User-defined name |
| state | TEXT | State (ACTIVE/SUSPENDED) |
| included_formats | TEXT | Included formats (JSON) |
| included_platforms | TEXT | Included platforms (JSON) |
| included_sizes | TEXT | Included sizes (JSON) |
| included_geos | TEXT | Included geos (JSON) |
| excluded_geos | TEXT | Excluded geos (JSON) |
| raw_config | TEXT | Raw config JSON |
| synced_at | TIMESTAMP | Last sync time |

**Unique Constraint:** (bidder_id, config_id)

### pretargeting_history

Audit trail of pretargeting changes.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| config_id | TEXT | Config ID |
| bidder_id | TEXT | Bidder ID |
| change_type | TEXT | Type of change |
| field_changed | TEXT | Which field changed |
| old_value | TEXT | Previous value |
| new_value | TEXT | New value |
| changed_at | TIMESTAMP | When changed |
| changed_by | TEXT | Who made change |
| change_source | TEXT | Source (api_sync, manual) |
| raw_config_snapshot | TEXT | Full config at time |

### pretargeting_snapshots

Point-in-time snapshots for A/B comparison.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| billing_id | TEXT | Billing account ID |
| snapshot_name | TEXT | Snapshot name |
| snapshot_type | TEXT | Type (manual, auto) |
| included_formats | TEXT | Formats (JSON) |
| included_platforms | TEXT | Platforms (JSON) |
| included_sizes | TEXT | Sizes (JSON) |
| included_geos | TEXT | Included geos (JSON) |
| excluded_geos | TEXT | Excluded geos (JSON) |
| state | TEXT | Config state |
| total_impressions | INTEGER | Impressions during period |
| total_clicks | INTEGER | Clicks during period |
| total_spend_usd | REAL | Spend during period |
| total_reached_queries | INTEGER | Queries reached |
| days_tracked | INTEGER | Days in snapshot |
| avg_daily_impressions | REAL | Daily avg impressions |
| avg_daily_spend_usd | REAL | Daily avg spend |
| ctr_pct | REAL | CTR percentage |
| cpm_usd | REAL | CPM in USD |
| created_at | TIMESTAMP | Creation time |
| notes | TEXT | User notes |

### snapshot_comparisons

Compare before/after pretargeting changes.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| billing_id | TEXT | Billing account ID |
| comparison_name | TEXT | Comparison name |
| before_snapshot_id | INTEGER | FK to pretargeting_snapshots |
| after_snapshot_id | INTEGER | FK to pretargeting_snapshots |
| before_start_date | DATE | Before period start |
| before_end_date | DATE | Before period end |
| after_start_date | DATE | After period start |
| after_end_date | DATE | After period end |
| impressions_delta | INTEGER | Impressions change |
| impressions_delta_pct | REAL | Impressions change % |
| spend_delta_usd | REAL | Spend change |
| spend_delta_pct | REAL | Spend change % |
| ctr_delta_pct | REAL | CTR change % |
| cpm_delta_pct | REAL | CPM change % |
| status | TEXT | Comparison status |
| conclusion | TEXT | Analysis conclusion |
| created_at | TIMESTAMP | Creation time |
| completed_at | TIMESTAMP | Completion time |

### pretargeting_pending_changes

Queue of pending pretargeting changes.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| billing_id | TEXT | Billing account ID |
| config_id | TEXT | Config ID |
| change_type | TEXT | Type of change |
| field_name | TEXT | Field to change |
| value | TEXT | New value |
| reason | TEXT | Reason for change |
| estimated_qps_impact | REAL | Estimated QPS impact |
| created_at | TIMESTAMP | Creation time |
| created_by | TEXT | Who created |
| status | TEXT | Status (pending, applied) |
| applied_at | TIMESTAMP | When applied |
| applied_by | TEXT | Who applied |

### pretargeting_change_log

Log of detected pretargeting changes.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| billing_id | TEXT | Billing account ID |
| change_type | TEXT | Type of change |
| field_changed | TEXT | Field that changed |
| old_value | TEXT | Previous value |
| new_value | TEXT | New value |
| detected_at | TIMESTAMP | When detected |
| auto_snapshot_id | INTEGER | FK to auto-created snapshot |

### rtb_endpoints

RTB endpoint configurations.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| bidder_id | TEXT | Bidder account ID |
| endpoint_id | TEXT | Endpoint ID |
| url | TEXT | Endpoint URL |
| maximum_qps | INTEGER | Max QPS limit |
| trading_location | TEXT | Trading location |
| bid_protocol | TEXT | Bid protocol |
| synced_at | TIMESTAMP | Last sync time |

**Unique Constraint:** (bidder_id, endpoint_id)

---

## Import & Upload Tracking

### import_history

Tracks all CSV import operations.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| batch_id | TEXT | Unique batch ID |
| bidder_id | TEXT | Bidder ID |
| billing_ids_found | TEXT | Billing IDs (JSON) |
| filename | TEXT | Original filename |
| imported_at | TIMESTAMP | Import timestamp |
| rows_read | INTEGER | Rows read |
| rows_imported | INTEGER | Rows imported |
| rows_skipped | INTEGER | Rows skipped |
| rows_duplicate | INTEGER | Duplicate rows |
| date_range_start | DATE | Data start date |
| date_range_end | DATE | Data end date |
| columns_found | TEXT | Columns in file |
| columns_missing | TEXT | Missing columns |
| total_reached | INTEGER | Total reached queries |
| total_impressions | INTEGER | Total impressions |
| total_spend_usd | REAL | Total spend |
| status | TEXT | Import status |
| error_message | TEXT | Error if failed |
| file_size_bytes | INTEGER | File size |

**Unique Constraint:** batch_id

### daily_upload_summary

Daily aggregated upload statistics.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| upload_date | DATE | Date (unique) |
| bidder_id | TEXT | Bidder ID |
| total_uploads | INTEGER | Total uploads |
| successful_uploads | INTEGER | Successful count |
| failed_uploads | INTEGER | Failed count |
| total_rows_written | INTEGER | Total rows |
| total_file_size_bytes | INTEGER | Total size |
| avg_rows_per_upload | REAL | Average rows |
| min_rows | INTEGER | Minimum rows |
| max_rows | INTEGER | Maximum rows |
| has_anomaly | INTEGER | Anomaly flag |
| anomaly_reason | TEXT | Anomaly reason |
| created_at | TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | Last update time |

### account_daily_upload_summary

Per-account daily upload statistics.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| upload_date | DATE | Date |
| bidder_id | TEXT | Bidder account ID |
| total_uploads | INTEGER | Total uploads |
| successful_uploads | INTEGER | Successful count |
| failed_uploads | INTEGER | Failed count |
| total_rows_written | INTEGER | Total rows |
| total_file_size_bytes | INTEGER | Total size |
| avg_rows_per_upload | REAL | Average rows |
| min_rows | INTEGER | Minimum rows |
| max_rows | INTEGER | Maximum rows |
| has_anomaly | INTEGER | Anomaly flag |
| anomaly_reason | TEXT | Anomaly reason |
| created_at | TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | Last update time |

**Unique Constraint:** (upload_date, bidder_id)

### import_anomalies

Detected anomalies during import.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| import_id | TEXT | Import batch ID |
| row_number | INTEGER | Row number |
| anomaly_type | TEXT | Anomaly type |
| creative_id | TEXT | Creative ID if applicable |
| app_id | TEXT | App ID if applicable |
| app_name | TEXT | App name if applicable |
| details | TEXT | Anomaly details |
| created_at | TIMESTAMP | Creation time |

---

## User Authentication & Security

### users

User accounts for platform access.

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Primary key |
| email | TEXT | Email (unique) |
| password_hash | TEXT | Hashed password |
| display_name | TEXT | Display name |
| role | TEXT | Role (admin, user) |
| is_active | INTEGER | Active flag |
| created_at | TEXT | Creation time |
| updated_at | TEXT | Last update time |
| last_login_at | TEXT | Last login time |

### user_sessions

Active user sessions.

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Primary key (session token) |
| user_id | TEXT | FK to users |
| created_at | TEXT | Creation time |
| expires_at | TEXT | Expiration time |
| ip_address | TEXT | Client IP |
| user_agent | TEXT | Browser user agent |

### user_service_account_permissions

User permissions for service accounts.

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Primary key |
| user_id | TEXT | FK to users |
| service_account_id | TEXT | FK to service_accounts |
| permission_level | TEXT | Level (read, write, admin) |
| granted_by | TEXT | Who granted |
| granted_at | TEXT | When granted |

**Unique Constraint:** (user_id, service_account_id)

### login_attempts

Tracks login attempts for security.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| email | TEXT | Attempted email |
| ip_address | TEXT | Client IP |
| attempted_at | TEXT | Attempt time |
| success | INTEGER | Success flag |

### audit_log

Audit trail of user actions.

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Primary key |
| user_id | TEXT | User who acted |
| action | TEXT | Action performed |
| resource_type | TEXT | Resource type |
| resource_id | TEXT | Resource ID |
| details | TEXT | Action details |
| ip_address | TEXT | Client IP |
| created_at | TEXT | Timestamp |

### system_settings

System-wide configuration settings.

| Column | Type | Description |
|--------|------|-------------|
| key | TEXT | Primary key |
| value | TEXT | Setting value |
| description | TEXT | Setting description |
| updated_at | TEXT | Last update |
| updated_by | TEXT | Who updated |

---

## Lookup & Reference Tables

### apps

Mobile app registry.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| app_id | TEXT | App ID (unique) |
| app_name | TEXT | App name |
| platform | TEXT | Platform (iOS, Android) |
| first_seen | TIMESTAMP | First seen time |
| fraud_score | REAL | Fraud risk score |
| quality_tier | TEXT | Quality tier |

### publishers

Publisher registry.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| publisher_id | TEXT | Publisher ID (unique) |
| publisher_name | TEXT | Publisher name |
| first_seen | TIMESTAMP | First seen time |

### geographies

Geography lookup table.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| country_code | VARCHAR(2) | ISO country code |
| country_name | VARCHAR(100) | Country name |
| city_name | VARCHAR(100) | City name |
| created_at | TIMESTAMP | Creation time |

**Unique Constraint:** (country_code, city_name)

### billing_accounts

Billing account lookup table.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| billing_id | TEXT | Billing ID (unique) |
| name | TEXT | Account name |
| created_at | TIMESTAMP | Creation time |

### recommendations

AI-generated recommendations.

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Primary key |
| type | TEXT | Recommendation type |
| severity | TEXT | Severity level |
| confidence | TEXT | Confidence level |
| title | TEXT | Recommendation title |
| description | TEXT | Description |
| evidence_json | TEXT | Supporting evidence |
| impact_json | TEXT | Expected impact |
| actions_json | TEXT | Suggested actions |
| affected_creatives | TEXT | Affected creative IDs |
| affected_campaigns | TEXT | Affected campaign IDs |
| status | TEXT | Status (new, resolved) |
| generated_at | TIMESTAMP | Generation time |
| expires_at | TIMESTAMP | Expiration time |
| resolved_at | TIMESTAMP | Resolution time |
| resolution_notes | TEXT | Resolution notes |

### retention_config

Data retention configuration.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| seat_id | INTEGER | FK to seats |
| raw_retention_days | INTEGER | Raw data retention (default: 90) |
| summary_retention_days | INTEGER | Summary retention (default: 365) |
| auto_aggregate_after_days | INTEGER | Auto-aggregate threshold (default: 30) |
| updated_at | TIMESTAMP | Last update time |

---

## Entity Relationship Summary

```
service_accounts
    └── buyer_seats (1:N)
    └── user_service_account_permissions (1:N)

seats
    └── ai_campaigns (1:N)
    └── retention_config (1:1)

creatives
    ├── campaigns (N:1)
    ├── clusters (N:1)
    ├── creative_campaigns (1:1)
    ├── campaign_creatives (N:M junction)
    ├── performance_metrics (1:N)
    └── thumbnail_status (1:1)

ai_campaigns
    ├── creative_campaigns (1:N)
    └── campaign_daily_summary (1:N)

performance_metrics
    └── video_metrics (1:1)

pretargeting_configs
    ├── pretargeting_history (1:N)
    └── pretargeting_snapshots (via billing_id)
        └── snapshot_comparisons (N:N)

import_history
    └── import_anomalies (1:N)

users
    ├── user_sessions (1:N)
    ├── user_service_account_permissions (1:N)
    ├── login_attempts (by email)
    └── audit_log (1:N)
```

---

## Table Count Summary

| Category | Count |
|----------|-------|
| Creative Management | 3 |
| Campaign Management | 5 |
| Service Accounts & Seats | 3 |
| RTB Performance & Analytics | 7 |
| Pretargeting Configuration | 7 |
| Import & Upload Tracking | 4 |
| User Authentication | 6 |
| Lookup & Reference | 6 |
| **Total** | **41** |
