-- Migration: Add user default language
-- Created: 2026-01-15
-- Description: Store per-user default UI language

ALTER TABLE users ADD COLUMN default_language TEXT DEFAULT 'en';

UPDATE users SET default_language = 'en' WHERE default_language IS NULL;
