CREATE TABLE IF NOT EXISTS sherlock_access (
    uid TEXT PRIMARY KEY,
    expires_at TIMESTAMPTZ NOT NULL,
    credits INTEGER NOT NULL CHECK (credits BETWEEN 0 AND 100),
    granted_by TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS sherlock_budget (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    ceiling NUMERIC(14,8) NOT NULL CHECK (ceiling > 0 AND ceiling <= 10),
    committed NUMERIC(14,8) NOT NULL DEFAULT 0 CHECK (committed >= 0),
    CHECK (committed <= ceiling)
);
INSERT INTO sherlock_budget(id, ceiling) VALUES (1, 10) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS sherlock_requests (
    id TEXT PRIMARY KEY,
    uid TEXT NOT NULL REFERENCES sherlock_access(uid),
    submission_key TEXT NOT NULL,
    question TEXT NOT NULL,
    scope TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN
        ('queued','researching','awaiting_review','completed','failed','cancelled','insufficient_evidence')),
    stage TEXT NOT NULL DEFAULT 'queued',
    credit_state TEXT NOT NULL DEFAULT 'reserved' CHECK (credit_state IN ('reserved','consumed','refunded')),
    cost_limit NUMERIC(14,8) NOT NULL CHECK (cost_limit > 0 AND cost_limit <= 0.5),
    committed NUMERIC(14,8) NOT NULL DEFAULT 0 CHECK (committed >= 0 AND committed <= cost_limit),
    lease_token TEXT,
    lease_until TIMESTAMPTZ,
    report JSONB,
    review JSONB,
    error_code TEXT,
    reviewed_by TEXT,
    review_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    due_at TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours',
    completed_at TIMESTAMPTZ,
    UNIQUE(uid, submission_key)
);
CREATE UNIQUE INDEX IF NOT EXISTS sherlock_one_active ON sherlock_requests(uid)
    WHERE status IN ('queued','researching','awaiting_review');
CREATE INDEX IF NOT EXISTS sherlock_queue ON sherlock_requests(status, created_at);
CREATE TABLE IF NOT EXISTS sherlock_operations (
    request_id TEXT NOT NULL REFERENCES sherlock_requests(id),
    name TEXT NOT NULL,
    reserved NUMERIC(14,8) NOT NULL CHECK (reserved > 0),
    charged NUMERIC(14,8),
    state TEXT NOT NULL DEFAULT 'reserved' CHECK (state IN ('reserved','settled')),
    metadata JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY(request_id, name)
);
CREATE TABLE IF NOT EXISTS sherlock_artifacts (
    request_id TEXT NOT NULL REFERENCES sherlock_requests(id),
    name TEXT NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY(request_id, name)
);
CREATE TABLE IF NOT EXISTS sherlock_audit (
    id BIGSERIAL PRIMARY KEY,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    target TEXT NOT NULL,
    note TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
