CREATE TABLE IF NOT EXISTS creative_thumbnails (
    creative_id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',
    error_reason TEXT,
    gcs_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_thumbnails_status ON creative_thumbnails(status);
