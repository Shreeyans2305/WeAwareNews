import sqlite3
import re
import numpy as np
from itertools import combinations
from sentence_transformers import SentenceTransformer

EMBED_MODEL_NAME = "intfloat/multilingual-e5-base"
EMBED_PREFIX = "query: "
EMBED_SENTENCE_LIMIT = 2
MIN_SIMILARITY_THRESHOLD = 0.82

def _make_embed_input(title: str, raw_text: str) -> str:
    title = title or ""
    raw_text = raw_text or ""
    sentences = re.split(r"(?<=[.!?])\s+", raw_text.strip())
    body_snippet = " ".join(sentences[:EMBED_SENTENCE_LIMIT])
    text = f"{title}. {body_snippet}".strip()
    return f"{EMBED_PREFIX}{text}"

def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))

def split_clusters():
    print("Loading embedding model...")
    embedder = SentenceTransformer(EMBED_MODEL_NAME)
    
    conn = sqlite3.connect("ingestion/store/items.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Get all corroborated stories
    cur.execute("SELECT story_id FROM stories WHERE source_count >= 2")
    stories = cur.fetchall()
    
    print(f"Checking {len(stories)} corroborated stories for false merges...")
    split_count = 0
    
    for row in stories:
        story_id = row["story_id"]
        cur.execute("SELECT item_hash, title, raw_text FROM items WHERE story_id = ?", (story_id,))
        items = cur.fetchall()
        
        if len(items) < 2:
            continue
            
        # Compute embeddings for all items in the cluster
        embeddings = []
        for item in items:
            embed_input = _make_embed_input(item["title"], item["raw_text"])
            vec = embedder.encode([embed_input], normalize_embeddings=True, show_progress_bar=False)[0]
            embeddings.append(vec)
            
        # Check all pairwise similarities
        is_false_merge = False
        for (i, vec_a), (j, vec_b) in combinations(enumerate(embeddings), 2):
            sim = _cosine(vec_a, vec_b)
            if sim < MIN_SIMILARITY_THRESHOLD:
                is_false_merge = True
                print(f"False merge detected (sim: {sim:.3f}):")
                print(f"  A: {items[i]['title']}")
                print(f"  B: {items[j]['title']}")
                break
                
        if is_false_merge:
            cur.execute("UPDATE items SET story_id = NULL, has_cross_source_corroboration = 0 WHERE story_id = ?", (story_id,))
            split_count += 1
            
    conn.commit()
    conn.close()
    
    print(f"Split {split_count} false clusters based on semantic similarity.")

if __name__ == "__main__":
    split_clusters()
