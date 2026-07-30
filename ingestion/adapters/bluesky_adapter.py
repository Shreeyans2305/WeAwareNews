"""
Bluesky adapter for the WeAware ingestion pipeline.

Fetches posts from:
  - Curated accounts (app.bsky.feed.getAuthorFeed)
  - Keyword searches  (app.bsky.feed.searchPosts)

Authenticates via BLUESKY_HANDLE + BLUESKY_APP_PASSWORD env vars when
present; falls back to unauthenticated public API endpoints otherwise.
"""

import json
import os
from datetime import datetime
from http.client import IncompleteRead, RemoteDisconnected
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
import urllib.parse
import urllib.request

from ingestion.utils import UTC, slugify


class BlueskyAdapter:
    def __init__(
        self,
        request_timeout_seconds: int,
        max_items_per_source: int,
        curated_accounts: List[str],
        keywords: List[str],
    ) -> None:
        self.request_timeout_seconds = request_timeout_seconds
        self.max_items_per_source = max_items_per_source
        self.curated_accounts = curated_accounts
        self.keywords = keywords
        self.authenticated_base_url = "https://bsky.social/xrpc"
        self.public_base_url = "https://api.bsky.app/xrpc"

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _post_json(self, endpoint: str, body: Dict, base_url: str) -> Dict:
        payload = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            f"{base_url}/{endpoint}",
            data=payload,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "User-Agent": "WeAwareIngestion/1.0 (+Bluesky)",
            },
        )
        with urllib.request.urlopen(request, timeout=self.request_timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def _get_json(
        self,
        endpoint: str,
        params: Dict,
        token: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> Dict:
        query = urllib.parse.urlencode(params)
        url_base = base_url or self.authenticated_base_url
        headers = {"User-Agent": "WeAwareIngestion/1.0 (+Bluesky)"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(
            f"{url_base}/{endpoint}?{query}", headers=headers
        )
        with urllib.request.urlopen(request, timeout=self.request_timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _login(self, base_url: str) -> str:
        handle = os.getenv("BLUESKY_HANDLE", "").strip()
        app_password = os.getenv("BLUESKY_APP_PASSWORD", "").strip()
        if not handle or not app_password:
            return ""
        response = self._post_json(
            "com.atproto.server.createSession",
            {"identifier": handle, "password": app_password},
            base_url=base_url,
        )
        return str(response.get("accessJwt") or "")

    # ------------------------------------------------------------------
    # Item construction
    # ------------------------------------------------------------------

    def _build_post_url(self, handle: str, uri: str) -> str:
        rkey = uri.split("/")[-1] if uri else ""
        return f"https://bsky.app/profile/{handle}/post/{rkey}"

    def _to_item(self, post: Dict, fallback_source_name: str, fetched_at: str) -> Dict:
        author = post.get("author") if isinstance(post.get("author"), dict) else {}
        handle = str(author.get("handle") or fallback_source_name)
        source_name = str(author.get("displayName") or handle)
        uri = str(post.get("uri") or "")
        record = post.get("record") if isinstance(post.get("record"), dict) else {}
        text = str(record.get("text") or "").strip()
        created_at = record.get("createdAt") if record else None

        return {
            "source_id": f"bluesky-{slugify(handle)}",
            "source_name": source_name,
            "source_type": "bluesky",
            "region": "global",
            "url": self._build_post_url(handle, uri) if uri else "",
            "title": text[:160],
            "raw_text": text,
            "published_at": created_at,
            "fetched_at": fetched_at,
            "author": handle,
            "lang": "en",
            "paywall": False,
            "is_social": True,
        }

    # ------------------------------------------------------------------
    # Public fetch
    # ------------------------------------------------------------------

    _NETWORK_ERRORS = (
        HTTPError, URLError, TimeoutError, json.JSONDecodeError,
        ValueError, RemoteDisconnected, IncompleteRead,
    )

    def fetch(self) -> Tuple[List[Dict], List[str]]:
        errors: List[str] = []
        token = ""
        base_url = self.public_base_url

        if os.getenv("BLUESKY_HANDLE", "").strip() and os.getenv("BLUESKY_APP_PASSWORD", "").strip():
            try:
                token = self._login(self.authenticated_base_url)
                if token:
                    base_url = self.authenticated_base_url
            except self._NETWORK_ERRORS as error:
                errors.append(f"Bluesky login failed, continuing unauthenticated: {error}")

        fetched_at = datetime.now(UTC).isoformat()
        items: List[Dict] = []

        for handle in self.curated_accounts:
            try:
                payload = self._get_json(
                    "app.bsky.feed.getAuthorFeed",
                    {"actor": handle, "limit": str(self.max_items_per_source)},
                    token=token or None,
                    base_url=base_url,
                )
            except self._NETWORK_ERRORS as error:
                errors.append(f"Bluesky author feed failed for {handle}: {error}")
                continue

            feed = payload.get("feed", [])
            if not isinstance(feed, list):
                continue
            for item in feed:
                if not isinstance(item, dict):
                    continue
                post = item.get("post") if isinstance(item.get("post"), dict) else {}
                if post:
                    items.append(self._to_item(post, handle, fetched_at))

        for keyword in self.keywords:
            try:
                payload = self._get_json(
                    "app.bsky.feed.searchPosts",
                    {"q": keyword, "limit": str(self.max_items_per_source)},
                    token=token or None,
                    base_url=base_url,
                )
            except self._NETWORK_ERRORS as error:
                errors.append(f"Bluesky keyword search failed for '{keyword}': {error}")
                continue

            posts = payload.get("posts", [])
            if not isinstance(posts, list):
                continue
            for post in posts:
                if isinstance(post, dict):
                    items.append(self._to_item(post, "search", fetched_at))

        return items, errors
