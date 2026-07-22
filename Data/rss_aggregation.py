"""
WeAware RSS Aggregator
-----------------------
Polls a list of news RSS feeds, extracts structured items with full
attribution metadata, deduplicates near-identical stories across sources,
and stores results as JSON (swap out save_items() for a DB call later).

Design notes (per WeAware principles):
- Every item keeps source name + original URL -> required for attribution.
- Dedup groups same-event coverage across outlets -> enables cross-source
  bias comparison downstream, instead of treating each feed hit in isolation.
- Lightweight (stdlib + feedparser only) -> fits a self-hosted/local-model
  pipeline; no heavy dependencies.

Install: pip install feedparser
"""

import feedparser
import hashlib
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

# ---- Config -----------------------------------------------------------

FEEDS = [
    # --- North American Baselines ---
    {"source": "Associated Press (Top News)", "url": "https://feeds.apnews.com/rss/apf-topnews"},
    {"source": "NPR News (National)", "url": "https://feeds.npr.org/1001/rss.xml"},
    {"source": "NPR News (World)", "url": "https://feeds.npr.org/1004/rss.xml"},
    {"source": "New York Times (HomePage)", "url": "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml"},
    {"source": "New York Times (World)", "url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"},
    {"source": "Washington Post (World)", "url": "https://feeds.washingtonpost.com/rss/world"},
    {"source": "CNN (World)", "url": "http://rss.cnn.com/rss/edition_world.rss"},
    {"source": "CBC News (Top Stories)", "url": "https://www.cbc.ca/webfeed/rss/rss-topstories"},
    {"source": "CBC News (Indigenous)", "url": "https://www.cbc.ca/webfeed/rss/rss-Indigenous"},
    
    # --- European & Continental Perspectives ---
    {"source": "BBC World", "url": "http://feeds.bbci.co.uk/news/world/rss.xml"},
    {"source": "BBC Technology", "url": "http://feeds.bbci.co.uk/news/technology/rss.xml"},
    {"source": "The Guardian (World)", "url": "https://www.theguardian.com/world/rss"},
    {"source": "Deutsche Welle (DW)", "url": "https://rss.dw.com/rdf/rss-en-all"},
    {"source": "France 24 (English)", "url": "https://www.france24.com/en/rss"},
    {"source": "El País (Global)", "url": "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada"},

    # --- Middle East & Global South ---
    {"source": "Al Jazeera (All)", "url": "https://www.aljazeera.com/xml/rss/all.xml"},
    {"source": "Folha de S.Paulo (Brazil)", "url": "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml"},

    # --- The Asian Geopolitical Theater ---
    {"source": "South China Morning Post (World)", "url": "https://www.scmp.com/rss/5/feed"},
    {"source": "South China Morning Post (China)", "url": "https://www.scmp.com/rss/4/feed"},
    {"source": "South China Morning Post (Tech)", "url": "https://www.scmp.com/rss/36/feed"},
    {"source": "The Hindu (Home)", "url": "https://www.thehindu.com/feeder/default.rss"},
    {"source": "Times of India (Top Stories)", "url": "http://timesofindia.indiatimes.com/rssfeedstopstories.cms"},
    {"source": "Indian Express (India)", "url": "https://indianexpress.com/section/india/feed/"},
    {"source": "Indian Express (World)", "url": "https://indianexpress.com/section/world/feed/"},
    {"source": "Hindustan Times (Top News)", "url": "https://www.hindustantimes.com/feeds/rss/top-news/rssfeed.xml"},
    {"source": "NDTV (Top Stories)", "url": "https://feeds.feedburner.com/ndtvnews-top-stories"},
    {"source": "Sydney Morning Herald", "url": "https://www.smh.com.au/rss/feed.xml"},
    {"source": "The Daily Star (Bangladesh)", "url": "https://www.thedailystar.net/frontpage/rss.xml"},

    # --- Financial & Economic Intelligence ---
    {"source": "Financial Times (World)", "url": "https://www.ft.com/world?format=rss"},
    {"source": "Financial Times (Markets)", "url": "https://www.ft.com/markets?format=rss"},
    {"source": "Wall Street Journal (World)", "url": "https://feeds.a.dj.com/rss/RSSWorldNews.xml"},
    {"source": "Wall Street Journal (Markets)", "url": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"},
    {"source": "Bloomberg (Markets)", "url": "https://feeds.bloomberg.com/markets/news.rss"},
    {"source": "Bloomberg (Technology)", "url": "https://feeds.bloomberg.com/technology/news.rss"},
    {"source": "The Economist", "url": "https://www.economist.com/latest/rss.xml"},
    {"source": "Livemint (News)", "url": "https://www.livemint.com/rss/news"},
    {"source": "The Economic Times (Latest)", "url": "https://economictimes.indiatimes.com/rssfeedsdefault.cms"},
    {"source": "Business Standard", "url": "http://www.business-standard.com/rss/latest.rss"},
    {"source": "MarketWatch (Top Stories)", "url": "https://www.marketwatch.com/rss/topstories"},
    {"source": "CNBC (World)", "url": "https://www.cnbc.com/id/100727362/device/rss/rss.html"},

    # --- Technology, Science, and Cybersecurity ---
    {"source": "Ars Technica", "url": "http://feeds.arstechnica.com/arstechnica/index"},
    {"source": "Wired", "url": "https://www.wired.com/feed/rss"},
    {"source": "TechCrunch", "url": "https://techcrunch.com/feed/"},
    {"source": "The Verge", "url": "https://www.theverge.com/rss/index.xml"},
    {"source": "Krebs on Security", "url": "https://krebsonsecurity.com/feed"},

    # --- Synthetic Bridges (For publishers lacking native RSS) ---
    # Reuters discontinued direct RSS in 2020; this uses the Google News proxy bridge to retain coverage.
    {"source": "Reuters (via Google News Bridge)", "url": "https://news.google.com/rss/search?q=when:24h+allinurl:reuters.com"}
]

OUTPUT_FILE = Path("weaware_items.json")
TITLE_SIMILARITY_WINDOW_HOURS = 6  # only compare items within this window


# ---- Fetching -----------------------------------------------------------

def fetch_feed(source_name, url):
    """Fetch one feed and return a list of normalized item dicts."""
    parsed = feedparser.parse(url)
    items = []

    status = parsed.get("status")
    if status and status >= 400:
        print(f"[error] '{source_name}' returned HTTP {status} -- feed URL may be dead or blocked")
    if parsed.bozo and not parsed.entries:
        print(f"[warn] '{source_name}' feed had a parse issue: {parsed.bozo_exception}")
    if not parsed.entries:
        print(f"[warn] '{source_name}' returned 0 entries")

    for entry in parsed.entries:
        published = entry.get("published_parsed") or entry.get("updated_parsed")
        published_iso = (
            datetime(*published[:6], tzinfo=timezone.utc).isoformat()
            if published else None
        )

        items.append({
            "source": source_name,
            "title": entry.get("title", "").strip(),
            "summary": entry.get("summary", "").strip(),
            "url": entry.get("link", ""),
            "author": entry.get("author", None),
            "published_at": published_iso,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "item_id": hashlib.sha256(entry.get("link", "").encode()).hexdigest()[:16],
        })
    return items


def fetch_all_feeds(feeds=FEEDS):
    all_items = []
    for feed in feeds:
        try:
            all_items.extend(fetch_feed(feed["source"], feed["url"]))
        except Exception as e:
            print(f"[error] failed to fetch '{feed['source']}': {e}")
    return all_items


# ---- Deduplication / clustering -----------------------------------------

def normalize_title(title):
    """Lowercase, strip punctuation, collapse whitespace for comparison."""
    title = title.lower()
    title = re.sub(r"[^\w\s]", "", title)
    return re.sub(r"\s+", " ", title).strip()


def title_overlap_ratio(a, b):
    """Simple word-overlap similarity (0-1). No heavy NLP deps needed."""
    words_a, words_b = set(a.split()), set(b.split())
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def cluster_items(items, similarity_threshold=0.5):
    """
    Group items likely covering the same story across sources.
    Returns a list of clusters; each cluster = list of original items.
    This is intentionally simple (word-overlap heuristic) -- swap in an
    embedding-based match later if your local model stack supports it.
    """
    clusters = []
    for item in items:
        norm_title = normalize_title(item["title"])
        placed = False
        for cluster in clusters:
            rep_title = normalize_title(cluster[0]["title"])
            if title_overlap_ratio(norm_title, rep_title) >= similarity_threshold:
                cluster.append(item)
                placed = True
                break
        if not placed:
            clusters.append([item])
    return clusters


# ---- Output ---------------------------------------------------------------

def save_items(clusters, path=OUTPUT_FILE):
    """
    Save clustered stories to JSON. Each cluster becomes one 'story' with
    its contributing sources listed -- this is the shape a bias/cross-
    reference agent would consume next.
    """
    stories = []
    for cluster in clusters:
        stories.append({
            "story_id": cluster[0]["item_id"],
            "source_count": len(cluster),
            "sources": [c["source"] for c in cluster],
            "items": cluster,
        })

    with open(path, "w", encoding="utf-8") as f:
        json.dump(stories, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(stories)} story clusters ({sum(len(s['items']) for s in stories)} total items) -> {path.resolve()}")


# ---- Main -----------------------------------------------------------------

if __name__ == "__main__":
    print(f"Fetching {len(FEEDS)} feeds...")
    items = fetch_all_feeds()
    print(f"Retrieved {len(items)} raw items.")

    clusters = cluster_items(items)
    multi_source = [c for c in clusters if len(c) > 1]
    print(f"Formed {len(clusters)} clusters ({len(multi_source)} confirmed by 2+ sources).")

    save_items(clusters)