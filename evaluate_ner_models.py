import sqlite3
import math
import time
from pathlib import Path
from collections import defaultdict
import re

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
    
    # 1. Load spaCy
    import spacy
    print("Loading spaCy...")
    spacy_nlp = spacy.load("xx_ent_wiki_sm")
    
    def extract_spacy(text):
        if not text.strip(): return {}
        doc = spacy_nlp(text)
        # return dict of text -> label
        return {ent.text.lower().strip(): ent.label_ for ent in doc.ents if ent.text.strip()}
        
    # 2. Load wikineural
    print("Loading wikineural...")
    from transformers import pipeline
    wiki_pipeline = pipeline("ner", model="Babelscape/wikineural-multilingual-ner", aggregation_strategy="simple")
    
    def extract_wiki(text):
        if not text.strip(): return {}
        ents = wiki_pipeline(text)
        # return dict of text -> label
        # The label is in `entity_group` (e.g. 'PER', 'LOC', 'ORG', 'MISC')
        return {ent['word'].lower().strip(): ent['entity_group'] for ent in ents if ent['word'].strip()}
        
    # Build DFs and evaluate time
    print("Extracting with spaCy (timing 50 items)...")
    start = time.time()
    for item in items[:50]:
        ner_input = _make_ner_input(item['title'] or "", item['raw_text'] or "", 2)
        extract_spacy(ner_input)
    spacy_time = time.time() - start
    print(f"spaCy 50 items: {spacy_time:.2f}s (approx {spacy_time/50:.3f}s/item)")

    print("Extracting with wikineural (timing 50 items)...")
    start = time.time()
    for item in items[:50]:
        ner_input = _make_ner_input(item['title'] or "", item['raw_text'] or "", 2)
        extract_wiki(ner_input)
    wiki_time = time.time() - start
    print(f"wikineural 50 items: {wiki_time:.2f}s (approx {wiki_time/50:.3f}s/item)")

    # Build global DF for both models
    print("Building global DF for both models over all items...")
    df_spacy = defaultdict(int)
    df_wiki = defaultdict(int)
    
    item_ents_spacy = {}
    item_ents_wiki = {}
    
    for item in items:
        ner_input = _make_ner_input(item['title'] or "", item['raw_text'] or "", 2)
        
        ents_s = extract_spacy(ner_input)
        item_ents_spacy[item['item_hash']] = ents_s
        for e in ents_s: df_spacy[e] += 1
            
        ents_w = extract_wiki(ner_input)
        item_ents_wiki[item['item_hash']] = ents_w
        for e in ents_w: df_wiki[e] += 1
            
    # Evaluation
    pairs = [
        ("GOOD", "Blanche", "With Blanche Nomination at Stake", "Senate committee delays vote on Todd Blanche", True),
        ("GOOD", "Durov", "Why is the founder of Telegram on Russia", "Who is Pavel Durov? Inside the Telegram", True),
        ("GOOD", "Morales", "ordena prisão de Evo Morales", "ordena la detención del expresidente Evo Morales", True),
        ("BAD", "Trump/Carroll", "With Blanche Nomination at Stake", "Trump appeals $83.3m E Jean Carroll", False),
        ("BAD", "Trump Media/Iran", "probe Trump Media's paid service", "Trump threatens to hit Iran ‘hard’", False),
        ("BAD", "China", "China’s Coal Demand Gets Boost", "China’s Launch of Advanced Hypersonic Missile", False),
        ("BAD", "OpenAI/ChatGPT", "OpenAI’s alarming escape", "ChatGPT, Roblox to Fall Under Strictest EU Rules", False),
        ("BAD", "Delhi HPV/Shooting", "Delhi HC declines to stay HPV vaccination drive", "Woman Shot Dead By Unidentified Gunmen In Delhi", False),
        ("BAD", "Trump-China Stack", "Trump widens China tech war", "Trump blasts Fauci, says he ‘always tried to protect China’", False)
    ]
    
    def score_pair(item_a, item_b, item_ents_dict, df):
        ents_a = item_ents_dict[item_a['item_hash']]
        ents_b = item_ents_dict[item_b['item_hash']]
        shared = set(ents_a.keys()) & set(ents_b.keys())
        
        # We need the extracted entities with labels to print
        shared_details = []
        for e in shared:
            label = ents_a.get(e) or ents_b.get(e)
            shared_details.append(f"{e} ({label})")
            
        if not shared:
            return 0.0, 0.0, False, shared_details
            
        score = sum(math.log(N / df[e]) for e in shared)
        max_single = max(math.log(N / df[e]) for e in shared)
        passes = (score >= 4.5) and (max_single >= 4.0)
        return score, max_single, passes, shared_details

    print("\n" + "="*80)
    print("COMPARISON TABLE")
    print("="*80)
    
    for type_val, name, title_a, title_b, expected_pass in pairs:
        item_a = next((i for i in items if title_a.lower() in (i['title'] or "").lower()), None)
        item_b = next((i for i in items if title_b.lower() in (i['title'] or "").lower()), None)
        
        if not item_a or not item_b:
            print(f"{name}: Missing items!")
            continue
            
        spacy_score, spacy_max, spacy_pass, spacy_shared = score_pair(item_a, item_b, item_ents_spacy, df_spacy)
        wiki_score, wiki_max, wiki_pass, wiki_shared = score_pair(item_a, item_b, item_ents_wiki, df_wiki)
        
        print(f"[{name}] Expected Pass: {expected_pass}")
        print(f"  spaCy:      Score={spacy_score:.2f}, MaxSingle={spacy_max:.2f}, Pass={spacy_pass} | Shared={spacy_shared}")
        print(f"  wikineural: Score={wiki_score:.2f}, MaxSingle={wiki_max:.2f}, Pass={wiki_pass} | Shared={wiki_shared}")
        print("-" * 80)
        
if __name__ == "__main__":
    main()
