-- Migration: Billing ID Tracking
-- Created: 2025-12-10
-- Description: Add billing_id to performance_metrics for per-account filtering

-- Add billing_id column to performance_metrics
-- This allows filtering analysis by billing account (pretargeting config)
ALTER TABLE performance_metrics ADD COLUMN billing_id TEXT;

-- Create index for efficient filtering by billing_id
CREATE INDEX IF NOT EXISTS idx_perf_billing_id ON performance_metrics(billing_id);

-- Create composite index for common query pattern: billing_id + date range
CREATE INDEX IF NOT EXISTS idx_perf_billing_date ON performance_metrics(billing_id, metric_date DESC);

