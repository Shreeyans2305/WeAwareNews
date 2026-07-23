import json
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, List, Optional
from urllib.error import HTTPError, URLError


def _strip_html(value: str) -> str:
    return re.sub(r"<[^>]+>", " ", value or "").strip()


def _parse_datetime(value: str | None) -> Optional[str]:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(UTC).isoformat()
    except (TypeError, ValueError):
        pass

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC).isoformat()
    except ValueError:
        return None


def _xml_text(parent: ET.Element, tags: List[str]) -> str:
    for tag in tags:
        node = parent.find(tag)
        if node is not None and node.text:
            return node.text.strip()
    return ""


class RSSAdapter:
    def __init__(
        self,
        registry_path: Path,
        request_timeout_seconds: int,
        max_items_per_source: int,
        tier_intervals_seconds: Dict[str, int],
    ) -> None:
        self.registry_path = registry_path
        self.request_timeout_seconds = request_timeout_seconds
        self.max_items_per_source = max_items_per_source
        self.tier_intervals_seconds = tier_intervals_seconds
        self.sources = self._load_sources()

    def _load_sources(self) -> List[Dict[str, object]]:
        data = json.loads(self.registry_path.read_text(encoding="utf-8"))
        return data["sources"]

    def _due_for_poll(
        self,
        source: Dict[str, object],
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

    def _parse_feed_items(self, xml_bytes: bytes) -> List[Dict[str, str | None]]:
        root = ET.fromstring(xml_bytes)
        items: List[Dict[str, str | None]] = []

        channel = root.find("channel")
        if channel is not None:
            nodes = channel.findall("item")
            for node in nodes:
                items.append(
                    {
                        "title": _xml_text(node, ["title"]),
                        "link": _xml_text(node, ["link"]),
                        "summary": _strip_html(_xml_text(node, ["description"])),
                        "author": _xml_text(
                            node, ["author", "{http://purl.org/dc/elements/1.1/}creator"]
                        ),
                        "published_at": _parse_datetime(
                            _xml_text(node, ["pubDate", "{http://purl.org/dc/elements/1.1/}date"])
                        ),
                        "lang": _xml_text(node, ["{http://www.w3.org/XML/1998/namespace}lang"]),
                    }
                )
            return items

        atom_entries = root.findall("{http://www.w3.org/2005/Atom}entry")
        for entry in atom_entries:
            link = ""
            link_node = entry.find("{http://www.w3.org/2005/Atom}link")
            if link_node is not None:
                link = (link_node.attrib.get("href") or "").strip()

            summary = _xml_text(entry, ["{http://www.w3.org/2005/Atom}summary"])
            if not summary:
                summary = _xml_text(entry, ["{http://www.w3.org/2005/Atom}content"])
            items.append(
                {
                    "title": _xml_text(entry, ["{http://www.w3.org/2005/Atom}title"]),
                    "link": link,
                    "summary": _strip_html(summary),
                    "author": _xml_text(entry, ["{http://www.w3.org/2005/Atom}author"]),
                    "published_at": _parse_datetime(
                        _xml_text(
                            entry,
                            [
                                "{http://www.w3.org/2005/Atom}published",
                                "{http://www.w3.org/2005/Atom}updated",
                            ],
                        )
                    ),
                    "lang": "",
                }
            )
        return items

    def fetch(
        self, last_polled_at_by_feed_id: Dict[str, str]
    ) -> tuple[List[Dict[str, object]], Dict[str, str], List[str]]:
        now_utc = datetime.now(UTC)
        fetched_at = now_utc.isoformat()
        raw_items: List[Dict[str, object]] = []
        poll_updates: Dict[str, str] = {}
        errors: List[str] = []

        for source in self.sources:
            if not self._due_for_poll(source, now_utc, last_polled_at_by_feed_id):
                continue

            request = urllib.request.Request(
                str(source["url"]),
                headers={"User-Agent": "WeAwareIngestion/1.0 (+RSS Poller)"},
            )

            feed_entries: List[Dict[str, str | None]] = []
            try:
                with urllib.request.urlopen(request, timeout=self.request_timeout_seconds) as response:
                    feed_entries = self._parse_feed_items(response.read())
            except (HTTPError, URLError, TimeoutError, ET.ParseError, UnicodeDecodeError) as error:
                errors.append(f"RSS fetch failed for {source['feed_id']}: {error}")
                poll_updates[str(source["feed_id"])] = fetched_at
                continue

            for entry in feed_entries[: self.max_items_per_source]:
                raw_items.append(
                    {
                        "source_id": source["source_id"],
                        "source_name": source["source_name"],
                        "source_type": "rss",
                        "region": source["region"],
                        "url": entry.get("link", "") or "",
                        "title": entry.get("title", "") or "",
                        "raw_text": entry.get("summary", "") or "",
                        "published_at": entry.get("published_at"),
                        "fetched_at": fetched_at,
                        "author": entry.get("author") or None,
                        "lang": (entry.get("lang") or "en"),
                        "paywall": bool(source["paywall"]),
                        "is_social": False,
                    }
                )

            poll_updates[str(source["feed_id"])] = fetched_at

        return raw_items, poll_updates, errors
