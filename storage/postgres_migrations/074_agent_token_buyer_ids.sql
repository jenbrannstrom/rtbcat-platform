-- Migration 074: explicit multi-buyer hard-scope for agent API tokens.
--
-- A token could be hard-scoped to one buyer (buyer_id) or carry no hard-scope
-- at all (non-sudo users only, bounded by seat grants). buyer_ids adds a third
-- shape: an explicit list of buyers, which is also allowed for sudo users.
--
-- A list token keeps buyer_id set to the first listed buyer. Releases that
-- pre-date this column only read buyer_id, so after an image rollback they
-- treat the token as a single-buyer token instead of an unscoped one.

ALTER TABLE agent_api_tokens
    ADD COLUMN IF NOT EXISTS buyer_ids TEXT[];

ALTER TABLE agent_api_tokens
    DROP CONSTRAINT IF EXISTS agent_api_tokens_buyer_ids_check;

ALTER TABLE agent_api_tokens
    ADD CONSTRAINT agent_api_tokens_buyer_ids_check
    CHECK (
        buyer_ids IS NULL
        OR (
            cardinality(buyer_ids) BETWEEN 1 AND 50
            AND buyer_id IS NOT NULL
            AND buyer_id = buyer_ids[1]
        )
    );

COMMENT ON COLUMN agent_api_tokens.buyer_ids IS
    'Explicit buyer hard-scope list. NULL means buyer_id (or the user''s seat grants) is the scope. When set, buyer_id mirrors the first entry for pre-074 releases.';
