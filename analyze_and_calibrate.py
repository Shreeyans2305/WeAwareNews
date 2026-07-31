import sqlite3
import math
from pathlib import Path
from collections import defaultdict
import re
from sentence_transformers import SentenceTransformer

def cosine_sim(a, b):
    import numpy as np
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

def _get_nlp():
    import spacy
    return spacy.load("xx_ent_wiki_sm")

def _extract_entities_with_labels(text: str, nlp):
    if not text.strip():
        return {}
    doc = nlp(text)
    # Return dict of text -> label
    return {ent.text.lower().strip(): ent.label_ for ent in doc.ents if ent.text.strip()}

def _make_ner_input(title: str, raw_text: str, sentence_limit: int) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", (raw_text or "").strip())
    body_snippet = " ".join(sentences[:sentence_limit])
    return f"{title}. {body_snippet}".strip()

def main():
    db_path = Path("ingestion/store/items.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    
    rows = conn.execute("SELECT item_hash, title, raw_text FROM items").fetchall()
    items = [dict(r) for r in rows]
    N = len(items)
    
    nlp = _get_nlp()
    
    item_entities = {}
    df = defaultdict(int)
    entity_labels = {}
    
    for item in items:
        ner_input = _make_ner_input(item['title'] or "", item['raw_text'] or "", 2)
        ents = _extract_entities_with_labels(ner_input, nlp)
        item_entities[item['item_hash']] = ents
        for e, label in ents.items():
            df[e] += 1
            # Keep the most recent label, or we could collect all
            entity_labels[e] = label
            
    # Task 1: Investigate Unexplained Merge
    print("--- 1. INVESTIGATE THE UNEXPLAINED MERGE ---")
    airfare_item = next(i for i in items if "Higher Airfares Loom" in i['title'])
    copper_item = next(i for i in items if "Global surge in copper theft" in i['title'])
    
    ents_a = item_entities[airfare_item['item_hash']]
    ents_b = item_entities[copper_item['item_hash']]
    print(f"Airfare entities: {ents_a}")
    print(f"Copper entities: {ents_b}")
    
    shared = set(ents_a.keys()) & set(ents_b.keys())
    print(f"Shared entities: {shared}")
    
    if not ents_a and not ents_b:
        path = "Zero-entity fallback (strict threshold)"
    elif not ents_a or not ents_b:
        path = "Asymmetric zero-entity fallback (default threshold)"
    elif shared:
        path = "Shared-entity blocking"
    else:
        path = "NO MATCH (should not have been a candidate)"
    print(f"Path taken: {path}")
    
    embedder = SentenceTransformer('intfloat/multilingual-e5-base')
    def get_vec(item):
        raw = item['raw_text'] or ""
        sentences = re.split(r"(?<=[.!?])\s+", raw.strip())
        body_snippet = " ".join(sentences[:2])
        text = f"query: {item['title']}. {body_snippet}".strip()
        vec = embedder.encode([text], normalize_embeddings=True)[0]
        return vec
        
    vec_a = get_vec(airfare_item)
    vec_b = get_vec(copper_item)
    sim = cosine_sim(vec_a, vec_b)
    print(f"Cosine similarity: {sim:.3f}")
    
    # Task 2 & 3: Calibration for types and weak entity stacking
    LOC_MULTIPLIER = 0.3
    
    def get_weight(e):
        base_weight = math.log(N / df[e])
        label = entity_labels.get(e)
        if label == "LOC":
            return base_weight * LOC_MULTIPLIER
        return base_weight
        
    def match_score(ents_a_dict, ents_b_dict):
        shared_keys = set(ents_a_dict.keys()) & set(ents_b_dict.keys())
        if not shared_keys:
            return 0.0, 0.0
        score = sum(get_weight(e) for e in shared_keys)
        max_single = max(get_weight(e) for e in shared_keys)
        return score, max_single
        
    print("\n--- 4. RE-VALIDATE ON ALL KNOWN EXAMPLES ---")
    pairs = [
        ("GOOD", "Blanche", "With Blanche Nomination at Stake", "Senate committee delays vote on Todd Blanche"),
        ("GOOD", "Durov", "Why is the founder of Telegram on Russia", "Who is Pavel Durov? Inside the Telegram"),
        ("GOOD", "Morales", "ordena prisão de Evo Morales", "ordena la detención del expresidente Evo Morales"),
        ("BAD", "Trump/Carroll", "With Blanche Nomination at Stake", "Trump appeals $83.3m E Jean Carroll"),
        ("BAD", "Trump Media/Iran", "probe Trump Media's paid service", "Trump threatens to hit Iran ‘hard’"),
        ("BAD", "China", "China’s Coal Demand Gets Boost", "China’s Launch of Advanced Hypersonic Missile"),
        ("BAD", "OpenAI/ChatGPT", "OpenAI’s alarming escape", "ChatGPT, Roblox to Fall Under Strictest EU Rules"),
        ("BAD", "Delhi HPV/Shooting", "Delhi HC declines to stay HPV vaccination drive", "Woman Shot Dead By Unidentified Gunmen In Delhi"),
        ("BAD", "Trump-China Stack", "Trump widens China tech war", "Trump blasts Fauci, says he ‘always tried to protect China’")
    ]
    
    for type_val, name, title_a, title_b in pairs:
        item_a = next((i for i in items if title_a.lower() in (i['title'] or "").lower()), None)
        item_b = next((i for i in items if title_b.lower() in (i['title'] or "").lower()), None)
        
        if not item_a or not item_b:
            print(f"[{type_val}-{name}] Missing items!")
            continue
            
        ents_a = item_entities[item_a['item_hash']]
        ents_b = item_entities[item_b['item_hash']]
        shared_keys = set(ents_a.keys()) & set(ents_b.keys())
        
        score, max_single = match_score(ents_a, ents_b)
        
        details = []
        for e in shared_keys:
            label = entity_labels.get(e)
            w = get_weight(e)
            mult = LOC_MULTIPLIER if label == "LOC" else 1.0
            details.append(f"{e} ({label}, w={w:.2f}, mult={mult})")
            
        print(f"{type_val} - {name} | Shared: {details} | Score: {score:.3f} | Max Single: {max_single:.3f}")

if __name__ == "__main__":
    main()
