"""
SQLite storage layer for the WeAware ingestion pipeline.

Single database — ingestion/store/items.db — with the following tables:

  source_poll_state   tracks when each RSS feed was last fetched
  stories             one row per cross-source story cluster
  items               one row per news item (FK → stories)
  review_queue        items flagged for human review (short/failed extraction)

All writes use upsert (INSERT … ON CONFLICT DO UPDATE) so the store is
idempotent and safe to call on every ingestion cycle.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from ingestion.utils import UTC, stable_item_hash


_SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS source_poll_state (
    feed_id        TEXT PRIMARY KEY,
    last_polled_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stories (
    story_id     TEXT PRIMARY KEY,
    source_count INTEGER NOT NULL,
    recency      TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    centroid     TEXT,             -- JSON-serialised float array (nullable; NULL for jaccard-mode rows)
    posted       INTEGER NOT NULL DEFAULT 0
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
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
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


class SQLiteIngestionStore:
    """
    Thread-unsafe single-writer store (fine for the single-process pipeline).
    Each public method opens and closes its own connection to avoid
    long-lived connection state across pipeline stages.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Create all tables and indices if they don't already exist."""
        with self._connect() as connection:
            connection.executescript(_SCHEMA)
            connection.commit()
        self._migrate()

    def _migrate(self) -> None:
        """
        Non-destructive schema migrations for existing databases.

        Each migration is guarded by a column-existence check so it is safe
        to call on every startup — it is a no-op when the schema is current.

        Migration history:
          v1 → v2: ADD COLUMN centroid TEXT to stories
                   (existing rows keep NULL; backfill centroids separately
                   by re-running clustering with CLUSTERING_MODE=hybrid)
        """
        with self._connect() as connection:
            cols = {
                row[1]
                for row in connection.execute("PRAGMA table_info(stories)").fetchall()
            }
            if "centroid" not in cols:
                connection.execute(
                    "ALTER TABLE stories ADD COLUMN centroid TEXT"
                )
            if "posted" not in cols:
                connection.execute(
                    "ALTER TABLE stories ADD COLUMN posted INTEGER NOT NULL DEFAULT 0"
                )
            
            item_cols = {
                row[1]
                for row in connection.execute("PRAGMA table_info(items)").fetchall()
            }
            if "image_url" not in item_cols:
                connection.execute(
                    "ALTER TABLE items ADD COLUMN image_url TEXT"
                )
            connection.commit()

    # ------------------------------------------------------------------
    # Poll state
    # ------------------------------------------------------------------

    def get_poll_state(self) -> Dict[str, str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT feed_id, last_polled_at FROM source_poll_state"
            ).fetchall()
            return {str(row["feed_id"]): str(row["last_polled_at"]) for row in rows}

    def upsert_poll_state(self, poll_updates: Dict[str, str]) -> None:
        if not poll_updates:
            return
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO source_poll_state(feed_id, last_polled_at)
                VALUES (?, ?)
                ON CONFLICT(feed_id) DO UPDATE SET last_polled_at = excluded.last_polled_at
                """,
                list(poll_updates.items()),
            )
            connection.commit()

    # ------------------------------------------------------------------
    # Stories
    # ------------------------------------------------------------------

    def upsert_stories(self, stories: List[Dict]) -> None:
        """
        Persist story-cluster metadata rows.
        Called after clustering, before items are persisted.

        The `centroid` field (JSON-serialised float array or None) is written
        when present in the story dict. Rows from jaccard-mode clustering
        will have centroid=None and the column will be left as NULL.
        """
        if not stories:
            return
        now_iso = datetime.now(UTC).isoformat()
        rows = [
            (
                story["story_id"],
                story["source_count"],
                story["recency"],
                now_iso,
                story.get("centroid"),   # None → NULL for jaccard-mode rows
            )
            for story in stories
        ]
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO stories(story_id, source_count, recency, created_at, centroid)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(story_id) DO UPDATE SET
                    source_count = excluded.source_count,
                    recency      = excluded.recency,
                    centroid     = COALESCE(excluded.centroid, stories.centroid)
                """,
                rows,
            )
            connection.commit()

    # ------------------------------------------------------------------
    # Items
    # ------------------------------------------------------------------

    def upsert_items(self, items: Iterable[Dict]) -> int:
        """
        Persist normalised items. Returns the number of rows written.

        item["item_hash"] must already be set (by normalize_items).
        item["story_id"] may be None if clustering was skipped.
        """
        rows: List[tuple] = []
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
                    item.get("image_url"),
                )
            )

        if not rows:
            return 0

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO items(
                    item_hash, source_id, source_name, source_type, region, url,
                    title, raw_text, published_at, fetched_at, author, lang,
                    paywall, is_social, extraction_status, story_id,
                    has_cross_source_corroboration, image_url
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(item_hash) DO UPDATE SET
                    source_name                    = excluded.source_name,
                    source_type                    = excluded.source_type,
                    region                         = excluded.region,
                    title                          = excluded.title,
                    raw_text                       = excluded.raw_text,
                    published_at                   = excluded.published_at,
                    fetched_at                     = excluded.fetched_at,
                    author                         = excluded.author,
                    lang                           = excluded.lang,
                    paywall                        = excluded.paywall,
                    is_social                      = excluded.is_social,
                    extraction_status              = excluded.extraction_status,
                    story_id                       = excluded.story_id,
                    has_cross_source_corroboration = excluded.has_cross_source_corroboration,
                    image_url                      = excluded.image_url
                """,
                rows,
            )
            connection.commit()
            return len(rows)

    # ------------------------------------------------------------------
    # Review queue
    # ------------------------------------------------------------------

    def flag_for_review(self, items: Iterable[Dict]) -> None:
        """
        Insert items with extraction_status 'short' or 'failed' into the
        review_queue table so they can be inspected or re-processed later.
        """
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
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO review_queue(item_hash, reason, status, flagged_at)
                VALUES (?, ?, 'pending', ?)
                ON CONFLICT(item_hash) DO UPDATE SET
                    reason     = excluded.reason,
                    flagged_at = excluded.flagged_at
                """,
                rows,
            )
            connection.commit()

    # ------------------------------------------------------------------
    # Extraction stage helpers (Stage 1.5)
    # ------------------------------------------------------------------

    def get_pending_extraction_items(self, limit: int = 50) -> List[Dict]:
        """
        Return up to `limit` items from the review_queue that are still
        pending extraction. Excludes paywalled items (Jina can't bypass them)
        and items without a URL.
        """
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT i.item_hash, i.url, i.source_name, i.extraction_status
                FROM review_queue rq
                JOIN items i ON i.item_hash = rq.item_hash
                WHERE rq.status = 'pending'
                  AND i.paywall = 0
                  AND i.url IS NOT NULL
                  AND i.url != ''
                ORDER BY i.published_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def update_item_extraction(
        self, item_hash: str, raw_text: str, extraction_status: str, image_url: Optional[str] = None
    ) -> None:
        """
        Overwrite raw_text and extraction_status for a single item after
        successful Jina extraction.
        """
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE items
                SET raw_text = ?, extraction_status = ?, image_url = COALESCE(?, image_url)
                WHERE item_hash = ?
                """,
                (raw_text, extraction_status, image_url, item_hash),
            )
            connection.commit()

    def resolve_review_item(self, item_hash: str, status: str) -> None:
        """
        Set the review_queue status for one item.
        Expected values: 'resolved' (text now ok) | 'failed' (Jina couldn't help).
        """
        with self._connect() as connection:
            connection.execute(
                "UPDATE review_queue SET status = ? WHERE item_hash = ?",
                (status, item_hash),
            )
            connection.commit()

