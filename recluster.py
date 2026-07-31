import sqlite3
from pathlib import Path
from ingestion.store.sqlite_store import SQLiteIngestionStore
from ingestion.cluster import cluster_items

def main():
    db_path = Path("ingestion/store/items.db")
    store = SQLiteIngestionStore(db_path)
    
    with store._connect() as conn:
        # Fetch all items from the DB as dicts
        rows = conn.execute("SELECT * FROM items ORDER BY published_at ASC").fetchall()
        items = [dict(r) for r in rows]
        
    print(f"Loaded {len(items)} items from database. Re-clustering with hybrid mode...")
    
    # Run clustering
    stories, item_to_story = cluster_items(items, mode="hybrid")
    
    # Re-apply story IDs and corroboration flag
    for item in items:
        story_id = item_to_story.get(str(item["item_hash"]))
        item["story_id"] = story_id
        story = next((s for s in stories if s["story_id"] == story_id), None)
        item["has_cross_source_corroboration"] = bool(story and story["source_count"] > 1)
        
    print(f"Generated {len(stories)} stories. Upserting to database...")
    
    with store._connect() as conn:
        # Clear existing stories completely to avoid orphaned old stories
        conn.execute("DELETE FROM stories")
        conn.execute("DELETE FROM items")
        conn.commit()
    
    # Re-insert everything
    store.upsert_stories(stories)
    store.upsert_items(items)
    
    multi_source_stories = sum(1 for s in stories if s["source_count"] > 1)
    print(f"Done! {multi_source_stories} corroborated stories.")

if __name__ == "__main__":
    main()
