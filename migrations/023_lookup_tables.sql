-- Migration: Create lookup tables (geographies, apps, publishers, billing_accounts)
-- Created: 2026-01-18
-- Description: Normalize common lookup data and provide geo mappings

CREATE TABLE IF NOT EXISTS geographies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT,
    country_name TEXT,
    city_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(country_code, city_name)
);

CREATE TABLE IF NOT EXISTS apps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id TEXT UNIQUE,
    app_name TEXT,
    platform TEXT,
    store_url TEXT,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS billing_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    billing_id TEXT UNIQUE NOT NULL,
    name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS publishers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    publisher_id TEXT UNIQUE,
    publisher_name TEXT,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_geo_country ON geographies(country_code);
CREATE INDEX IF NOT EXISTS idx_geo_name ON geographies(country_name);
CREATE INDEX IF NOT EXISTS idx_apps_name ON apps(app_name);
CREATE INDEX IF NOT EXISTS idx_apps_platform ON apps(platform);
CREATE INDEX IF NOT EXISTS idx_publishers_name ON publishers(publisher_name);

INSERT OR IGNORE INTO geographies (country_code, country_name) VALUES
('US', 'United States'),
('GB', 'United Kingdom'),
('CA', 'Canada'),
('AU', 'Australia'),
('DE', 'Germany'),
('FR', 'France'),
('JP', 'Japan'),
('BR', 'Brazil'),
('IN', 'India'),
('MX', 'Mexico'),
('ES', 'Spain'),
('IT', 'Italy'),
('NL', 'Netherlands'),
('SE', 'Sweden'),
('NO', 'Norway'),
('DK', 'Denmark'),
('FI', 'Finland'),
('PL', 'Poland'),
('RU', 'Russia'),
('CN', 'China'),
('KR', 'South Korea'),
('SG', 'Singapore'),
('ID', 'Indonesia'),
('TH', 'Thailand'),
('MY', 'Malaysia'),
('PH', 'Philippines'),
('VN', 'Vietnam'),
('AR', 'Argentina'),
('CL', 'Chile'),
('CO', 'Colombia'),
('PE', 'Peru'),
('ZA', 'South Africa'),
('NG', 'Nigeria'),
('EG', 'Egypt'),
('AE', 'United Arab Emirates'),
('SA', 'Saudi Arabia'),
('IL', 'Israel'),
('TR', 'Turkey'),
('IE', 'Ireland'),
('PT', 'Portugal'),
('AT', 'Austria'),
('CH', 'Switzerland'),
('BE', 'Belgium'),
('CZ', 'Czech Republic'),
('HU', 'Hungary'),
('RO', 'Romania'),
('UA', 'Ukraine'),
('GR', 'Greece'),
('NZ', 'New Zealand'),
('HK', 'Hong Kong'),
('TW', 'Taiwan');
