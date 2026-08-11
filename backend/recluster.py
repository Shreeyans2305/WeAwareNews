"""
Recluster all items in the local SQLite database using current calibrated settings.

What this does:
  1. Loads all items from items.db (preserving raw_text, image_url, extraction_status)
  2. Runs cluster_items() in hybrid mode (wikineural + IDF-weighted entity blocking)
  3. Clears the stories table and item story_id/corroboration columns
  4. Re-writes clean story assignments — does NOT touch raw_text, image_url, or
     extraction_status, which are preserved in place

Safe to re-run: won't delete any article content.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

from ingestion.store.sqlite_store import SQLiteIngestionStore
from ingestion.cluster import cluster_items
from ingestion.utils import UTC


def main():
    db_path = Path("ingestion/store/items.db")
    store = SQLiteIngestionStore(db_path)

    # ------------------------------------------------------------------ #
    # 1. Load all items — use direct connection to get full Row objects
    # ------------------------------------------------------------------ #
    with store._connect() as conn:
        rows = conn.execute("SELECT * FROM items ORDER BY published_at ASC").fetchall()
        items = [dict(r) for r in rows]

    print(f"Loaded {len(items)} items. Re-clustering with hybrid mode (wikineural)…")

    # ------------------------------------------------------------------ #
    # 2. Run clustering
    # ------------------------------------------------------------------ #
    stories, item_to_story = cluster_items(items, mode="hybrid")

    corroborated_count = sum(1 for s in stories if s["source_count"] >= 2)
    print(f"Clustered → {len(stories)} stories, {corroborated_count} corroborated (source_count ≥ 2)")

    # ------------------------------------------------------------------ #
    # 3. Re-apply story assignments to item dicts
    # ------------------------------------------------------------------ #
    for item in items:
        key = str(item["item_hash"])
        story_id = item_to_story.get(key)
        item["story_id"] = story_id
        story = next((s for s in stories if s["story_id"] == story_id), None)
        item["has_cross_source_corroboration"] = int(bool(story and story["source_count"] > 1))

    # ------------------------------------------------------------------ #
    # 4. Wipe ONLY the stories table and the story FK columns on items.
    #    Preserve all article content (raw_text, image_url, extraction_status).
    # ------------------------------------------------------------------ #
    now_iso = datetime.now(UTC).isoformat()
    story_rows = [
        (
            s["story_id"],
            s["source_count"],
            s["recency"],
            now_iso,
            s.get("centroid"),
        )
        for s in stories
    ]
    item_assignment_rows = [
        (item.get("story_id"), item.get("has_cross_source_corroboration", 0), item["item_hash"])
        for item in items
    ]

    with store._connect() as conn:
        conn.execute("DELETE FROM stories")

        conn.executemany(
            """
            INSERT INTO stories(story_id, source_count, recency, created_at, centroid)
            VALUES (?, ?, ?, ?, ?)
            """,
            story_rows,
        )

        # Update item → story assignment without touching any content columns
        conn.executemany(
            """
            UPDATE items
            SET story_id = ?,
                has_cross_source_corroboration = ?
            WHERE item_hash = ?
            """,
            item_assignment_rows,
        )
        conn.commit()

    print(f"Done. {corroborated_count} corroborated stories written to items.db.")
    print("Content columns (raw_text, image_url, extraction_status) were NOT modified.")


if __name__ == "__main__":
    main()
