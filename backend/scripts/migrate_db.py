import os
import sqlite3
from google.cloud.sql.connector import Connector, IPTypes
from psycopg2.extras import execute_batch
import pg8000

def migrate():
    print("Starting migration...")
    
    # 1. Connect to both DBs
    sqlite_conn = sqlite3.connect("ingestion/store/items.db")
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cur = sqlite_conn.cursor()
    
    # Use connector
    connector = Connector()
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    instance_connection_name = f"{project_id}:us-central1:weaware-pg"
    db_user = "weaware_user"
    db_name = "weaware"
    
    # Load from secret manager natively if DB_PASS is missing
    if os.getenv("DB_PASS"):
        db_pass = os.getenv("DB_PASS")
    else:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{project_id}/secrets/db-password/versions/latest"
        response = client.access_secret_version(request={"name": name})
        db_pass = response.payload.data.decode("UTF-8")
    
    pg_conn = connector.connect(
        instance_connection_name,
        "pg8000",
        user=db_user,
        password=db_pass,
        db=db_name,
        ip_type=IPTypes.PUBLIC,
    )
    pg_cur = pg_conn.cursor()

    # Initialise schema using postgres_store logic (run schema queries)
    from ingestion.store.postgres_store import _SCHEMA
    pg_cur.execute(_SCHEMA)
    pg_conn.commit()

    # 2. Migrate source_poll_state
    sqlite_cur.execute("SELECT * FROM source_poll_state")
    poll_rows = sqlite_cur.fetchall()
    if poll_rows:
        pg_cur.executemany("""
            INSERT INTO source_poll_state (feed_id, last_polled_at) 
            VALUES (%s, %s) ON CONFLICT DO NOTHING
        """, [(r["feed_id"], r["last_polled_at"]) for r in poll_rows])
        print(f"Migrated {len(poll_rows)} source_poll_state rows")

    # 3. Migrate stories
    sqlite_cur.execute("SELECT * FROM stories")
    story_rows = sqlite_cur.fetchall()
    if story_rows:
        pg_cur.executemany("""
            INSERT INTO stories (story_id, source_count, recency, created_at, centroid, posted) 
            VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING
        """, [(r["story_id"], r["source_count"], r["recency"], r["created_at"], r["centroid"], bool(r["posted"])) for r in story_rows])
        print(f"Migrated {len(story_rows)} stories")

    # 4. Migrate items
    sqlite_cur.execute("SELECT * FROM items")
    item_rows = sqlite_cur.fetchall()
    if item_rows:
        pg_cur.executemany("""
            INSERT INTO items (
                item_hash, source_id, source_name, source_type, region, url, title, raw_text, 
                published_at, fetched_at, author, lang, paywall, is_social, extraction_status, 
                story_id, has_cross_source_corroboration, image_url
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING
        """, [(
            r["item_hash"], r["source_id"], r["source_name"], r["source_type"], r["region"], r["url"],
            r["title"], r["raw_text"], r["published_at"], r["fetched_at"], r["author"], r["lang"],
            int(r["paywall"]), int(r["is_social"]), r["extraction_status"], r["story_id"], 
            int(r["has_cross_source_corroboration"]), r["image_url"] if "image_url" in r.keys() else None
        ) for r in item_rows])
        print(f"Migrated {len(item_rows)} items")

    # 5. Migrate review_queue
    sqlite_cur.execute("SELECT * FROM review_queue")
    review_rows = sqlite_cur.fetchall()
    if review_rows:
        pg_cur.executemany("""
            INSERT INTO review_queue (item_hash, reason, status, flagged_at) 
            VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING
        """, [(r["item_hash"], r["reason"], r["status"], r["flagged_at"]) for r in review_rows])
        print(f"Migrated {len(review_rows)} review_queue rows")
    
    pg_conn.commit()
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
