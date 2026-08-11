import sqlite3
import psycopg2
import os

PROXY_HOST = "127.0.0.1"
PROXY_PORT = 5433
DB_NAME = "weaware"
DB_USER = "weaware_user"
GCP_PROJECT = "project-9ba21d45-1dfd-4108-b69"
SECRET_NAME = "db-password"
SQLITE_PATH = "ingestion/store/items.db"

def get_db_password():
    pw = os.getenv("DB_PASS")
    if pw:
        return pw
    from google.cloud import secretmanager
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{GCP_PROJECT}/secrets/{SECRET_NAME}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

def check_status():
    password = get_db_password()
    pg_conn = psycopg2.connect(host=PROXY_HOST, port=PROXY_PORT, dbname=DB_NAME, user=DB_USER, password=password, connect_timeout=10)
    with pg_conn.cursor() as cur:
        cur.execute("SELECT MAX(fetched_at) FROM items")
        pg_cutoff = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM items")
        pg_item_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM stories")
        pg_story_count = cur.fetchone()[0]
    
    sq_conn = sqlite3.connect(SQLITE_PATH)
    sq_cur = sq_conn.cursor()
    sq_cur.execute("SELECT MAX(fetched_at) FROM items")
    sq_cutoff = sq_cur.fetchone()[0]
    sq_cur.execute("SELECT COUNT(*) FROM items")
    sq_item_count = sq_cur.fetchone()[0]
    sq_cur.execute("SELECT COUNT(*) FROM stories")
    sq_story_count = sq_cur.fetchone()[0]

    print(f"Cloud DB: {pg_item_count} items, {pg_story_count} stories, latest fetch: {pg_cutoff}")
    print(f"Local DB: {sq_item_count} items, {sq_story_count} stories, latest fetch: {sq_cutoff}")
    
    if pg_cutoff:
        sq_cur.execute("SELECT COUNT(*) FROM items WHERE fetched_at > ?", (pg_cutoff,))
        pending_items = sq_cur.fetchone()[0]
    else:
        pending_items = sq_item_count
        
    print(f"Pending items to sync: {pending_items}")

if __name__ == '__main__':
    check_status()
