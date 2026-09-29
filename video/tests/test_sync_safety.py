"""
Behavioral tests for sync_to_postgres.py against real PostgreSQL.
Verifies that sync_to_postgres.py (--full and incremental):
1. NEVER overwrites or clears posted=true in PostgreSQL.
2. NEVER modifies, truncates, or touches the video_runs table.
"""

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
import psycopg2
import pytest

from backend import sync_to_postgres
from backend.ingestion.store.postgres_store import _SCHEMA as PROD_PG_SCHEMA

TEST_DB_URL = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:testpass@127.0.0.1:5434/weaware_test")


def _is_pg_reachable() -> bool:
    try:
        conn = psycopg2.connect(TEST_DB_URL, connect_timeout=1)
        conn.close()
        return True
    except Exception:
        return False


@pytest.fixture
def clean_pg_and_sqlite(tmp_path, monkeypatch):
    """
    Sets up real PostgreSQL with the production schema and migration,
    and a fresh SQLite database for sync_to_postgres.py.
    """
    # 1. Setup Postgres
    pg_conn = psycopg2.connect(TEST_DB_URL)
    with pg_conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS video_runs CASCADE;")
        cur.execute("DROP TABLE IF EXISTS review_queue CASCADE;")
        cur.execute("DROP TABLE IF EXISTS items CASCADE;")
        cur.execute("DROP TABLE IF EXISTS stories CASCADE;")
        cur.execute("DROP TABLE IF EXISTS source_poll_state CASCADE;")
        
        # Load official production schema
        cur.execute(PROD_PG_SCHEMA)
        
        # Run video_runs migration (with lock_timeout)
        migration_sql = Path("video/migrations/001_create_video_runs.sql").read_text()
        cur.execute(migration_sql)
    pg_conn.commit()
    pg_conn.close()

    # 2. Setup SQLite
    sqlite_db_path = tmp_path / "test_items.db"
    sq_conn = sqlite3.connect(sqlite_db_path)
    sq_cur = sq_conn.cursor()
    sq_cur.execute("""
    CREATE TABLE stories (
        story_id     TEXT PRIMARY KEY,
        source_count INTEGER NOT NULL,
        recency      TEXT NOT NULL,
        created_at   TEXT NOT NULL,
        centroid     TEXT,
        posted       INTEGER NOT NULL DEFAULT 0
    );
    """)
    sq_cur.execute("""
    CREATE TABLE items (
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
        story_id                    TEXT,
        has_cross_source_corroboration INTEGER NOT NULL DEFAULT 0,
        image_url                   TEXT
    );
    """)
    sq_conn.commit()
    sq_conn.close()

    # 3. Monkeypatch sync_to_postgres configuration
    monkeypatch.setattr(sync_to_postgres, "SQLITE_PATH", str(sqlite_db_path))
    monkeypatch.setattr(sync_to_postgres, "PROXY_HOST", "127.0.0.1")
    monkeypatch.setattr(sync_to_postgres, "PROXY_PORT", 5434)
    monkeypatch.setattr(sync_to_postgres, "DB_NAME", "weaware_test")
    monkeypatch.setattr(sync_to_postgres, "DB_USER", "postgres")
    monkeypatch.setattr(sync_to_postgres, "get_db_password", lambda: "testpass")

    return str(sqlite_db_path)


@pytest.mark.skipif(
    not _is_pg_reachable(),
    reason="Local PostgreSQL not reachable at TEST_DB_URL (port 5434). Run docker container to test."
)
def test_sync_to_postgres_preserves_posted_and_video_runs_behavioral(clean_pg_and_sqlite):
    """
    BEHAVIORAL TEST:
    1. Seed Postgres with a story where posted=true and an active video_runs row.
    2. Seed SQLite with updated data for that story where posted=0.
    3. Run sync_to_postgres.sync(full=False) (incremental sync).
    4. Assert story in Postgres STILL has posted=true and video_runs is intact.
    5. Run sync_to_postgres.sync(full=True) (full sync).
    6. Assert story in Postgres STILL has posted=true and video_runs is intact.
    """
    story_id = f"posted-story-{uuid.uuid4()}"
    run_id = str(uuid.uuid4())
    item_hash_1 = f"hash-{uuid.uuid4()}"

    # 1. Seed Postgres with posted=true and an active video_runs record
    pg_conn = psycopg2.connect(TEST_DB_URL)
    with pg_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO stories (story_id, source_count, recency, created_at, posted)
            VALUES (%s, 2, '2026-09-29T10:00:00Z', '2026-09-29T10:00:00Z', TRUE)
            """,
            (story_id,),
        )
        cur.execute(
            """
            INSERT INTO items (
                item_hash, source_id, source_name, source_type, region,
                url, title, raw_text, published_at, fetched_at, story_id
            )
            VALUES (%s, 'src1', 'Reuters', 'rss', 'us', 'https://reuters.com/1', 'Headline 1', 'Content 1', '2026-09-29T09:00:00Z', '2026-09-29T10:00:00Z', %s)
            """,
            (item_hash_1, story_id),
        )
        cur.execute(
            """
            INSERT INTO video_runs (
                run_id, story_id, status, claim_mode, claimed_at, expires_at,
                heartbeat_at, headline_snapshot, story_text_snapshot, source_urls
            )
            VALUES (
                %s, %s, 'generating_video', 'separate', NOW(), NOW() + INTERVAL '30 minutes',
                NOW(), 'Snapshot Headline', 'Snapshot Text', ARRAY['https://reuters.com/1']
            )
            """,
            (run_id, story_id),
        )
    pg_conn.commit()
    pg_conn.close()

    # 2. Seed SQLite with the same story (where posted is FALSE / 0) and a newer item
    item_hash_2 = f"hash-{uuid.uuid4()}"
    sq_conn = sqlite3.connect(clean_pg_and_sqlite)
    sq_cur = sq_conn.cursor()
    sq_cur.execute(
        """
        INSERT INTO stories (story_id, source_count, recency, created_at, posted)
        VALUES (?, 3, '2026-09-29T11:00:00Z', '2026-09-29T10:00:00Z', 0)
        """,
        (story_id,),
    )
    sq_cur.execute(
        """
        INSERT INTO items (
            item_hash, source_id, source_name, source_type, region,
            url, title, raw_text, published_at, fetched_at, story_id
        )
        VALUES (?, 'src2', 'BBC', 'rss', 'uk', 'https://bbc.com/2', 'Headline 2', 'Content 2', '2026-09-29T10:30:00Z', '2026-09-29T11:00:00Z', ?)
        """,
        (item_hash_2, story_id),
    )
    sq_conn.commit()
    sq_conn.close()

    # 3. Run incremental sync
    sync_to_postgres.sync(full=False)

    # 4. Verify in Postgres: posted=true MUST remain True, video_runs MUST be intact
    pg_conn = psycopg2.connect(TEST_DB_URL)
    with pg_conn.cursor() as cur:
        cur.execute("SELECT posted, source_count FROM stories WHERE story_id = %s", (story_id,))
        row = cur.fetchone()
        assert row is not None
        assert row[0] is True, "INCREMENTAL sync violated invariant: posted was reset from TRUE to FALSE!"
        assert row[1] == 3, "INCREMENTAL sync should update source_count"

        cur.execute("SELECT status, headline_snapshot FROM video_runs WHERE run_id = %s", (run_id,))
        v_row = cur.fetchone()
        assert v_row is not None
        assert v_row[0] == "generating_video"
        assert v_row[1] == "Snapshot Headline"
    pg_conn.close()

    # 5. Run full sync
    sync_to_postgres.sync(full=True)

    # 6. Verify in Postgres: posted=true MUST STILL remain True, video_runs MUST STILL be intact
    pg_conn = psycopg2.connect(TEST_DB_URL)
    with pg_conn.cursor() as cur:
        cur.execute("SELECT posted, source_count FROM stories WHERE story_id = %s", (story_id,))
        row = cur.fetchone()
        assert row is not None
        assert row[0] is True, "FULL sync violated invariant: posted was reset from TRUE to FALSE!"

        cur.execute("SELECT status, headline_snapshot FROM video_runs WHERE run_id = %s", (run_id,))
        v_row = cur.fetchone()
        assert v_row is not None
        assert v_row[0] == "generating_video"
        assert v_row[1] == "Snapshot Headline"
    pg_conn.close()
