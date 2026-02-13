-- Migration 041: Bootstrap tracking
-- Adds bootstrap_completed system setting so the app knows whether
-- the first admin has been provisioned.  Idempotent via ON CONFLICT.

INSERT INTO system_settings (key, value, description)
VALUES ('bootstrap_completed', '0', 'Set to 1 after first admin is bootstrapped')
ON CONFLICT (key) DO NOTHING;

INSERT INTO schema_migrations (version, applied_at, description)
VALUES ('041_bootstrap_tracking', CURRENT_TIMESTAMP, 'Add bootstrap_completed system setting')
ON CONFLICT (version) DO NOTHING;
