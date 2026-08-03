import json
from datetime import datetime
from typing import Dict, Iterable, List, Optional

import psycopg2
from psycopg2.extras import DictCursor, execute_batch

from ingestion.utils import UTC

_SCHEMA = """
CREATE TABLE IF NOT EXISTS source_poll_state (
    feed_id        TEXT PRIMARY KEY,
    last_polled_at TEXT NOT NULL
);

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
"""

class PostgresIngestionStore:
    def __init__(self, connection_string: str) -> None:
        self.connection_string = connection_string

    def _connect(self):
        return psycopg2.connect(self.connection_string)

    def initialize(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(_SCHEMA)
            conn.commit()

    def get_poll_state(self) -> Dict[str, str]:
        with self._connect() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute("SELECT feed_id, last_polled_at FROM source_poll_state")
                return {str(row["feed_id"]): str(row["last_polled_at"]) for row in cur.fetchall()}

    def upsert_poll_state(self, poll_updates: Dict[str, str]) -> None:
        if not poll_updates:
            return
        with self._connect() as conn:
            with conn.cursor() as cur:
                execute_batch(
                    cur,
                    """
                    INSERT INTO source_poll_state(feed_id, last_polled_at)
                    VALUES (%s, %s)
                    ON CONFLICT(feed_id) DO UPDATE SET last_polled_at = EXCLUDED.last_polled_at
                    """,
                    list(poll_updates.items()),
                )
            conn.commit()

    def upsert_stories(self, stories: List[Dict]) -> None:
        if not stories:
            return
        now_iso = datetime.now(UTC).isoformat()
        rows = [
            (
                story["story_id"],
                story["source_count"],
                story["recency"],
                now_iso,
                story.get("centroid"),
            )
            for story in stories
        ]
        with self._connect() as conn:
            with conn.cursor() as cur:
                execute_batch(
                    cur,
                    """
                    INSERT INTO stories(story_id, source_count, recency, created_at, centroid)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT(story_id) DO UPDATE SET
                        source_count = EXCLUDED.source_count,
                        recency      = EXCLUDED.recency,
                        centroid     = COALESCE(EXCLUDED.centroid, stories.centroid)
                    """,
                    rows,
                )
            conn.commit()

    def upsert_items(self, items: Iterable[Dict]) -> int:
        rows = []
        for item in items:
            rows.append(
                (
                    str(item["item_hash"]),
                    item["source_id"],
                    item["source_name"],
                    item["source_type"],
                    item["region"],
                    item["url"],
                    item.get("title"),
                    item.get("raw_text"),
                    item.get("published_at"),
                    item["fetched_at"],
                    item.get("author"),
                    item.get("lang"),
                    int(bool(item.get("paywall", False))),
                    int(bool(item.get("is_social", False))),
                    item.get("extraction_status", "ok"),
                    item.get("story_id"),
                    int(bool(item.get("has_cross_source_corroboration", False))),
                    item.get("image_url")
                )
            )

        if not rows:
            return 0

        with self._connect() as conn:
            with conn.cursor() as cur:
                execute_batch(
                    cur,
                    """
                    INSERT INTO items(
                        item_hash, source_id, source_name, source_type, region, url,
                        title, raw_text, published_at, fetched_at, author, lang,
                        paywall, is_social, extraction_status, story_id,
                        has_cross_source_corroboration, image_url
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(item_hash) DO UPDATE SET
                        source_name                    = EXCLUDED.source_name,
                        source_type                    = EXCLUDED.source_type,
                        region                         = EXCLUDED.region,
                        title                          = EXCLUDED.title,
                        raw_text                       = EXCLUDED.raw_text,
                        published_at                   = EXCLUDED.published_at,
                        fetched_at                     = EXCLUDED.fetched_at,
                        author                         = EXCLUDED.author,
                        lang                           = EXCLUDED.lang,
                        paywall                        = EXCLUDED.paywall,
                        is_social                      = EXCLUDED.is_social,
                        extraction_status              = EXCLUDED.extraction_status,
                        story_id                       = EXCLUDED.story_id,
                        has_cross_source_corroboration = EXCLUDED.has_cross_source_corroboration,
                        image_url                      = EXCLUDED.image_url
                    """,
                    rows,
                )
            conn.commit()
            return len(rows)

    def flag_for_review(self, items: Iterable[Dict]) -> None:
        now_iso = datetime.now(UTC).isoformat()
        rows = [
            (
                str(item["item_hash"]),
                f"extraction_status:{item['extraction_status']}",
                now_iso,
            )
            for item in items
            if item.get("extraction_status") in {"short", "failed"}
        ]
        if not rows:
            return
        with self._connect() as conn:
            with conn.cursor() as cur:
                execute_batch(
                    cur,
                    """
                    INSERT INTO review_queue(item_hash, reason, status, flagged_at)
                    VALUES (%s, %s, 'pending', %s)
                    ON CONFLICT(item_hash) DO UPDATE SET
                        reason     = EXCLUDED.reason,
                        flagged_at = EXCLUDED.flagged_at
                    """,
                    rows,
                )
            conn.commit()

    def get_pending_extraction_items(self, limit: int = 50) -> List[Dict]:
        with self._connect() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cur:
                cur.execute(
                    """
                    SELECT i.item_hash, i.url, i.source_name, i.extraction_status
                    FROM review_queue rq
                    JOIN items i ON i.item_hash = rq.item_hash
                    WHERE rq.status = 'pending'
                      AND i.paywall = 0
                      AND i.url IS NOT NULL
                      AND i.url != ''
                    ORDER BY i.published_at DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                return [dict(row) for row in cur.fetchall()]

    def update_item_extraction(
        self, item_hash: str, raw_text: str, extraction_status: str, image_url: Optional[str] = None
    ) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE items
                    SET raw_text = %s, extraction_status = %s, image_url = COALESCE(%s, image_url)
                    WHERE item_hash = %s
                    """,
                    (raw_text, extraction_status, image_url, item_hash),
                )
            conn.commit()

    def resolve_review_item(self, item_hash: str, status: str) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE review_queue SET status = %s WHERE item_hash = %s",
                    (status, item_hash),
                )
            conn.commit()
