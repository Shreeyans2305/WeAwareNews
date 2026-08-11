"""
RSS adapter for the WeAware ingestion pipeline.

Uses feedparser (feedparser-6.x) for robust RSS/Atom parsing — the same
library that powered the original WeAware prototype. The polling-state and
tier-interval logic from the modern pipeline is preserved so feeds are only
re-fetched when their interval has elapsed.

Source metadata (region, tier, paywall, etc.) comes from
ingestion/sources/registry.json so the feed list is managed in one place.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import feedparser

from ingestion.utils import UTC, normalize_text, strip_html


class RSSAdapter:
    def __init__(
        self,
        registry_path: Path,
        request_timeout_seconds: int,
        max_items_per_source: int,
        tier_intervals_seconds: Dict[str, int],
    ) -> None:
        self.request_timeout_seconds = request_timeout_seconds
        self.max_items_per_source = max_items_per_source
        self.tier_intervals_seconds = tier_intervals_seconds
        self.sources = self._load_sources(registry_path)

    # ------------------------------------------------------------------
    # Source registry
    # ------------------------------------------------------------------

    @staticmethod
    def _load_sources(registry_path: Path) -> List[Dict]:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        return data["sources"]

    # ------------------------------------------------------------------
    # Polling-interval gate
    # ------------------------------------------------------------------

    def _due_for_poll(
        self,
        source: Dict,
        now_utc: datetime,
        last_polled_at_by_feed_id: Dict[str, str],
    ) -> bool:
        feed_id = str(source["feed_id"])
        last_polled_at = last_polled_at_by_feed_id.get(feed_id)
        if not last_polled_at:
            return True

        tier = str(source.get("tier", "secondary"))
        interval = self.tier_intervals_seconds.get(tier, self.tier_intervals_seconds["secondary"])
        last_polled_dt = datetime.fromisoformat(last_polled_at)
        elapsed_seconds = (now_utc - last_polled_dt).total_seconds()
        return elapsed_seconds >= interval

    # ------------------------------------------------------------------
    # Feed parsing (feedparser)
    # ------------------------------------------------------------------

    def _parse_feed(self, url: str) -> Tuple[List[Dict], Optional[str]]:
        """
        Fetch and parse one feed URL with feedparser.

        Returns (entries, error_message_or_None).
        feedparser handles both RSS 2.0 and Atom transparently.

        feedparser.parse() is documented as "never raises", but in practice
        some redirect chains (HTTP → HTTPS) cause RemoteDisconnected or other
        socket-level errors to escape. We catch them here so one bad feed
        cannot abort the entire run.
        """
        try:
            parsed = feedparser.parse(
                url,
                request_headers={"User-Agent": "WeAwareIngestion/1.0 (+RSS Poller)"},
                agent="WeAwareIngestion/1.0 (+RSS Poller)",
            )
        except Exception as exc:
            return [], str(exc)

        http_status = parsed.get("status", 200)
        if http_status and http_status >= 400:
            return [], f"HTTP {http_status}"

        if parsed.bozo and not parsed.entries:
            return [], f"Parse error: {parsed.bozo_exception}"

        entries: List[Dict] = []
        for entry in parsed.entries:
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            published_iso: Optional[str] = None
            if published:
                try:
                    published_iso = datetime(*published[:6], tzinfo=UTC).isoformat()
                except (TypeError, ValueError):
                    published_iso = None

            # Prefer content > summary for raw_text
            raw_text = ""
            if entry.get("content"):
                raw_text = strip_html(entry["content"][0].get("value", ""))
            if not raw_text:
                raw_text = strip_html(entry.get("summary", ""))

            entries.append(
                {
                    "title": normalize_text(entry.get("title", "")),
                    "link": entry.get("link", ""),
                    "raw_text": raw_text,
                    "author": entry.get("author") or None,
                    "published_at": published_iso,
                    "lang": entry.get("language") or "",
                }
            )

        return entries, None

    # ------------------------------------------------------------------
    # Public fetch
    # ------------------------------------------------------------------

    def fetch(
        self, last_polled_at_by_feed_id: Dict[str, str]
    ) -> Tuple[List[Dict], Dict[str, str], List[str]]:
        """
        Fetch all due RSS feeds.

        Returns:
            raw_items   – list of normalised-ish item dicts
            poll_updates – feed_id → fetched_at timestamp (for poll-state table)
            errors       – list of human-readable warning strings
        """
        now_utc = datetime.now(UTC)
        fetched_at = now_utc.isoformat()
        raw_items: List[Dict] = []
        poll_updates: Dict[str, str] = {}
        errors: List[str] = []

        for source in self.sources:
            if not self._due_for_poll(source, now_utc, last_polled_at_by_feed_id):
                continue

            entries, error = self._parse_feed(str(source["url"]))
            poll_updates[str(source["feed_id"])] = fetched_at

            if error:
                errors.append(f"RSS fetch failed for {source['feed_id']}: {error}")
                continue

            for entry in entries[: self.max_items_per_source]:
                raw_items.append(
                    {
                        "source_id": source["source_id"],
                        "source_name": source["source_name"],
                        "source_type": "rss",
                        "region": source.get("region", "global"),
                        "url": entry.get("link", "") or "",
                        "title": entry.get("title", "") or "",
                        "raw_text": entry.get("raw_text", "") or "",
                        "published_at": entry.get("published_at"),
                        "fetched_at": fetched_at,
                        "author": entry.get("author") or None,
                        "lang": entry.get("lang") or "en",
                        "paywall": bool(source.get("paywall", False)),
                        "is_social": False,
                    }
                )

        return raw_items, poll_updates, errors
