import sqlite3

def dump():
    conn = sqlite3.connect("ingestion/store/items.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT story_id, COUNT(DISTINCT source_name) as sc
        FROM items
        WHERE story_id IS NOT NULL
        GROUP BY story_id
        HAVING sc >= 2
        ORDER BY sc DESC
    """)
    stories = cur.fetchall()
    
    for story_id, sc in stories:
        print(f"\n[{story_id}]")
        cur.execute("SELECT item_hash, source_name, title FROM items WHERE story_id = ?", (story_id,))
        for item_hash, source, title in cur.fetchall():
            print(f"  {item_hash[:8]} | [{source}] {title}")
    conn.close()

if __name__ == "__main__":
    dump()
