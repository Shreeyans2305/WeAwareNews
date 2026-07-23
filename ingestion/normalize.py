import hashlib
import re
from datetime import UTC, datetime
from typing import Dict, Iterable, List
from urllib.parse import urlparse, urlunparse


def _canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", parsed.query, ""))


def _normalize_iso(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC).isoformat()
    except ValueError:
        return None


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def normalize_items(raw_items: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    now_iso = datetime.now(UTC).isoformat()
    normalized: List[Dict[str, object]] = []

    for item in raw_items:
        source_name = _normalize_text(str(item.get("source_name") or ""))
        url = _canonicalize_url(str(item.get("url") or ""))
        if not source_name or not url:
            continue

        source_id = _normalize_text(str(item.get("source_id") or ""))
        if not source_id:
            continue

        normalized_item: Dict[str, object] = {
            "source_id": source_id,
            "source_name": source_name,
            "source_type": _normalize_text(str(item.get("source_type") or "unknown")),
            "region": _normalize_text(str(item.get("region") or "global")),
            "url": url,
            "title": _normalize_text(str(item.get("title") or "")),
            "raw_text": _normalize_text(str(item.get("raw_text") or "")),
            "published_at": _normalize_iso(str(item.get("published_at") or "")),
            "fetched_at": _normalize_iso(str(item.get("fetched_at") or "")) or now_iso,
            "author": _normalize_text(str(item.get("author") or "")) or None,
            "lang": _normalize_text(str(item.get("lang") or "en")),
            "paywall": bool(item.get("paywall", False)),
            "is_social": bool(item.get("is_social", False)),
            "has_cross_source_corroboration": False,
        }
        normalized.append(normalized_item)

    return normalized


def dedup_intra_source(items: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    deduped: Dict[tuple[str, str], Dict[str, object]] = {}

    for item in items:
        source_id = str(item["source_id"])
        canonical_url = _canonicalize_url(str(item["url"]))
        key = (source_id, canonical_url)

        existing = deduped.get(key)
        if not existing:
            deduped[key] = item
            continue

        existing_text_len = len(str(existing.get("raw_text") or ""))
        candidate_text_len = len(str(item.get("raw_text") or ""))
        if candidate_text_len > existing_text_len:
            deduped[key] = item

    return list(deduped.values())


def stable_item_hash(source_id: str, url: str) -> str:
    return hashlib.sha256(f"{source_id}|{_canonicalize_url(url)}".encode("utf-8")).hexdigest()
