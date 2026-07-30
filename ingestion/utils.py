"""
Shared utilities for the WeAware ingestion pipeline.
Centralises constants and helpers that were previously duplicated across adapters.
"""

import hashlib
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse, urlunparse

UTC = timezone.utc


# ---------------------------------------------------------------------------
# String helpers
# ---------------------------------------------------------------------------

def slugify(value: str) -> str:
    """Convert an arbitrary string to a URL-safe slug."""
    lowered = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return lowered or "unknown"


def normalize_text(value: Optional[str]) -> str:
    """Collapse whitespace and strip a string; return '' if falsy."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def strip_html(value: str) -> str:
    """Remove HTML tags from a string."""
    return re.sub(r"<[^>]+>", " ", value or "").strip()


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

def canonicalize_url(url: str) -> str:
    """Normalise scheme/netloc case and strip trailing slash + fragment."""
    parsed = urlparse(url.strip())
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", parsed.query, ""))


def stable_item_hash(source_id: str, url: str) -> str:
    """Deterministic SHA-256 content-address for a (source, url) pair."""
    return hashlib.sha256(f"{source_id}|{canonicalize_url(url)}".encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Datetime helpers
# ---------------------------------------------------------------------------

def normalize_iso(value: Optional[str]) -> Optional[str]:
    """Parse an ISO-8601 timestamp string and re-emit as UTC ISO string."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC).isoformat()
    except (ValueError, TypeError):
        return None
