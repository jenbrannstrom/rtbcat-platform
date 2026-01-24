-- Migration: Add publisher targeting columns to pretargeting snapshots
-- Created: 2026-01-23

ALTER TABLE pretargeting_snapshots ADD COLUMN publisher_targeting_mode TEXT;
ALTER TABLE pretargeting_snapshots ADD COLUMN publisher_targeting_values TEXT;
