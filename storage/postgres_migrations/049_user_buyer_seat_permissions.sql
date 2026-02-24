-- Migration 049: explicit buyer-seat permissions for users
-- Adds first-class seat access assignment to support user management without
-- depending on indirect service-account permissions.

CREATE TABLE IF NOT EXISTS user_buyer_seat_permissions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    buyer_id TEXT NOT NULL REFERENCES buyer_seats(buyer_id) ON DELETE CASCADE,
    access_level TEXT NOT NULL DEFAULT 'read' CHECK (access_level IN ('read', 'admin')),
    granted_by TEXT,
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, buyer_id)
);

CREATE INDEX IF NOT EXISTS idx_user_buyer_seat_permissions_user
    ON user_buyer_seat_permissions(user_id);

CREATE INDEX IF NOT EXISTS idx_user_buyer_seat_permissions_buyer
    ON user_buyer_seat_permissions(buyer_id);
