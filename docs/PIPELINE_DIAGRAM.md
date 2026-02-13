# CatScan Platform — Full Data Pipeline Diagram

## High-Level Overview

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                              DATA SOURCES (External)                                     │
│                                                                                          │
│  ┌─────────────────┐   ┌──────────────────────┐   ┌──────────────────┐                   │
│  │  Gmail Inbox     │   │ Google Auth Buyers    │   │ Manual CSV Upload│                   │
│  │  (GCS + attach)  │   │ REST API              │   │ (user via UI)    │                   │
│  └────────┬────────┘   └──────────┬───────────┘   └────────┬─────────┘                   │
└───────────┼─────────────────────┬─┼───────────────────────┬─┼────────────────────────────┘
            │                     │ │                       │ │
            ▼                     │ │                       │ │
┌──────────────────────┐          │ │                       │ │
│ scripts/              │          │ │                       │ │
│  gmail_import.py      │          │ │                       │ │
│  gmail_import_worker  │          │ │                       │ │
│  gmail_import_batch   │          │ │                       │ │
│                       │          │ │                       │ │
│ Download CSV from     │          │ │                       │ │
│ GCS URL or attachment │          │ │                       │ │
└──────────┬────────────┘          │ │                       │ │
           │                       │ │                       │ │
           ▼                       │ │                       ▼ │
┌──────────────────────────────────┼─┼──────────────────────────────────────────────────────┐
│                    INGESTION LAYER                                                        │
│                                  │ │                                                      │
│  ┌───────────────────────────────┼─┼──────────────────────────┐                           │
│  │  importers/unified_importer.py│ │                          │                           │
│  │  - Auto-detect report type    │ │                          │                           │
│  │  - Column mapping (synonyms)  │ │                          │                           │
│  │  - Dedup via import_history   │ │                          │                           │
│  └──────────┬────────────────────┘ │                          │                           │
│             │                      │                          │                           │
│             ▼                      ▼                          │                           │
│  ┌─────────────────────────────────────────────┐              │                           │
│  │           collectors/                        │              │                           │
│  │  seats.py ─────────► buyer_seats             │              │                           │
│  │  csv_reports.py ───► CSV fetch               │              │                           │
│  │                                              │              │                           │
│  │           services/                          │              │                           │
│  │  endpoints_service.py ► rtb_endpoints        │              │                           │
│  │  pretargeting_service.py ► pretargeting_*    │              │                           │
│  │  collect_service.py ► creatives              │              │                           │
│  └──────────────────────────────────────────────┘              │                           │
│                                                                │                           │
│  Tracking:                                                     │                           │
│  ┌──────────────────┐  ┌──────────────────┐                    │                           │
│  │ import_history    │  │ ingestion_runs   │                    │                           │
│  └──────────────────┘  └──────────────────┘                    │                           │
└────────────┬───────────────────────────────────────────────────┘                           │
             │                                                                               │
             ▼                                                                               │
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                         RAW FACT TABLES (PostgreSQL)                                      │
│                                                                                           │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────────┐                       │
│  │   rtb_daily       │  │  rtb_bidstream   │  │ rtb_bid_filtering  │                       │
│  │                   │  │                  │  │                    │                       │
│  │ metric_date       │  │ metric_date      │  │ metric_date        │                       │
│  │ billing_id        │  │ buyer_account_id │  │ buyer_account_id   │                       │
│  │ creative_id       │  │ publisher_id     │  │ filtering_reason   │                       │
│  │ country           │  │ country          │  │ creative_id        │                       │
│  │ buyer_account_id  │  │ reached_queries  │  │ bids               │                       │
│  │ reached_queries   │  │ impressions      │  │ opportunity_cost   │                       │
│  │ impressions       │  │ bids             │  │                    │                       │
│  │ spend_micros      │  │ bid_requests     │  │                    │                       │
│  │ clicks            │  │ auctions_won     │  │                    │                       │
│  └────────┬─────────┘  └───────┬──────────┘  └────────────────────┘                       │
│           │                    │                                                           │
└───────────┼────────────────────┼───────────────────────────────────────────────────────────┘
            │                    │
            ▼                    ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                         BIGQUERY (Analytics Layer)                                        │
│                                                                                           │
│  ┌─────────────────────────────────────────────────────────┐                              │
│  │  Parquet export → BigQuery load                         │                              │
│  │  scripts/export_csv_to_parquet.py                       │                              │
│  │  scripts/load_parquet_to_bigquery.py                    │                              │
│  │                                                         │                              │
│  │  Tables:                                                │                              │
│  │    {project}.{dataset}.rtb_daily                        │                              │
│  │    {project}.{dataset}.rtb_bidstream                    │                              │
│  └─────────────────────────┬───────────────────────────────┘                              │
│                            │                                                              │
└────────────────────────────┼──────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                    PRECOMPUTE / AGGREGATION LAYER                                         │
│                                                                                           │
│  Trigger: scripts/refresh_precompute.py  |  post-import hook  |  API /refresh-precompute  │
│  Log:     precompute_refresh_log                                                          │
│                                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────────────────┐  │
│  │  services/home_precompute.py::refresh_home_summaries()                              │  │
│  │  SOURCE: BigQuery rtb_bidstream + rtb_daily                                         │  │
│  │                                                                                     │  │
│  │  WRITES ──► home_seat_daily        (1 row/day/buyer)                                │  │
│  │         ──► home_config_daily      (1 row/day/buyer/billing_id)                     │  │
│  │         ──► home_publisher_daily   (1 row/day/buyer/publisher)                      │  │
│  │         ──► home_geo_daily         (1 row/day/buyer/country)                        │  │
│  │         ──► home_size_daily        (1 row/day/buyer/creative_size)                  │  │
│  └─────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────────────────┐  │
│  │  services/config_precompute.py::refresh_config_breakdowns()                         │  │
│  │  SOURCE: BigQuery rtb_daily                                                         │  │
│  │                                                                                     │  │
│  │  WRITES ──► config_creative_daily  (1 row/day/buyer/billing/creative)               │  │
│  │         ──► config_geo_daily       (1 row/day/buyer/billing/country)                │  │
│  │         ──► config_size_daily      (1 row/day/buyer/billing/size)                   │  │
│  │         ──► config_publisher_daily (1 row/day/buyer/billing/publisher)              │  │
│  │         ──► fact_delivery_daily    (reconciliation)                                 │  │
│  │         ──► fact_dimension_gaps_daily (data quality)                                │  │
│  └─────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                           │
│  ┌─────────────────────────────────────────────────────────────────────────────────────┐  │
│  │  services/rtb_precompute.py::refresh_rtb_summaries()                                │  │
│  │  SOURCE: BigQuery rtb_bidstream + rtb_daily                                         │  │
│  │                                                                                     │  │
│  │  WRITES ──► rtb_funnel_daily       (funnel metrics per day)                         │  │
│  │         ──► rtb_publisher_daily    (publisher breakdown)                            │  │
│  │         ──► rtb_geo_daily          (geo breakdown)                                  │  │
│  │         ──► rtb_app_daily          (app performance)                                │  │
│  │         ──► rtb_app_size_daily     (app × size)                                     │  │
│  │         ──► rtb_app_country_daily  (app × country)                                  │  │
│  │         ──► rtb_app_creative_daily (app × creative)                                 │  │
│  └─────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                           │
└───────────────────────────────────────────────────────────────────────────────────────────┘
             │
             ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                  DIMENSION / CONFIG TABLES (Live API Sync)                                 │
│                                                                                           │
│  Google Auth Buyers API ─────────────────────────────────────────────┐                    │
│        │                                                             │                    │
│        ├──► collectors/seats.py ──────────► buyer_seats              │                    │
│        │                                    (buyer_id, bidder_id,    │                    │
│        │                                     display_name, active)   │                    │
│        │                                                             │                    │
│        ├──► services/pretargeting_service ► pretargeting_configs     │                    │
│        │                                    (bidder_id, billing_id,  │                    │
│        │                                     display_name, state,    │                    │
│        │                                     geos, formats, sizes)   │                    │
│        │                                                             │                    │
│        ├──► services/endpoints_service ───► rtb_endpoints            │                    │
│        │                                    (bidder_id, endpoint_id, │                    │
│        │                                     url, maximum_qps,       │                    │
│        │                                     trading_location)       │                    │
│        │                                                             │                    │
│        ├──► services/collect_service ─────► creatives                │                    │
│        │                                    (id, name, format,       │                    │
│        │                                     approval_status)        │                    │
│        │                                                             │                    │
│        └──► [QPS observation job] ────────► rtb_endpoints_current    │                    │
│                                              (bidder_id, endpoint_id,│                    │
│                                               current_qps,          │                    │
│                                               observed_at)           │                    │
│                                              ⚠️ CURRENTLY EMPTY      │                    │
│                                                                      │                    │
└──────────────────────────────────────────────────────────────────────┘────────────────────┘
             │
             ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                         API LAYER (FastAPI)                                                │
│                                                                                           │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐   │
│  │  /analytics/home/configs                                                           │   │
│  │  READS: home_seat_daily + home_config_daily + pretargeting_configs                 │   │
│  │  SERVICE: home_analytics_service.py::get_home_configs()                            │   │
│  │  → Config cards with reached, impressions, win_rate, waste_pct                     │   │
│  └────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                           │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐   │
│  │  /analytics/rtb-funnel/configs                                                     │   │
│  │  READS: home_config_daily + rtb_funnel_daily                                       │   │
│  │  SERVICE: home_analytics_service.py::get_rtb_funnel_configs()                      │   │
│  │  → Funnel view: reached → bids → impressions per config                            │   │
│  └────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                           │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐   │
│  │  /analytics/breakdown/{type}                                                       │   │
│  │  READS: config_creative_daily | config_geo_daily | config_publisher_daily |         │   │
│  │         config_size_daily                                                          │   │
│  │  SERVICE: home_analytics_service.py::get_config_breakdown()                        │   │
│  │  → Per-config breakdown by creative / geo / publisher / size                       │   │
│  └────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                           │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐   │
│  │  /analytics/config-performance                                                     │   │
│  │  READS: home_config_daily + pretargeting_configs                                   │   │
│  │  SERVICE: home_analytics_service.py::get_config_performance()                      │   │
│  │  → Daily time-series per config                                                    │   │
│  └────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                           │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐   │
│  │  /analytics/endpoint-efficiency                                                    │   │
│  │  READS: rtb_endpoints + rtb_endpoints_current + home_seat_daily                    │   │
│  │  SERVICE: home_analytics_service.py::get_endpoint_efficiency()                     │   │
│  │  → Allocated QPS, observed QPS, utilization, reconciliation                        │   │
│  │  ⚠️ rtb_endpoints_current is EMPTY → observed_query_rate always null               │   │
│  └────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                           │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐   │
│  │  /seats/list          READS: buyer_seats                                           │   │
│  │  /creatives/list      READS: creatives, creative_thumbnails                        │   │
│  │  /qps/current         READS: rtb_endpoints, rtb_endpoints_current                  │   │
│  │  /performance/upload  WRITES: rtb_daily, import_history                            │   │
│  └────────────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                           │
└───────────────────────────┬───────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌───────────────────────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js Dashboard)                                       │
│                                                                                           │
│  ┌──────────────────┐  ┌──────────────────────┐  ┌────────────────────────┐               │
│  │  Home Page        │  │  RTB Funnel Page      │  │  Config Drill-Down     │               │
│  │                   │  │                       │  │                        │               │
│  │  fetchHomeConfigs │  │  fetchRtbFunnelConfigs│  │  fetchBreakdown(type)  │               │
│  │  ────────────────►│  │  ─────────────────────│  │  ──────────────────────│               │
│  │  /home/configs    │  │  /rtb-funnel/configs  │  │  /breakdown/{type}     │               │
│  │                   │  │                       │  │                        │               │
│  │  Config cards:    │  │  Funnel bars:         │  │  Creative table        │               │
│  │  reached, impr,   │  │  reached → bids →     │  │  Geo breakdown         │               │
│  │  win%, waste%     │  │  impr per config      │  │  Publisher breakdown    │               │
│  └──────────────────┘  └──────────────────────┘  └────────────────────────┘               │
│                                                                                           │
│  ┌──────────────────┐  ┌──────────────────────┐                                           │
│  │  Config Perf      │  │  Endpoint Efficiency  │                                          │
│  │                   │  │  Panel                │                                          │
│  │  fetchConfigPerf  │  │  fetchEndpointEff     │                                          │
│  │  ─────────────────│  │  ─────────────────────│                                          │
│  │  /config-perf     │  │  /endpoint-efficiency │                                          │
│  │                   │  │                       │                                          │
│  │  Time-series      │  │  QPS allocation       │                                          │
│  │  chart per config │  │  vs observation       │                                          │
│  │                   │  │  Reconciliation table │                                          │
│  │                   │  │  Funnel bridge stats  │                                          │
│  └──────────────────┘  └──────────────────────┘                                           │
│                                                                                           │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Table Interconnection Map

```
                    ┌─────────────────────┐
                    │   buyer_seats        │
                    │   (buyer_id,         │
                    │    bidder_id)        │
                    └──────┬──────────────┘
                           │
              ┌────────────┼─────────────────────────────────┐
              │            │                                  │
              ▼            ▼                                  ▼
┌──────────────────┐ ┌──────────────────┐    ┌──────────────────────────┐
│pretargeting_     │ │rtb_endpoints     │    │creatives                 │
│configs           │ │                  │    │                          │
│                  │ │bidder_id ◄───┐   │    │buyer_id                  │
│bidder_id         │ │endpoint_id   │   │    │creative_id               │
│billing_id ◄──┐   │ │maximum_qps   │   │    └──────────────────────────┘
│display_name  │   │ │trading_loc   │   │
│state         │   │ └──────┬───────┘   │
└──────────────┘   │        │           │
               │   │        ▼           │
               │   │ ┌──────────────────┐
               │   │ │rtb_endpoints_    │
               │   │ │current           │
               │   │ │                  │
               │   │ │bidder_id ◄───────┘
               │   │ │endpoint_id
               │   │ │current_qps
               │   │ │observed_at
               │   │ │⚠️ TABLE IS EMPTY
               │   │ └──────────────────┘
               │   │
               │   │
    ┌──────────┘   │
    │              │
    │  billing_id links precomputed data to pretargeting configs
    │              │
    ▼              ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                        RAW FACT TABLES                                           │
│                                                                                  │
│  rtb_daily ◄────────── unified_importer (CSV import)                            │
│    │  metric_date, buyer_account_id, billing_id, creative_id,                   │
│    │  country, publisher_id, reached_queries, impressions, spend_micros          │
│    │                                                                             │
│  rtb_bidstream ◄────── unified_importer (CSV import)                            │
│    │  metric_date, buyer_account_id, publisher_id, country,                     │
│    │  reached_queries, impressions, bids, bid_requests, auctions_won            │
│    │                                                                             │
│  rtb_bid_filtering ◄── unified_importer (CSV import)                            │
│      metric_date, buyer_account_id, filtering_reason, creative_id, bids         │
│                                                                                  │
└─────┬────────────┬───────────────────────────────────────────────────────────────┘
      │            │
      │   ┌────────┘
      │   │  (exported to BigQuery, then aggregated back)
      ▼   ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                    PRECOMPUTED TABLES (via BigQuery)                              │
│                                                                                  │
│  FROM rtb_bidstream:                    FROM rtb_daily:                          │
│  ┌──────────────────────┐              ┌──────────────────────┐                  │
│  │ home_seat_daily       │              │ home_config_daily     │                 │
│  │  metric_date          │◄─────┐      │  metric_date          │                 │
│  │  buyer_account_id     │      │      │  buyer_account_id     │                 │
│  │  reached_queries      │      │      │  billing_id ──────────┼──► joins with   │
│  │  impressions          │      │      │  reached_queries      │    pretargeting_ │
│  │  bids                 │      │      │  impressions          │    configs       │
│  │  bid_requests         │      │      │  bids_in_auction      │                 │
│  │  auctions_won         │      │      │  auctions_won         │                 │
│  └──────────────────────┘      │      └──────────────────────┘                  │
│                                 │                                                │
│  ┌──────────────────────┐      │      ┌──────────────────────┐                  │
│  │ home_publisher_daily  │      │      │ config_creative_daily │                 │
│  │  buyer_account_id     │      │      │  buyer_account_id     │                 │
│  │  publisher_id         │      │      │  billing_id           │                 │
│  └──────────────────────┘      │      │  creative_id ─────────┼──► joins with   │
│                                 │      │  creative_size        │    creatives    │
│  ┌──────────────────────┐      │      │  reached / impr /     │                 │
│  │ home_geo_daily        │      │      │  spend_micros         │                 │
│  │  buyer_account_id     │      │      └──────────────────────┘                  │
│  │  country              │      │                                                │
│  └──────────────────────┘      │      ┌──────────────────────┐                  │
│                                 │      │ config_geo_daily      │                 │
│  ┌──────────────────────┐      │      │  billing_id + country │                 │
│  │ home_size_daily       │      │      └──────────────────────┘                  │
│  │  buyer_account_id     │      │                                                │
│  │  creative_size        │      │      ┌──────────────────────┐                  │
│  └──────────────────────┘      │      │ config_publisher_daily│                  │
│                                 │      │  billing_id +         │                 │
│  ┌──────────────────────┐      │      │  publisher_id         │                 │
│  │ rtb_funnel_daily      │      │      │  ⚠️ 0 ROWS FOR 6574  │                 │
│  │  buyer_account_id     │      │      └──────────────────────┘                  │
│  │  [funnel metrics]     │      │                                                │
│  └──────────────────────┘      │      ┌──────────────────────┐                  │
│                                 │      │ config_size_daily     │                 │
│  ┌──────────────────────┐      │      │  billing_id + size    │                 │
│  │ rtb_publisher_daily   │      │      └──────────────────────┘                  │
│  │ rtb_geo_daily         │      │                                                │
│  │ rtb_app_daily         │      │      ┌──────────────────────┐                  │
│  │ rtb_app_size_daily    │      │      │ fact_delivery_daily   │                 │
│  │ rtb_app_country_daily │      │      │ (reconciliation)      │                 │
│  │ rtb_app_creative_daily│      │      └──────────────────────┘                  │
│  └──────────────────────┘      │                                                │
│                                 │      ┌──────────────────────┐                  │
│  ALL precompute tables ─────────┼─────►│precompute_refresh_log│                  │
│  log their refresh              │      │  cache_name           │                 │
│                                 │      │  buyer_account_id     │                 │
│                                 │      │  refreshed_at         │                 │
│                                 │      └──────────────────────┘                  │
└─────────────────────────────────┘────────────────────────────────────────────────┘
```

---

## API → Table Read Map

```
API Endpoint                        Tables Read                        Frontend Component
─────────────────────────────────── ────────────────────────────────── ──────────────────────
/analytics/home/configs             home_seat_daily                    Home config cards
                                    home_config_daily
                                    pretargeting_configs

/analytics/rtb-funnel/configs       home_config_daily                  RTB funnel bars
                                    rtb_funnel_daily
                                    pretargeting_configs

/analytics/breakdown/creative       config_creative_daily              Creative breakdown tbl
/analytics/breakdown/geo            config_geo_daily                   Geo breakdown table
/analytics/breakdown/publisher      config_publisher_daily             Publisher breakdown
/analytics/breakdown/size           config_size_daily                  Size breakdown table

/analytics/config-performance       home_config_daily                  Time-series chart
                                    pretargeting_configs

/analytics/endpoint-efficiency      rtb_endpoints                      EndpointEfficiency
                                    rtb_endpoints_current  ⚠️ EMPTY    Panel
                                    home_seat_daily

/seats/list                         buyer_seats                        Seat selector dropdown
/creatives/list                     creatives                          Creative browser
/qps/current                        rtb_endpoints                      QPS dashboard
                                    rtb_endpoints_current  ⚠️ EMPTY
```

---

## End-to-End Data Flow (Single Row)

```
1. Gmail receives scheduled report email
          │
2. gmail_import.py downloads CSV from GCS bucket
          │
3. unified_importer.py parses CSV, detects type (rtb_daily)
          │
4. INSERT INTO rtb_daily (metric_date, billing_id, creative_id, ...)
   INSERT INTO import_history (filename, rows_imported, ...)
          │
5. export_csv_to_parquet.py → creates .parquet file
          │
6. load_parquet_to_bigquery.py → uploads to BigQuery rtb_daily
          │
7. refresh_home_summaries() → SELECT ... FROM BQ GROUP BY buyer_account_id, date
          │                   → INSERT INTO home_seat_daily
          │                   → SELECT ... FROM BQ GROUP BY buyer_account_id, billing_id, date
          │                   → INSERT INTO home_config_daily
          │
8. refresh_config_breakdowns() → SELECT ... FROM BQ GROUP BY billing_id, creative_id, date
          │                     → INSERT INTO config_creative_daily
          │
9. INSERT INTO precompute_refresh_log (cache_name, refreshed_at)
          │
10. API /analytics/home/configs → SELECT FROM home_config_daily
                                   JOIN pretargeting_configs ON billing_id
          │
11. Frontend renders config cards with reached, impressions, win_rate
```

---

## Known Data Gaps (from evidence collection)

| Table | Status | Impact |
|-------|--------|--------|
| `rtb_endpoints_current` | **0 rows (all bidders)** | endpoint-efficiency shows no observed QPS |
| `config_publisher_daily` | **0 rows for buyer 6574658621** | publisher breakdown returns empty |
| `ingestion_runs` | **0 rows** | no ingestion tracking |
| `import_history` | **only buyer 6634662463** | no import tracking for 6574658621 |
| billing_id `173162721799` | in pretargeting but **not in precompute** | IDN_Banner_Instl config has no data |
