-- Production Schema Truth extracted verbatim from Cloud SQL weaware-pg
-- Matches information_schema.columns and \d stories, \d items exactly

CREATE TABLE IF NOT EXISTS stories (
    story_id     TEXT PRIMARY KEY,
    source_count INTEGER NOT NULL,
    recency      TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    centroid     TEXT,
    posted       BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS items (
    item_hash                   TEXT PRIMARY KEY,
    source_id                   TEXT NOT NULL,
    source_name                 TEXT NOT NULL,
    source_type                 TEXT NOT NULL,
    region                      TEXT NOT NULL,
    url                         TEXT NOT NULL,
    title                       TEXT,
    raw_text                    TEXT,
    published_at                TEXT,
    fetched_at                  TEXT NOT NULL,
    author                      TEXT,
    lang                        TEXT,
    paywall                     INTEGER NOT NULL DEFAULT 0,
    is_social                   INTEGER NOT NULL DEFAULT 0,
    extraction_status           TEXT NOT NULL DEFAULT 'ok',
    story_id                    TEXT REFERENCES stories(story_id),
    has_cross_source_corroboration INTEGER NOT NULL DEFAULT 0,
    image_url                   TEXT
);

CREATE TABLE IF NOT EXISTS review_queue (
    id         SERIAL PRIMARY KEY,
    item_hash  TEXT NOT NULL UNIQUE REFERENCES items(item_hash),
    reason     TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'pending',
    flagged_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_items_published_at      ON items(published_at);
CREATE INDEX IF NOT EXISTS idx_items_source_id         ON items(source_id);
CREATE INDEX IF NOT EXISTS idx_items_story_id          ON items(story_id);
CREATE INDEX IF NOT EXISTS idx_items_extraction_status ON items(extraction_status);
CREATE INDEX IF NOT EXISTS idx_stories_recency         ON stories(recency);
CREATE INDEX IF NOT EXISTS idx_review_queue_status     ON review_queue(status);
