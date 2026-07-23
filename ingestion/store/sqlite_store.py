import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List

from ingestion.normalize import stable_item_hash


class SQLiteIngestionStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS items (
                    item_hash TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    region TEXT NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT,
                    raw_text TEXT,
                    published_at TEXT,
                    fetched_at TEXT NOT NULL,
                    author TEXT,
                    lang TEXT,
                    paywall INTEGER NOT NULL,
                    is_social INTEGER NOT NULL,
                    has_cross_source_corroboration INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS source_poll_state (
                    feed_id TEXT PRIMARY KEY,
                    last_polled_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def get_poll_state(self) -> Dict[str, str]:
        with self._connect() as connection:
            rows = connection.execute("SELECT feed_id, last_polled_at FROM source_poll_state").fetchall()
            return {str(row["feed_id"]): str(row["last_polled_at"]) for row in rows}

    def upsert_poll_state(self, poll_updates: Dict[str, str]) -> None:
        if not poll_updates:
            return
        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO source_poll_state(feed_id, last_polled_at)
                VALUES (?, ?)
                ON CONFLICT(feed_id) DO UPDATE SET last_polled_at=excluded.last_polled_at
                """,
                list(poll_updates.items()),
            )
            connection.commit()

    def upsert_items(self, items: Iterable[Dict[str, object]]) -> int:
        rows: List[tuple[object, ...]] = []
        for item in items:
            item_hash = stable_item_hash(str(item["source_id"]), str(item["url"]))
            rows.append(
                (
                    item_hash,
                    item["source_id"],
                    item["source_name"],
                    item["source_type"],
                    item["region"],
                    item["url"],
                    item["title"],
                    item["raw_text"],
                    item["published_at"],
                    item["fetched_at"],
                    item["author"],
                    item["lang"],
                    int(bool(item["paywall"])),
                    int(bool(item["is_social"])),
                    int(bool(item["has_cross_source_corroboration"])),
                )
            )

        if not rows:
            return 0

        with self._connect() as connection:
            connection.executemany(
                """
                INSERT INTO items(
                    item_hash, source_id, source_name, source_type, region, url, title, raw_text,
                    published_at, fetched_at, author, lang, paywall, is_social, has_cross_source_corroboration
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(item_hash) DO UPDATE SET
                    source_name=excluded.source_name,
                    source_type=excluded.source_type,
                    region=excluded.region,
                    title=excluded.title,
                    raw_text=excluded.raw_text,
                    published_at=excluded.published_at,
                    fetched_at=excluded.fetched_at,
                    author=excluded.author,
                    lang=excluded.lang,
                    paywall=excluded.paywall,
                    is_social=excluded.is_social,
                    has_cross_source_corroboration=excluded.has_cross_source_corroboration
                """,
                rows,
            )
            connection.commit()
            return len(rows)
