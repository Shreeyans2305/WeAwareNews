CREATE TABLE IF NOT EXISTS sherlock_invites (
    email TEXT PRIMARY KEY CHECK (email = LOWER(email)),
    expires_at TIMESTAMPTZ NOT NULL,
    credits INTEGER NOT NULL CHECK (credits BETWEEN 1 AND 20),
    granted_by TEXT NOT NULL,
    redeemed_uid TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
