-- Migration 061: Accelerate buyer-scoped bidder joins used by startup pretargeting queries.

CREATE INDEX IF NOT EXISTS idx_buyer_seats_buyer_bidder
    ON buyer_seats (buyer_id, bidder_id);

INSERT INTO schema_migrations (version, applied_at, description)
VALUES (
    '061_buyer_seats_buyer_bidder_index',
    CURRENT_TIMESTAMP,
    'Add composite buyer_seats index for buyer-scoped bidder join paths'
)
ON CONFLICT (version) DO NOTHING;
