import sqlite3

def check_clusters():
    conn = sqlite3.connect("ingestion/store/items.db")
    cur = conn.cursor()
    
    # Get corroborated stories
    cur.execute("""
        SELECT story_id, COUNT(DISTINCT source_name) as sc, MAX(fetched_at) as recency
        FROM items
        WHERE story_id IS NOT NULL
        GROUP BY story_id
        HAVING sc >= 2
        ORDER BY recency DESC
        LIMIT 20
    """)
    stories = cur.fetchall()
    
    print(f"Top {len(stories)} recently corroborated stories (out of all corroborated):")
    for story_id, sc, recency in stories:
        print(f"\n--- Story: {story_id[:8]}... (Sources: {sc}) ---")
        cur.execute("SELECT source_name, title FROM items WHERE story_id = ?", (story_id,))
        for source, title in cur.fetchall():
            print(f"[{source}] {title}")
            
    conn.close()

if __name__ == "__main__":
    check_clusters()
