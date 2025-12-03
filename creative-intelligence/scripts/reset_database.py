#!/usr/bin/env python3
"""Reset database tables for clean unified architecture."""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.expanduser("~/.catscan/catscan.db")

def backup_database():
    """Create backup before destructive changes."""
    if os.path.exists(DB_PATH):
        backup_path = DB_PATH.replace(".db", f"_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
        import shutil
        shutil.copy(DB_PATH, backup_path)
        print(f"Backup created: {backup_path}")
        return backup_path
    return None

def reset_tables():
    """Drop old tables and create new unified schema."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("\n1. Dropping old tables...")
    cursor.executescript("""
        DROP TABLE IF EXISTS size_metrics_daily;
        DROP TABLE IF EXISTS performance_metrics;
        DROP TABLE IF EXISTS fraud_signals;
    """)
    print("   ✓ Dropped: size_metrics_daily, performance_metrics, fraud_signals")

    print("\n2. Creating unified rtb_daily table...")
    cursor.executescript("""
        -- THE Fact Table: rtb_daily
        -- Stores raw CSV data from Authorized Buyers exports
        -- No aggregation at import - one CSV row = one DB row
        --
        -- NOTE: buyer_id, bidder_id are TEXT because Google API returns them as strings
        -- Converting to INTEGER would risk data loss if Google changes format

        CREATE TABLE IF NOT EXISTS rtb_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- ========================================
            -- ESSENTIAL FIELDS (Always export these)
            -- ========================================
            metric_date DATE NOT NULL,           -- Every export has this
            creative_id TEXT,                    -- Join key to creatives table
            billing_id TEXT,                     -- Pretargeting config ID (TEXT - Google format)
            creative_size TEXT,                  -- Size from bid request
            country TEXT,                        -- ESSENTIAL for geo analysis
            app_id TEXT,                         -- ESSENTIAL - where we buy inventory
            advertiser TEXT,                     -- ESSENTIAL - detect blocked advertisers
            reached_queries INTEGER,             -- THE critical waste metric
            impressions INTEGER,                 -- Win rate calculation
            clicks INTEGER,                      -- ESSENTIAL - major engagement signal
            spend_micros INTEGER,                -- Cost tracking

            -- ========================================
            -- IMPORTANT DIMENSIONS
            -- ========================================
            creative_format TEXT,                -- HTML, VIDEO, etc.
            platform TEXT,                       -- Desktop, Mobile, Tablet
            environment TEXT,                    -- App, Web
            app_name TEXT,                       -- Human-readable app name
            publisher_id TEXT,                   -- Publisher blocklist candidates
            publisher_name TEXT,                 -- Human-readable
            publisher_domain TEXT,               -- Domain-level analysis
            deal_id TEXT,                        -- Deal identifier
            deal_name TEXT,                      -- Human-readable
            transaction_type TEXT,               -- Open auction, PMP, etc.
            buyer_account_id TEXT,               -- Buyer seat ID (TEXT - Google format)
            buyer_account_name TEXT,             -- Human-readable

            -- ========================================
            -- VIDEO METRICS
            -- ========================================
            video_starts INTEGER,
            video_first_quartile INTEGER,
            video_midpoint INTEGER,
            video_third_quartile INTEGER,
            video_completions INTEGER,
            vast_errors INTEGER,
            engaged_views INTEGER,

            -- ========================================
            -- VIEWABILITY
            -- ========================================
            active_view_measurable INTEGER,
            active_view_viewable INTEGER,

            -- ========================================
            -- CONVERSIONS (Vendor-agnostic UA data)
            -- ========================================
            conversions INTEGER,                          -- Generic conversion count
            ua_installs INTEGER,                          -- App installs
            ua_reinstalls INTEGER,                        -- App reinstalls
            ua_uninstalls INTEGER,                        -- App uninstalls
            ua_sessions INTEGER,                          -- App sessions
            ua_in_app_events INTEGER,                     -- In-app events
            ua_ad_revenue REAL,                           -- Ad revenue (USD)
            ua_skan_conversions INTEGER,                  -- SKAdNetwork conversions (iOS)
            ua_retargeting_reengagements INTEGER,         -- Retargeting re-engagements
            ua_retargeting_reattributions INTEGER,        -- Retargeting re-attributions
            ua_fraud_blocked_installs INTEGER,            -- Fraud: blocked installs

            -- ========================================
            -- SDK FLAGS
            -- ========================================
            gma_sdk INTEGER DEFAULT 0,
            buyer_sdk INTEGER DEFAULT 0,

            -- ========================================
            -- METADATA
            -- ========================================
            row_hash TEXT,
            import_batch_id TEXT,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            -- Prevent exact duplicate rows
            UNIQUE(row_hash)
        );

        -- Indices for common queries
        CREATE INDEX IF NOT EXISTS idx_rtb_date ON rtb_daily(metric_date);
        CREATE INDEX IF NOT EXISTS idx_rtb_creative ON rtb_daily(creative_id);
        CREATE INDEX IF NOT EXISTS idx_rtb_billing ON rtb_daily(billing_id);
        CREATE INDEX IF NOT EXISTS idx_rtb_size ON rtb_daily(creative_size);
        CREATE INDEX IF NOT EXISTS idx_rtb_country ON rtb_daily(country);
        CREATE INDEX IF NOT EXISTS idx_rtb_app ON rtb_daily(app_id);
        CREATE INDEX IF NOT EXISTS idx_rtb_advertiser ON rtb_daily(advertiser);
        CREATE INDEX IF NOT EXISTS idx_rtb_batch ON rtb_daily(import_batch_id);

        -- Compound indices for reports
        CREATE INDEX IF NOT EXISTS idx_rtb_date_billing ON rtb_daily(metric_date, billing_id);
        CREATE INDEX IF NOT EXISTS idx_rtb_date_size ON rtb_daily(metric_date, creative_size);
        CREATE INDEX IF NOT EXISTS idx_rtb_date_creative ON rtb_daily(metric_date, creative_id);
        CREATE INDEX IF NOT EXISTS idx_rtb_date_app ON rtb_daily(metric_date, app_id);
        CREATE INDEX IF NOT EXISTS idx_rtb_date_country ON rtb_daily(metric_date, country);
    """)
    print("   ✓ Created: rtb_daily with indices")

    print("\n3. Creating fraud_signals table...")
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS fraud_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            entity_name TEXT,

            signal_type TEXT NOT NULL,
            signal_strength TEXT NOT NULL,
            evidence TEXT,

            days_observed INTEGER DEFAULT 1,
            first_seen DATE,
            last_seen DATE,

            status TEXT DEFAULT 'pending',
            reviewed_by TEXT,
            reviewed_at TIMESTAMP,
            notes TEXT,

            UNIQUE(entity_type, entity_id, signal_type)
        );

        CREATE INDEX IF NOT EXISTS idx_fraud_status ON fraud_signals(status);
        CREATE INDEX IF NOT EXISTS idx_fraud_entity ON fraud_signals(entity_type, entity_id);
    """)
    print("   ✓ Created: fraud_signals")

    print("\n4. Creating waste_signals table (Phase 11.2)...")
    cursor.executescript("""
        -- Phase 11.2: Evidence-based waste signals
        -- Stores waste detection signals with full evidence chain
        CREATE TABLE IF NOT EXISTS waste_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            creative_id TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            confidence TEXT DEFAULT 'medium',  -- low, medium, high
            evidence JSON NOT NULL,  -- Full evidence object
            observation TEXT,  -- Human-readable explanation
            recommendation TEXT,  -- Suggested action
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP,
            resolved_by TEXT,
            resolution_notes TEXT,

            FOREIGN KEY (creative_id) REFERENCES creatives(id)
        );

        CREATE INDEX IF NOT EXISTS idx_waste_signals_creative ON waste_signals(creative_id);
        CREATE INDEX IF NOT EXISTS idx_waste_signals_type ON waste_signals(signal_type);
        CREATE INDEX IF NOT EXISTS idx_waste_signals_confidence ON waste_signals(confidence);
        CREATE INDEX IF NOT EXISTS idx_waste_signals_unresolved ON waste_signals(resolved_at) WHERE resolved_at IS NULL;
    """)
    print("   ✓ Created: waste_signals with indices")

    print("\n5. Creating import_history table...")
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS import_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            batch_id TEXT NOT NULL UNIQUE,
            filename TEXT,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            rows_read INTEGER DEFAULT 0,
            rows_imported INTEGER DEFAULT 0,
            rows_skipped INTEGER DEFAULT 0,
            rows_duplicate INTEGER DEFAULT 0,

            date_range_start DATE,
            date_range_end DATE,

            columns_found TEXT,
            columns_missing TEXT,

            total_reached INTEGER DEFAULT 0,
            total_impressions INTEGER DEFAULT 0,
            total_spend_usd REAL DEFAULT 0,

            status TEXT DEFAULT 'complete',
            error_message TEXT
        );
    """)
    print("   ✓ Created: import_history")

    print("\n6. Creating troubleshooting_data tables (Phase 11)...")
    cursor.executescript("""
        -- Phase 11: RTB Troubleshooting API data storage
        -- Low-volume aggregate data (~100-200 rows/day)
        -- Store raw JSON, extract only what's needed for indexing

        CREATE TABLE IF NOT EXISTS troubleshooting_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            -- When collected
            collection_date DATE NOT NULL,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            -- What type of data
            metric_type TEXT NOT NULL,  -- 'filtered_bids', 'bid_metrics', 'callout_status', 'loser_bids'

            -- Extracted keys for querying (from raw_data)
            status_code INTEGER,        -- creative_status_id or callout_status_id
            status_name TEXT,           -- Human-readable status

            -- The actual numbers
            bid_count INTEGER,
            impression_count INTEGER,

            -- Full API response for anything we didn't extract
            raw_data JSON,

            -- Prevent duplicates
            UNIQUE(collection_date, metric_type, status_code)
        );

        -- Collection log (one row per API call)
        CREATE TABLE IF NOT EXISTS troubleshooting_collections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            collection_date DATE NOT NULL,
            days_requested INTEGER,
            filter_set_name TEXT,

            -- What we got
            filtered_bids_count INTEGER DEFAULT 0,
            bid_metrics_count INTEGER DEFAULT 0,
            callout_count INTEGER DEFAULT 0,

            -- Full raw response (for debugging)
            raw_response JSON,

            status TEXT DEFAULT 'complete',
            error_message TEXT,
            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            UNIQUE(collection_date)
        );

        -- Minimal indexes - add more when we know query patterns
        CREATE INDEX IF NOT EXISTS idx_ts_date_type ON troubleshooting_data(collection_date, metric_type);
        CREATE INDEX IF NOT EXISTS idx_ts_status ON troubleshooting_data(status_name);
    """)
    print("   ✓ Created: troubleshooting_data and troubleshooting_collections")

    conn.commit()

    # Verify creatives table still exists
    cursor.execute("SELECT COUNT(*) FROM creatives")
    creative_count = cursor.fetchone()[0]
    print(f"\n7. Verified: creatives table intact ({creative_count} rows)")

    conn.close()
    print("\n✅ Database reset complete!")

if __name__ == "__main__":
    print("=" * 60)
    print("RTBcat Database Reset")
    print("=" * 60)

    confirm = input("\nThis will DELETE performance data (creatives preserved).\nContinue? (yes/no): ")

    if confirm.lower() == "yes":
        backup_database()
        reset_tables()
        print("\nNext: Run the CSV importer")
        print("  python cli/qps_analyzer.py import <your_csv_file>")
    else:
        print("Cancelled.")
