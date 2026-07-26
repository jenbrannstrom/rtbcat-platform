-- Migration 070: durable dedup ledger for Gmail report imports.
--
-- Mark-as-read was the only Gmail import dedup: a read-but-never-imported
-- email was silently lost ("no_new_mail"), and a re-imported file
-- double-counted spend (buyer 6634662463 metric_date 2026-07-01).
-- Discovery now uses a rolling newer_than window and filters message ids
-- with status='imported' here; other statuses stay retryable.

CREATE TABLE IF NOT EXISTS gmail_processed_messages (
    gmail_message_id TEXT PRIMARY KEY,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    subject TEXT,
    seat_id TEXT,
    filename TEXT,
    batch_id TEXT,
    status TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_gmail_processed_messages_status
    ON gmail_processed_messages(status);

COMMENT ON TABLE gmail_processed_messages IS
    'Durable Gmail message dedup for report imports. Import correctness no longer depends on unread state; mark-as-read stays as a human-facing signal.';
