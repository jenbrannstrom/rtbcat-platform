-- Postgres schema for dimension tables

CREATE TABLE IF NOT EXISTS dim_creative (
    creative_id TEXT PRIMARY KEY,
    creative_size TEXT,
    creative_format TEXT,
    app_id TEXT,
    app_name TEXT
);

CREATE TABLE IF NOT EXISTS dim_publisher (
    publisher_id TEXT PRIMARY KEY,
    publisher_name TEXT
);

CREATE TABLE IF NOT EXISTS dim_country (
    country_code TEXT PRIMARY KEY,
    country_name TEXT
);

CREATE TABLE IF NOT EXISTS dim_billing (
    billing_id TEXT PRIMARY KEY,
    billing_name TEXT
);

CREATE TABLE IF NOT EXISTS dim_time (
    metric_date DATE PRIMARY KEY,
    day_of_week SMALLINT,
    month SMALLINT,
    year SMALLINT
);

CREATE INDEX IF NOT EXISTS idx_dim_creative_size ON dim_creative(creative_size);
CREATE INDEX IF NOT EXISTS idx_dim_creative_format ON dim_creative(creative_format);
CREATE INDEX IF NOT EXISTS idx_dim_creative_app_id ON dim_creative(app_id);
CREATE INDEX IF NOT EXISTS idx_dim_publisher_name ON dim_publisher(publisher_name);
CREATE INDEX IF NOT EXISTS idx_dim_country_name ON dim_country(country_name);
