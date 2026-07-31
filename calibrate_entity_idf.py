import sqlite3
import math
from pathlib import Path
from collections import defaultdict
import re

# Need to simulate cluster.py's NER extraction
def _get_nlp():
    import spacy
    return spacy.load("xx_ent_wiki_sm")

def _extract_entities(text: str, nlp) -> frozenset:
    if not text.strip():
        return frozenset()
    doc = nlp(text)
    return frozenset(ent.text.lower().strip() for ent in doc.ents if ent.text.strip())

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
    
    print(f"Loaded {N} items. Extracting entities to build DF...")
    nlp = _get_nlp()
    
    # Pre-extract entities for all items
    item_entities = {}
    df = defaultdict(int)
    
    for item in items:
        ner_input = _make_ner_input(item['title'] or "", item['raw_text'] or "", 2)
        ents = _extract_entities(ner_input, nlp)
        item_entities[item['item_hash']] = ents
        for e in ents:
            df[e] += 1
            
    def get_weight(e):
        # Using standard IDF formula: log(N / df(e)). 
        # df(e) is guaranteed to be >= 1 if it's in the dictionary.
        # This gives higher weight to rare entities (e.g. df=1 -> log(N)),
        # and lower weight to common entities.
        return math.log(N / df[e])
        
    def match_score(ents_a, ents_b):
        shared = ents_a & ents_b
        return sum(get_weight(e) for e in shared)
        
    print("\n--- Document Frequencies for key entities ---")
    for entity in ["trump", "china", "openai", "todd blanche", "blanche", "pavel durov", "durov", "evo morales", "morales"]:
        if entity in df:
            print(f"'{entity}': df={df[entity]}, weight={get_weight(entity):.3f}")
        else:
            print(f"'{entity}': NOT FOUND")
            
    print("\n--- Calibration for Known Pairs ---")
    # Helper to find an item by a substring in title
    def find_item(substr):
        for item in items:
            if substr.lower() in (item['title'] or "").lower():
                return item
        return None
        
    pairs = [
        ("GOOD", "Blanche", "With Blanche Nomination at Stake", "Senate committee delays vote on Todd Blanche"),
        ("GOOD", "Durov", "Why is the founder of Telegram on Russia", "Who is Pavel Durov? Inside the Telegram"),
        ("GOOD", "Morales", "ordena prisão de Evo Morales", "ordena la detención del expresidente Evo Morales"),
        ("BAD", "Trump/Carroll", "With Blanche Nomination at Stake", "Trump appeals $83.3m E Jean Carroll"),
        ("BAD", "Trump Media/Iran", "probe Trump Media's paid service", "Trump threatens to hit Iran ‘hard’"),
        ("BAD", "China", "China’s Coal Demand Gets Boost", "China’s Launch of Advanced Hypersonic Missile"),
        ("BAD", "OpenAI/ChatGPT", "OpenAI’s alarming escape", "ChatGPT, Roblox to Fall Under Strictest EU Rules")
    ]
    
    good_scores = []
    bad_scores = []
    
    for type_val, name, title_a, title_b in pairs:
        item_a = find_item(title_a)
        item_b = find_item(title_b)
        
        if not item_a or not item_b:
            print(f"[{type_val}-{name}] Missing items! ({title_a[:20]}... or {title_b[:20]}...)")
            continue
            
        ents_a = item_entities[item_a['item_hash']]
        ents_b = item_entities[item_b['item_hash']]
        shared = ents_a & ents_b
        score = match_score(ents_a, ents_b)
        
        print(f"[{type_val}-{name}] Score: {score:.3f} | Shared: {list(shared)}")
        if type_val == "GOOD":
            good_scores.append(score)
        else:
            bad_scores.append(score)
            
    print("\n--- Summary ---")
    if good_scores and bad_scores:
        print(f"Min Good Score: {min(good_scores):.3f}")
        print(f"Max Bad Score:  {max(bad_scores):.3f}")

if __name__ == "__main__":
    main()
