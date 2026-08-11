"""
Normalisation and intra-source deduplication for the WeAware ingestion pipeline.

normalize_items() converts heterogeneous raw dicts (from any adapter) into a
single canonical schema. dedup_intra_source() removes URL-level duplicates
within the same source within one fetch cycle.
"""

from datetime import datetime
from typing import Dict, Iterable, List, Optional

from ingestion.utils import UTC, canonicalize_url, normalize_text, normalize_iso, stable_item_hash

# Items with fewer than this many words in raw_text are flagged as 'short'
SHORT_TEXT_WORD_THRESHOLD = 20


def _extraction_status(raw_text: str) -> str:
    """Classify the extraction quality of a raw-text field."""
    if not raw_text:
        return "failed"
    if len(raw_text.split()) < SHORT_TEXT_WORD_THRESHOLD:
        return "short"
    return "ok"


def normalize_items(raw_items: Iterable[Dict]) -> List[Dict]:
    """
    Normalise raw items from any adapter into the unified pipeline schema.

    Items missing a source_id, source_name, or url are silently dropped
    (they cannot be meaningfully stored or deduplicated without those keys).
    """
    now_iso = datetime.now(UTC).isoformat()
    normalized: List[Dict] = []

    for item in raw_items:
        source_name = normalize_text(str(item.get("source_name") or ""))
        url = canonicalize_url(str(item.get("url") or ""))
        source_id = normalize_text(str(item.get("source_id") or ""))

        if not source_name or not url or not source_id:
            continue

        raw_text = normalize_text(str(item.get("raw_text") or ""))

        normalized_item: Dict = {
            "source_id": source_id,
            "source_name": source_name,
            "source_type": normalize_text(str(item.get("source_type") or "unknown")),
            "region": normalize_text(str(item.get("region") or "global")),
            "url": url,
            "title": normalize_text(str(item.get("title") or "")),
            "raw_text": raw_text,
            "published_at": normalize_iso(str(item.get("published_at") or "")),
            "fetched_at": normalize_iso(str(item.get("fetched_at") or "")) or now_iso,
            "author": normalize_text(str(item.get("author") or "")) or None,
            "lang": normalize_text(str(item.get("lang") or "en")),
            "paywall": bool(item.get("paywall", False)),
            "is_social": bool(item.get("is_social", False)),
            "extraction_status": _extraction_status(raw_text),
            # Populated by the clustering stage in run_stage1.py
            "story_id": None,
            "has_cross_source_corroboration": False,
        }
        # Attach the stable hash so downstream code can reference it
        normalized_item["item_hash"] = stable_item_hash(source_id, url)
        normalized.append(normalized_item)

    return normalized


def dedup_intra_source(items: Iterable[Dict]) -> List[Dict]:
    """
    Remove URL-level duplicates within the same source within one fetch cycle.

    When two items share (source_id, canonical_url), keep the one with the
    longer raw_text (richer content wins).
    """
    deduped: Dict[tuple, Dict] = {}

    for item in items:
        source_id = str(item["source_id"])
        canonical_url = canonicalize_url(str(item["url"]))
        key = (source_id, canonical_url)

        existing = deduped.get(key)
        if not existing:
            deduped[key] = item
            continue

        if len(str(item.get("raw_text") or "")) > len(str(existing.get("raw_text") or "")):
            deduped[key] = item

    return list(deduped.values())
