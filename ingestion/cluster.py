"""
Story clustering for the WeAware ingestion pipeline.

Groups news items that likely cover the same real-world event using a
word-overlap (Jaccard) similarity on normalised titles. This is the same
algorithm that was in the original Data/rss_aggregation.py, ported into
the modern pipeline so it runs as part of every ingestion cycle.

Design notes:
- Intentionally lightweight (no NLP deps) so the pipeline stays self-hostable.
- Comparison window limits work to items within TITLE_SIMILARITY_WINDOW_HOURS
  of each other, keeping O(n) manageable.
- `similarity_threshold` defaults to 0.5 — same as the original script.
- Each cluster is represented by the hash of its earliest/canonical item.
"""

import re
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from ingestion.utils import UTC, normalize_text


TITLE_SIMILARITY_WINDOW_HOURS: int = 6
DEFAULT_SIMILARITY_THRESHOLD: float = 0.5


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalise_title(title: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    title = title.lower()
    title = re.sub(r"[^\w\s]", "", title)
    return re.sub(r"\s+", " ", title).strip()


def _word_overlap_ratio(a: str, b: str) -> float:
    """Jaccard similarity on word sets (0–1)."""
    words_a, words_b = set(a.split()), set(b.split())
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / len(words_a | words_b)


def _parse_dt(iso: Optional[str]) -> Optional[datetime]:
    if not iso:
        return None
    try:
        return datetime.fromisoformat(iso).astimezone(UTC)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def cluster_items(
    items: List[Dict],
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    window_hours: int = TITLE_SIMILARITY_WINDOW_HOURS,
) -> Tuple[List[Dict], Dict[str, str]]:
    """
    Group items into story clusters based on title similarity.

    Returns:
        clusters: list of story dicts, each with:
            story_id, source_count, recency, item_hashes (list of item_hash)
        item_to_story: mapping of item_hash → story_id

    Items are only compared against cluster heads published within
    `window_hours` of each other to bound comparisons on large corpora.
    """
    # Each entry: (norm_title, published_dt, story_id, list_of_item_hashes)
    cluster_heads: List[Tuple[str, Optional[datetime], str, List[str]]] = []
    item_to_story: Dict[str, str] = {}

    for item in items:
        norm_title = _normalise_title(normalize_text(str(item.get("title") or "")))
        pub_dt = _parse_dt(str(item.get("published_at") or "") or None)
        item_hash = str(item["item_hash"])

        placed = False
        for idx, (head_title, head_dt, story_id, hashes) in enumerate(cluster_heads):
            # Time-window guard
            if pub_dt and head_dt:
                if abs((pub_dt - head_dt).total_seconds()) > window_hours * 3600:
                    continue

            if _word_overlap_ratio(norm_title, head_title) >= similarity_threshold:
                hashes.append(item_hash)
                item_to_story[item_hash] = story_id
                placed = True
                break

        if not placed:
            new_story_id = str(uuid.uuid4())
            cluster_heads.append((norm_title, pub_dt, new_story_id, [item_hash]))
            item_to_story[item_hash] = new_story_id

    # Build story records
    # Build a map from item_hash to item for recency calculation
    hash_to_item: Dict[str, Dict] = {str(i["item_hash"]): i for i in items}

    stories: List[Dict] = []
    for _norm_title, _head_dt, story_id, hashes in cluster_heads:
        recency_candidates = [
            str(hash_to_item[h]["published_at"])
            for h in hashes
            if hash_to_item.get(h, {}).get("published_at")
        ]
        recency = max(recency_candidates) if recency_candidates else datetime.now(UTC).isoformat()
        stories.append(
            {
                "story_id": story_id,
                "source_count": len({
                    hash_to_item[h].get("source_id") for h in hashes if h in hash_to_item
                }),
                "recency": recency,
                "item_hashes": hashes,
            }
        )

    return stories, item_to_story
