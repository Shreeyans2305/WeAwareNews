import sqlite3
import json
import numpy as np
from itertools import combinations
from sentence_transformers import SentenceTransformer

def cosine_sim(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def main():
    print("Loading model...")
    model = SentenceTransformer('intfloat/multilingual-e5-base')
    
    conn = sqlite3.connect('ingestion/store/items.db')
    conn.row_factory = sqlite3.Row
    
    # Get the 91 corroborated stories from the recent hybrid run
    # (recency should sort them, latest 91 with source_count >= 2)
    # Actually, we can just grab all stories with source_count >= 2 where centroid IS NOT NULL
    # and maybe filter to the latest 100 to be safe.
    stories_rows = conn.execute("""
        SELECT story_id, source_count 
        FROM stories 
        WHERE source_count >= 2 AND centroid IS NOT NULL
        ORDER BY recency DESC 
        LIMIT 91
    """).fetchall()
    
    contaminated_count_06 = 0
    total_stories = len(stories_rows)
    
    pair_sims = []
    
    # Also track the specific good/bad merges mentioned for step 3
    # We will identify them by the story_id or titles.
    good_pairs = []
    bad_pairs = []
    
    print(f"Analyzing {total_stories} stories...")
    
    for row in stories_rows:
        story_id = row['story_id']
        items = conn.execute("SELECT item_hash, title, raw_text FROM items WHERE story_id = ?", (story_id,)).fetchall()
        
        # Prepare inputs for embedding (prefix with "passage: " as per cluster.py logic)
        texts = []
        for i in items:
            # Reconstruct the string that was embedded in cluster.py
            raw = i['raw_text'] or ""
            text_to_embed = f"passage: {i['title']} {raw[:500]}"
            texts.append(text_to_embed)
            
        embeddings = model.encode(texts, normalize_embeddings=True)
        
        has_below_06 = False
        
        for (idx_a, emb_a), (idx_b, emb_b) in combinations(enumerate(embeddings), 2):
            sim = cosine_sim(emb_a, emb_b)
            pair_sims.append({
                'story_id': story_id,
                'title_a': items[idx_a]['title'],
                'title_b': items[idx_b]['title'],
                'sim': sim
            })
            
            if sim < 0.6:
                has_below_06 = True
                
        if has_below_06:
            contaminated_count_06 += 1

    print(f"Stories with at least one pair < 0.6: {contaminated_count_06} out of {total_stories}")
    
    # Let's inspect some of the specific pairs to find the threshold for Step 3
    print("\n--- Pairwise Similarity for Specific Mentions ---")
    for p in pair_sims:
        t_a, t_b = p['title_a'].lower(), p['title_b'].lower()
        
        # Blanche nomination (Good)
        if 'blanche' in t_a and 'blanche' in t_b:
            print(f"[GOOD-Blanche] {p['sim']:.3f} | {p['title_a'][:40]} <-> {p['title_b'][:40]}")
            good_pairs.append(p['sim'])
            
        # Durov / Telegram (Good)
        if ('durov' in t_a or 'telegram' in t_a) and ('durov' in t_b or 'telegram' in t_b):
            print(f"[GOOD-Durov]   {p['sim']:.3f} | {p['title_a'][:40]} <-> {p['title_b'][:40]}")
            good_pairs.append(p['sim'])

        # Trump/Blanche merged with Carroll/ICE (Bad)
        if ('blanche' in t_a and ('carroll' in t_b or 'ice' in t_b or 'maga' in t_b)) or \
           ('blanche' in t_b and ('carroll' in t_a or 'ice' in t_a or 'maga' in t_a)):
            print(f"[BAD-Trump]    {p['sim']:.3f} | {p['title_a'][:40]} <-> {p['title_b'][:40]}")
            bad_pairs.append(p['sim'])
            
        # Durov merged with DJ / France expels / Ukraine (Bad)
        if ('durov' in t_a and ('dj' in t_b or 'expels' in t_b or 'ukraine' in t_b)) or \
           ('durov' in t_b and ('dj' in t_a or 'expels' in t_a or 'ukraine' in t_a)):
            print(f"[BAD-Durov]    {p['sim']:.3f} | {p['title_a'][:40]} <-> {p['title_b'][:40]}")
            bad_pairs.append(p['sim'])
            
        # Iran strikes merged with Norwegian murder / Trident (Bad)
        if ('iran' in t_a and ('norwegian' in t_b or 'trident' in t_b)) or \
           ('iran' in t_b and ('norwegian' in t_a or 'trident' in t_a)):
            print(f"[BAD-Iran]     {p['sim']:.3f} | {p['title_a'][:40]} <-> {p['title_b'][:40]}")
            bad_pairs.append(p['sim'])
            
        # Hindu articles (Karnataka road / Cauvery / Lift) (Bad)
        if ('road' in t_a and 'cauvery' in t_b) or ('cauvery' in t_a and 'road' in t_b):
            print(f"[BAD-Hindu]    {p['sim']:.3f} | {p['title_a'][:40]} <-> {p['title_b'][:40]}")
            bad_pairs.append(p['sim'])

    print("\n--- Step 3 Analysis ---")
    if good_pairs:
        print(f"Min Good Sim: {min(good_pairs):.3f}")
        print(f"Max Good Sim: {max(good_pairs):.3f}")
    if bad_pairs:
        print(f"Min Bad Sim:  {min(bad_pairs):.3f}")
        print(f"Max Bad Sim:  {max(bad_pairs):.3f}")
        
    print("\nPairwise sim quantiles (all pairs):")
    all_sims = [p['sim'] for p in pair_sims]
    for q in [0, 10, 25, 50, 75, 90, 100]:
        print(f"{q}th percentile: {np.percentile(all_sims, q):.3f}")

if __name__ == "__main__":
    main()
