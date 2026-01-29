-- Migration 021: Change INTEGER columns to BIGINT for config breakdown tables
-- Fixes "integer out of range" error when aggregating large RTB data

ALTER TABLE config_size_daily
    ALTER COLUMN reached_queries TYPE BIGINT,
    ALTER COLUMN impressions TYPE BIGINT,
    ALTER COLUMN spend_micros TYPE BIGINT;

ALTER TABLE config_geo_daily
    ALTER COLUMN reached_queries TYPE BIGINT,
    ALTER COLUMN impressions TYPE BIGINT,
    ALTER COLUMN spend_micros TYPE BIGINT;

ALTER TABLE config_publisher_daily
    ALTER COLUMN reached_queries TYPE BIGINT,
    ALTER COLUMN impressions TYPE BIGINT,
    ALTER COLUMN spend_micros TYPE BIGINT;

ALTER TABLE config_creative_daily
    ALTER COLUMN reached_queries TYPE BIGINT,
    ALTER COLUMN impressions TYPE BIGINT,
    ALTER COLUMN spend_micros TYPE BIGINT;
