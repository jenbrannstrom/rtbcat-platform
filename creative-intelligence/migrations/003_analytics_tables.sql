-- Migration: Analytics Tables
-- Created: 2025-12-10
-- Description: Tables for analytics, recommendations, and summary data
-- Note: These match the existing table schemas in the database

-- AI campaigns (for clustering/grouping)
CREATE TABLE IF NOT EXISTS ai_campaigns (
    id TEXT PRIMARY KEY,
    seat_id INTEGER REFERENCES seats(id),
    name TEXT NOT NULL,
    description TEXT,
    ai_generated BOOLEAN DEFAULT TRUE,
    ai_confidence REAL,
    clustering_method TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ai_campaigns_seat ON ai_campaigns(seat_id);
CREATE INDEX IF NOT EXISTS idx_ai_campaigns_status ON ai_campaigns(status);

-- Apps table (fraud detection and quality scoring)
CREATE TABLE IF NOT EXISTS apps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id TEXT UNIQUE,
    app_name TEXT,
    platform TEXT,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    fraud_score REAL DEFAULT 0,
    quality_tier TEXT DEFAULT 'unknown'
);

CREATE INDEX IF NOT EXISTS idx_apps_name ON apps(app_name);

-- Publishers table
CREATE TABLE IF NOT EXISTS publishers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    publisher_id TEXT UNIQUE,
    publisher_name TEXT,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Recommendations table
CREATE TABLE IF NOT EXISTS recommendations (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    severity TEXT NOT NULL,
    confidence TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    evidence_json TEXT,
    impact_json TEXT,
    actions_json TEXT,
    affected_creatives TEXT,
    affected_campaigns TEXT,
    status TEXT DEFAULT 'new',
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    resolved_at TIMESTAMP,
    resolution_notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_rec_type ON recommendations(type);
CREATE INDEX IF NOT EXISTS idx_rec_severity ON recommendations(severity);
CREATE INDEX IF NOT EXISTS idx_rec_status ON recommendations(status);
CREATE INDEX IF NOT EXISTS idx_rec_generated ON recommendations(generated_at DESC);

-- Daily creative summary (aggregated per creative per day)
CREATE TABLE IF NOT EXISTS daily_creative_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seat_id INTEGER,
    creative_id TEXT NOT NULL,
    date DATE NOT NULL,
    total_queries INTEGER DEFAULT 0,
    total_impressions INTEGER DEFAULT 0,
    total_clicks INTEGER DEFAULT 0,
    total_spend REAL DEFAULT 0,
    total_video_starts INTEGER,
    total_video_completions INTEGER,
    win_rate REAL,
    ctr REAL,
    cpm REAL,
    completion_rate REAL,
    unique_geos INTEGER,
    unique_apps INTEGER,
    UNIQUE(seat_id, creative_id, date)
);

CREATE INDEX IF NOT EXISTS idx_summary_seat_date ON daily_creative_summary(seat_id, date);
CREATE INDEX IF NOT EXISTS idx_summary_creative ON daily_creative_summary(creative_id);

-- Campaign daily summary
CREATE TABLE IF NOT EXISTS campaign_daily_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER NOT NULL,
    date DATE NOT NULL,
    total_creatives INTEGER DEFAULT 0,
    active_creatives INTEGER DEFAULT 0,
    total_queries INTEGER DEFAULT 0,
    total_impressions INTEGER DEFAULT 0,
    total_clicks INTEGER DEFAULT 0,
    total_spend REAL DEFAULT 0,
    total_video_starts INTEGER,
    total_video_completions INTEGER,
    avg_win_rate REAL,
    avg_ctr REAL,
    avg_cpm REAL,
    unique_geos INTEGER,
    top_geo_id INTEGER,
    top_geo_spend REAL,
    UNIQUE(campaign_id, date)
);

CREATE INDEX IF NOT EXISTS idx_cds_campaign_date ON campaign_daily_summary(campaign_id, date DESC);

-- Video metrics (detailed video performance)
CREATE TABLE IF NOT EXISTS video_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    performance_id INTEGER UNIQUE,
    video_starts INTEGER DEFAULT 0,
    video_q1 INTEGER DEFAULT 0,
    video_q2 INTEGER DEFAULT 0,
    video_q3 INTEGER DEFAULT 0,
    video_completions INTEGER DEFAULT 0,
    vast_errors INTEGER DEFAULT 0,
    engaged_views INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_video_perf ON video_metrics(performance_id);
