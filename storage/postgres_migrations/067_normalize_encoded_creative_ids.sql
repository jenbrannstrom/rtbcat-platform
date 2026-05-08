-- Normalize creative IDs accidentally persisted from URL-encoded API resource names.
--
-- Google report CSVs use decoded creative IDs, while API resource names may contain
-- URL-encoded path characters such as %2F and %2B. Rows with encoded IDs cannot join
-- to performance facts, so normalize safe, unreferenced creative metadata rows.

CREATE TEMP TABLE _creative_id_decode_map ON COMMIT DROP AS
SELECT
    id AS old_id,
    REPLACE(
        REPLACE(
            REPLACE(
                REPLACE(id, '%2F', '/'),
            '%2f', '/'),
        '%2B', '+'),
    '%2b', '+') AS new_id
FROM creatives
WHERE id LIKE '%\%%' ESCAPE '\';

DELETE FROM _creative_id_decode_map
WHERE old_id = new_id;

UPDATE creatives c
SET id = m.new_id
FROM _creative_id_decode_map m
WHERE c.id = m.old_id
  AND NOT EXISTS (SELECT 1 FROM creatives existing WHERE existing.id = m.new_id)
  AND NOT EXISTS (SELECT 1 FROM performance_metrics p WHERE p.creative_id = m.old_id)
  AND NOT EXISTS (SELECT 1 FROM campaign_creatives cc WHERE cc.creative_id = m.old_id)
  AND NOT EXISTS (SELECT 1 FROM thumbnail_status ts WHERE ts.creative_id = m.old_id)
  AND NOT EXISTS (SELECT 1 FROM creative_campaigns ac WHERE ac.creative_id = m.old_id)
  AND (
      to_regclass('public.creative_thumbnails') IS NULL
      OR NOT EXISTS (SELECT 1 FROM creative_thumbnails ct WHERE ct.creative_id = m.old_id)
  );

UPDATE creative_live_fetch_telemetry t
SET creative_id = m.new_id
FROM _creative_id_decode_map m
WHERE t.creative_id = m.old_id
  AND EXISTS (SELECT 1 FROM creatives c WHERE c.id = m.new_id);

UPDATE creative_analysis_runs r
SET creative_id = m.new_id
FROM _creative_id_decode_map m
WHERE r.creative_id = m.old_id
  AND EXISTS (SELECT 1 FROM creatives c WHERE c.id = m.new_id);

INSERT INTO schema_migrations (version, applied_at, description)
VALUES (
    '067_normalize_encoded_creative_ids',
    CURRENT_TIMESTAMP,
    'Normalize URL-encoded creative IDs from API resource names so performance facts join correctly'
)
ON CONFLICT (version) DO NOTHING;
