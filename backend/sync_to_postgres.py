#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync_to_postgres.py — Incremental SQLite → Cloud SQL Postgres sync.

Usage:
  # Full sync (use after recluster.py — pushes everything, new story IDs)
  python sync_to_postgres.py --full

  # Incremental sync (use after a normal ingestion run — only new rows)
  python sync_to_postgres.py

Prerequisites:
  1. Cloud SQL Proxy must be running in another terminal:
       /opt/homebrew/bin/cloud-sql-proxy project-9ba21d45-1dfd-4108-b69:us-central1:weaware-pg --port=5433 &

  2. DB password available via Secret Manager (auto-fetched) or DB_PASS env var.

What it does:
  - Incremental mode: syncs items with fetched_at newer than the newest row in Postgres,
    plus any stories those items belong to.
  - Full mode: syncs ALL stories and items from SQLite.
  - In both modes: NEVER overwrites posted=true in Postgres. A story that's already been
    consumed by the teammate's automation stays marked as posted, even if reclustered locally.

Safety:
  - Idempotent: safe to run multiple times (all writes use ON CONFLICT DO NOTHING / DO UPDATE).
  - Stories table: ON CONFLICT updates source_count, recency, centroid but NOT posted.
  - Items table: ON CONFLICT updates story_id and has_cross_source_corroboration only
    (preserves raw_text and image_url if Postgres has a better version).
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Optional

import psycopg2
from psycopg2.extras import execute_batch

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SQLITE_PATH = "ingestion/store/items.db"
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 5433
DB_NAME = "weaware"
DB_USER = "weaware_user"
GCP_PROJECT = "project-9ba21d45-1dfd-4108-b69"
SECRET_NAME = "db-password"
BATCH_SIZE = 500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_db_password() -> str:
    """Read db-password from env var or Secret Manager."""
    pw = os.getenv("DB_PASS")
    if pw:
        return pw
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{GCP_PROJECT}/secrets/{SECRET_NAME}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"ERROR: Could not fetch db-password from Secret Manager: {e}")
        print("Set DB_PASS env var or ensure gcloud auth is configured.")
        sys.exit(1)


def connect_postgres(password: str):
    """Connect to Postgres via Cloud SQL Proxy (must be running on localhost:5432)."""
    try:
        return psycopg2.connect(
            host=PROXY_HOST,
            port=PROXY_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=password,
            connect_timeout=10,
        )
    except psycopg2.OperationalError as e:
        print(f"ERROR: Could not connect to Postgres at {PROXY_HOST}:{PROXY_PORT}")
        print("Is the Cloud SQL Proxy running?")
        print(f"  /opt/homebrew/bin/cloud-sql-proxy {GCP_PROJECT}:us-central1:weaware-pg &")
        print(f"Details: {e}")
        sys.exit(1)


def connect_sqlite() -> sqlite3.Connection:
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Core sync logic
# ---------------------------------------------------------------------------

def get_pg_newest_fetched_at(pg_conn) -> Optional[str]:
    """Return the MAX fetched_at in Postgres items table, or None if empty."""
    with pg_conn.cursor() as cur:
        cur.execute("SELECT MAX(fetched_at) FROM items")
        row = cur.fetchone()
        return row[0] if row and row[0] else None


def sync(full: bool = False) -> None:
    print(f"=== WeAwareNews Sync: {'FULL' if full else 'INCREMENTAL'} mode ===")
    print(f"SQLite: {SQLITE_PATH}")
    print(f"Postgres: {PROXY_HOST}:{PROXY_PORT}/{DB_NAME}")
    print()

    password = get_db_password()
    sq_conn = connect_sqlite()
    pg_conn = connect_postgres(password)

    # ------------------------------------------------------------------ #
    # Determine which items to sync
    # ------------------------------------------------------------------ #

    if full:
        cutoff = None
        print("Full mode: syncing ALL stories and items from SQLite.")
    else:
        cutoff = get_pg_newest_fetched_at(pg_conn)
        if cutoff:
            print(f"Incremental mode: syncing items fetched_at > {cutoff}")
        else:
            print("Postgres is empty — falling back to full sync.")
            cutoff = None

    sq_cur = sq_conn.cursor()

    # Fetch candidate items
    if cutoff:
        sq_cur.execute(
            "SELECT * FROM items WHERE fetched_at > ? ORDER BY fetched_at ASC",
            (cutoff,),
        )
    else:
        sq_cur.execute("SELECT * FROM items ORDER BY fetched_at ASC")

    item_rows = sq_cur.fetchall()

    if not item_rows:
        print("Nothing to sync — Postgres is already up to date.")
        pg_conn.close()
        sq_conn.close()
        return

    # Collect the story_ids these items belong to
    story_ids = {row["story_id"] for row in item_rows if row["story_id"]}

    # Fetch the corresponding story rows from SQLite
    if story_ids:
        placeholders = ",".join("?" * len(story_ids))
        sq_cur.execute(
            f"SELECT * FROM stories WHERE story_id IN ({placeholders})",
            tuple(story_ids),
        )
        story_rows = sq_cur.fetchall()
    else:
        story_rows = []

    print(f"Items to sync:   {len(item_rows)}")
    print(f"Stories to sync: {len(story_rows)}")
    print()

    # ------------------------------------------------------------------ #
    # Upsert stories — NEVER overwrite posted=true
    # ------------------------------------------------------------------ #

    story_data = [
        (
            row["story_id"],
            row["source_count"],
            row["recency"],
            row["created_at"],
            row["centroid"],       # may be None for jaccard-mode rows
        )
        for row in story_rows
    ]

    if story_data:
        with pg_conn.cursor() as cur:
            execute_batch(
                cur,
                """
                INSERT INTO stories(story_id, source_count, recency, created_at, centroid, posted)
                VALUES (%s, %s, %s, %s, %s, FALSE)
                ON CONFLICT(story_id) DO UPDATE SET
                    source_count = EXCLUDED.source_count,
                    recency      = EXCLUDED.recency,
                    centroid     = COALESCE(EXCLUDED.centroid, stories.centroid)
                    -- posted is intentionally NOT updated: never downgrade posted=true
                """,
                story_data,
                page_size=BATCH_SIZE,
            )
        pg_conn.commit()
        print(f"✓ Upserted {len(story_data)} stories (posted flags preserved).")

    # ------------------------------------------------------------------ #
    # Upsert items — only update clustering columns on conflict,
    # preserve raw_text/image_url in Postgres if it already has content
    # ------------------------------------------------------------------ #

    item_data = [
        (
            row["item_hash"],
            row["source_id"],
            row["source_name"],
            row["source_type"],
            row["region"],
            row["url"],
            row["title"],
            row["raw_text"],
            row["published_at"],
            row["fetched_at"],
            row["author"],
            row["lang"],
            int(row["paywall"] or 0),
            int(row["is_social"] or 0),
            row["extraction_status"] or "ok",
            row["story_id"],
            int(row["has_cross_source_corroboration"] or 0),
            row["image_url"],
        )
        for row in item_rows
    ]

    if item_data:
        with pg_conn.cursor() as cur:
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
                    story_id                       = EXCLUDED.story_id,
                    has_cross_source_corroboration = EXCLUDED.has_cross_source_corroboration,
                    -- Keep the better of SQLite or Postgres content:
                    -- prefer Postgres value if it's already populated, else take SQLite's
                    raw_text         = CASE
                                         WHEN items.raw_text IS NOT NULL AND LENGTH(items.raw_text) > LENGTH(COALESCE(EXCLUDED.raw_text,''))
                                         THEN items.raw_text
                                         ELSE EXCLUDED.raw_text
                                       END,
                    image_url        = COALESCE(items.image_url, EXCLUDED.image_url),
                    extraction_status = EXCLUDED.extraction_status,
                    title            = EXCLUDED.title
                """,
                item_data,
                page_size=BATCH_SIZE,
            )
        pg_conn.commit()
        print(f"✓ Upserted {len(item_data)} items.")

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #

    with pg_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM stories WHERE posted = false AND source_count >= 2")
        unposted = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM stories WHERE source_count >= 2")
        total_corroborated = cur.fetchone()[0]

    pg_conn.close()
    sq_conn.close()

    print()
    print("=== Postgres state after sync ===")
    print(f"  Total corroborated stories: {total_corroborated}")
    print(f"  Unposted (available to API): {unposted}")
    print()
    print("Sync complete.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync SQLite → Cloud SQL Postgres")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Sync ALL stories and items (use after recluster.py). "
             "Default is incremental (only rows newer than what Postgres has).",
    )
    args = parser.parse_args()
    sync(full=args.full)
