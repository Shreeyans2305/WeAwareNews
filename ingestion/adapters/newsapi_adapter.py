import json
import os
import re
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Dict, Iterable, List
from urllib.error import HTTPError, URLError


def _slugify(value: str) -> str:
    lowered = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return lowered or "unknown-source"


class NewsAPIClient(ABC):
    env_key_name: str
    source_type_name: str

    def __init__(self, request_timeout_seconds: int, max_items_per_source: int) -> None:
        self.request_timeout_seconds = request_timeout_seconds
        self.max_items_per_source = max_items_per_source

    @property
    def api_key(self) -> str:
        return os.getenv(self.env_key_name, "").strip()

    def enabled(self) -> bool:
        return bool(self.api_key)

    def _request_json(self, url: str) -> Dict[str, object]:
        request = urllib.request.Request(url, headers={"User-Agent": "WeAwareIngestion/1.0 (+NewsAPI)"})
        with urllib.request.urlopen(request, timeout=self.request_timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    @abstractmethod
    def fetch(self, fetched_at: str) -> List[Dict[str, object]]:
        raise NotImplementedError


class CurrentsClient(NewsAPIClient):
    env_key_name = "CURRENTS_API_KEY"
    source_type_name = "news_api_currents"

    def fetch(self, fetched_at: str) -> List[Dict[str, object]]:
        query = urllib.parse.urlencode(
            {
                "apiKey": self.api_key,
                "language": "en",
            }
        )
        payload = self._request_json(f"https://api.currentsapi.services/v1/latest-news?{query}")
        records = payload.get("news", [])
        if not isinstance(records, list):
            return []

        items: List[Dict[str, object]] = []
        for article in records:
            if not isinstance(article, dict):
                continue
            publisher = str(article.get("author") or "Currents")
            items.append(
                {
                    "source_id": _slugify(publisher),
                    "source_name": publisher,
                    "source_type": self.source_type_name,
                    "region": "global",
                    "url": str(article.get("url") or ""),
                    "title": str(article.get("title") or ""),
                    "raw_text": str(article.get("description") or ""),
                    "published_at": article.get("published") or article.get("published_at"),
                    "fetched_at": fetched_at,
                    "author": article.get("author"),
                    "lang": article.get("language") or "en",
                    "paywall": False,
                    "is_social": False,
                }
            )
        return items


class WorldNewsClient(NewsAPIClient):
    env_key_name = "WORLD_NEWS_API"
    source_type_name = "news_api_world_news"

    def fetch(self, fetched_at: str) -> List[Dict[str, object]]:
        query = urllib.parse.urlencode(
            {
                "api-key": self.api_key,
                "language": "en",
                "number": self.max_items_per_source,
                "sort": "publish-time",
                "sort-direction": "DESC",
            }
        )
        payload = self._request_json(f"https://api.worldnewsapi.com/search-news?{query}")
        records = payload.get("news", [])
        if not isinstance(records, list):
            return []

        items: List[Dict[str, object]] = []
        for article in records:
            if not isinstance(article, dict):
                continue
            source_name = str(article.get("source") or article.get("news_site") or "World News API")
            items.append(
                {
                    "source_id": _slugify(source_name),
                    "source_name": source_name,
                    "source_type": self.source_type_name,
                    "region": "global",
                    "url": str(article.get("url") or ""),
                    "title": str(article.get("title") or ""),
                    "raw_text": str(article.get("text") or article.get("summary") or ""),
                    "published_at": article.get("publish_date") or article.get("published_at"),
                    "fetched_at": fetched_at,
                    "author": article.get("author"),
                    "lang": article.get("language") or "en",
                    "paywall": bool(article.get("is_paid")),
                    "is_social": False,
                }
            )
        return items


class GNewsClient(NewsAPIClient):
    env_key_name = "GNEWS_API"
    source_type_name = "news_api_gnews"

    def fetch(self, fetched_at: str) -> List[Dict[str, object]]:
        query = urllib.parse.urlencode(
            {
                "token": self.api_key,
                "lang": "en",
                "max": self.max_items_per_source,
                "topic": "breaking-news",
            }
        )
        payload = self._request_json(f"https://gnews.io/api/v4/top-headlines?{query}")
        records = payload.get("articles", [])
        if not isinstance(records, list):
            return []

        items: List[Dict[str, object]] = []
        for article in records:
            if not isinstance(article, dict):
                continue
            source = article.get("source") if isinstance(article.get("source"), dict) else {}
            source_name = str(source.get("name") or "GNews")
            items.append(
                {
                    "source_id": _slugify(source_name),
                    "source_name": source_name,
                    "source_type": self.source_type_name,
                    "region": "global",
                    "url": str(article.get("url") or ""),
                    "title": str(article.get("title") or ""),
                    "raw_text": str(article.get("description") or article.get("content") or ""),
                    "published_at": article.get("publishedAt"),
                    "fetched_at": fetched_at,
                    "author": article.get("author"),
                    "lang": "en",
                    "paywall": False,
                    "is_social": False,
                }
            )
        return items


class WebzClient(NewsAPIClient):
    env_key_name = "WEBZ_API"
    source_type_name = "news_api_webz"

    def fetch(self, fetched_at: str) -> List[Dict[str, object]]:
        query = urllib.parse.urlencode(
            {
                "token": self.api_key,
                "format": "json",
                "language": "english",
                "size": self.max_items_per_source,
                "sort": "published",
            }
        )
        payload = self._request_json(f"https://api.webz.io/newsApiLite?{query}")
        records = payload.get("posts", [])
        if not isinstance(records, list):
            return []

        items: List[Dict[str, object]] = []
        for article in records:
            if not isinstance(article, dict):
                continue
            thread = article.get("thread") if isinstance(article.get("thread"), dict) else {}
            source_name = str(thread.get("site") or "Webz")
            items.append(
                {
                    "source_id": _slugify(source_name),
                    "source_name": source_name,
                    "source_type": self.source_type_name,
                    "region": "global",
                    "url": str(article.get("url") or ""),
                    "title": str(article.get("title") or ""),
                    "raw_text": str(article.get("text") or ""),
                    "published_at": article.get("published"),
                    "fetched_at": fetched_at,
                    "author": article.get("author"),
                    "lang": article.get("language") or "en",
                    "paywall": False,
                    "is_social": False,
                }
            )
        return items


class NewsAPIAdapter:
    def __init__(self, request_timeout_seconds: int, max_items_per_source: int) -> None:
        self.clients: Iterable[NewsAPIClient] = (
            CurrentsClient(request_timeout_seconds, max_items_per_source),
            WorldNewsClient(request_timeout_seconds, max_items_per_source),
            GNewsClient(request_timeout_seconds, max_items_per_source),
            WebzClient(request_timeout_seconds, max_items_per_source),
        )

    def fetch(self) -> tuple[List[Dict[str, object]], List[str]]:
        fetched_at = datetime.now(UTC).isoformat()
        items: List[Dict[str, object]] = []
        errors: List[str] = []

        for client in self.clients:
            if not client.enabled():
                continue
            try:
                items.extend(client.fetch(fetched_at))
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError) as error:
                errors.append(f"{client.__class__.__name__} failed: {error}")
                continue
        return items, errors
