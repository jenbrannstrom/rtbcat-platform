-- Migration 071: store buyer currency explicitly for spend API responses.
--
-- Authorized Buyers exports label the metric as "Spend (buyer currency)" but
-- do not include the ISO currency code in each report.  The code therefore
-- cannot infer currency from spend_micros.  Keep the account-level code on the
-- buyer seat and return NULL for seats that have not been configured, rather
-- than incorrectly claiming USD.

ALTER TABLE buyer_seats
    ADD COLUMN IF NOT EXISTS currency_code TEXT;

ALTER TABLE buyer_seats
    DROP CONSTRAINT IF EXISTS buyer_seats_currency_code_check;

ALTER TABLE buyer_seats
    ADD CONSTRAINT buyer_seats_currency_code_check
    CHECK (
        currency_code IS NULL
        OR currency_code ~ '^[A-Z]{3}$'
    );

-- Verified current account currencies.  Tuky Display is the retired USD seat;
-- Tuky Internet is Uplivo's replacement EUR seat.
UPDATE buyer_seats AS seat
SET currency_code = mapping.currency_code
FROM (
    VALUES
        ('1487810529', 'USD'),
        ('299038253',  'USD'),
        ('6574658621', 'USD'),
        ('6634662463', 'USD'),
        ('7942355670', 'USD'),
        ('8087233591', 'EUR')
) AS mapping(buyer_id, currency_code)
WHERE seat.buyer_id = mapping.buyer_id;

COMMENT ON COLUMN buyer_seats.currency_code IS
    'ISO-4217 code for Spend (buyer currency); NULL means not configured.';

CREATE OR REPLACE VIEW agent_read.accessible_buyers
WITH (security_barrier = true)
AS
SELECT
    buyer_id,
    bidder_id,
    display_name,
    active,
    creative_count,
    last_synced,
    currency_code AS currency
FROM public.buyer_seats
WHERE agent_private.role_has_buyer_access(buyer_id);
