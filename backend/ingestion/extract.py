"""
Stage 1.5 — Article text extraction via Jina AI Reader.

For items in the review_queue with extraction_status 'short' or 'failed',
fetches the full article text from https://r.jina.ai/<url> and updates
raw_text and extraction_status in the database.

How Jina AI Reader works:
  GET https://r.jina.ai/<target-url>
  Returns plain text: a short metadata header (Title / URL Source /
  Published Time / "Markdown Content:") followed by the page body as
  markdown. We strip the header and boilerplate navigation using
  Jina's X-Remove-Selector / X-Target-Selector request headers, then
  clean the remaining markdown to plain prose.

Configuration (env vars):
  JINA_API_KEY           Optional. Raises free-tier rate limits.
  WEAWARE_EXTRACT_MAX    Max items to extract per pipeline run (default 50).
  WEAWARE_EXTRACT_DELAY  Seconds to sleep between requests (default 0.5).
  WEAWARE_EXTRACT_ENABLED  Set to "false" to skip the stage entirely.
"""

import os
import re
import time
import urllib.request
from http.client import IncompleteRead, RemoteDisconnected
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError

from bs4 import BeautifulSoup

# ── Configuration constants ───────────────────────────────────────────────────

JINA_READER_BASE = "https://r.jina.ai"
SHORT_TEXT_WORD_THRESHOLD = 20  # must match the threshold in normalize.py

_NETWORK_ERRORS = (HTTPError, URLError, TimeoutError, RemoteDisconnected, IncompleteRead)


# ── Text helpers ──────────────────────────────────────────────────────────────

def _extraction_status(text: str) -> str:
    if not text.strip():
        return "failed"
    if len(text.split()) < SHORT_TEXT_WORD_THRESHOLD:
        return "short"
    return "ok"


def _clean_markdown(raw_body: str) -> str:
    """
    Convert Jina's markdown output to plain prose.

    Strips:
      - Markdown link syntax  [text](url) → text
      - Markdown image syntax ![alt](url) → ''
      - Bold/italic markers   ** / *
      - Heading markers       ## / ###
      - Bullet list prefixes  * / -
      - Excessive blank lines (collapse to single)
    """
    text = raw_body
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)          # images
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)  # links → text
    text = re.sub(r"[*_]{1,3}([^*_]+)[*_]{1,3}", r"\1", text)  # bold/italic
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)  # headings
    text = re.sub(r"^[\*\-]\s+", "", text, flags=re.MULTILINE)  # bullets
    text = re.sub(r"[ \t]+", " ", text)                   # collapse spaces
    text = re.sub(r"\n{3,}", "\n\n", text)                # collapse blank lines
    return text.strip()


def _is_boilerplate_line(line: str) -> bool:
    """
    Heuristic filter for Jina's markdown output.

    Jina dumps the full rendered page as markdown, so the content after
    'Markdown Content:' starts with nav links, image tags, and menu items
    before reaching article prose. We discard a line if it matches any of
    the patterns below. Lines that don't match are assumed to be article prose.
    """
    stripped = line.strip()
    if not stripped:
        return False  # blank lines kept as paragraph separators

    # Pure image tags  ![alt](url)
    if re.match(r"^!\[.*?\]\(.*?\)$", stripped):
        return True
    # Bullet / indented bullet that is ONLY a link  (* [text](url))
    if re.match(r"^\s*[\*\-]\s+\[.{1,80}\]\(.+?\)\s*(\S{0,20})?$", stripped):
        return True
    # Short heading (nav label, section title, not an article heading)
    if re.match(r"^#{1,6}\s+.{1,50}$", stripped) and len(stripped) < 55:
        return True
    # Bare URL
    if re.match(r"^https?://\S+$", stripped):
        return True
    # Very short line that looks like a UI label rather than prose
    # e.g. "skip to content", "Sections", "Edition", "LOGOUT", "Loading..."
    words = stripped.split()
    if len(words) <= 5 and len(stripped) <= 40:
        # Keep it only if it ends with sentence-final punctuation
        if not re.search(r"[.!?]$", stripped):
            return True
    # Lines that are only punctuation / symbols
    if re.match(r"^[\*_\-=~`#|>\\]+$", stripped):
        return True
    return False


def _parse_jina_response(raw: str) -> Tuple[str, int, int]:
    """
    Strip the Jina metadata header and boilerplate, return clean prose.

    Jina response structure (confirmed from live probing, free tier):
      Title: ...
      (blank)
      URL Source: ...
      (blank)
      Published Time: ...
      (blank)
      Markdown Content:
      <full page body as markdown — nav first, then article>

    Strategy:
      1. Split at 'Markdown Content:' to drop the metadata header.
      2. Walk lines and discard boilerplate (nav bullets, image tags, etc.)
         using _is_boilerplate_line().
      3. Clean markdown syntax from kept lines and return prose.
    """
    marker = "Markdown Content:"
    idx = raw.find(marker)
    body = raw[idx + len(marker):].lstrip("\n") if idx != -1 else raw

    kept = []
    total_lines = 0
    discarded_lines = 0
    for line in body.splitlines():
        total_lines += 1
        if not _is_boilerplate_line(line):
            kept.append(line)
        else:
            discarded_lines += 1

    return _clean_markdown("\n".join(kept)), discarded_lines, total_lines


# ── Jina fetch ────────────────────────────────────────────────────────────────

def _fetch_jina(
    url: str,
    api_key: Optional[str],
    timeout: int,
) -> Tuple[Optional[str], Optional[str], Optional[str], float, int, int]:
    """
    Fetch and extract article text for `url` via Jina AI Reader.

    Uses the free-tier endpoint (no CSS selector headers — those require
    an API key and return HTTP 422 without one). Boilerplate filtering
    is handled in _parse_jina_response() instead.

    Returns:
        (text, None, image_url, fetch_time, discarded_lines, total_lines) on success
        (None, error_str, None, fetch_time, 0, 0)  on failure
    """
    jina_url = f"{JINA_READER_BASE}/{url}"
    headers: Dict[str, str] = {
        "User-Agent": "WeAwareIngestion/1.0 (+Jina Extractor)",
        "Accept": "text/plain",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    request = urllib.request.Request(jina_url, headers=headers)
    start_time = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
        text, discarded, total = _parse_jina_response(raw)
        
        # Additionally fetch the direct URL to scrape the image tag
        image_url = None
        try:
            req_img = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"})
            with urllib.request.urlopen(req_img, timeout=timeout) as res_img:
                html = res_img.read().decode("utf-8", errors="ignore")
                soup = BeautifulSoup(html, "html.parser")
                meta_og = soup.find("meta", property="og:image")
                if meta_og and meta_og.get("content"):
                    image_url = meta_og["content"]
                else:
                    meta_tw = soup.find("meta", attrs={"name": "twitter:image"})
                    if meta_tw and meta_tw.get("content"):
                        image_url = meta_tw["content"]
        except Exception:
            pass
            
        fetch_time = time.perf_counter() - start_time
        return (text or None), None, image_url, fetch_time, discarded, total
    except _NETWORK_ERRORS as exc:
        return None, str(exc), None, time.perf_counter() - start_time, 0, 0
    except Exception as exc:
        return None, f"unexpected: {exc}", None, time.perf_counter() - start_time, 0, 0


# ── Public entry point ────────────────────────────────────────────────────────

def run_extraction(store, request_timeout: int = 15) -> Dict[str, int]:
    """
    Run Stage 1.5 extraction for items pending in the review queue.

    Reads up to WEAWARE_EXTRACT_MAX items from the review_queue, fetches
    their full text via Jina AI, updates items.raw_text and
    items.extraction_status, and marks each review_queue row as
    'resolved' (if text is now ok) or 'failed' (if Jina couldn't help).

    Returns a summary dict suitable for printing.
    """
    if os.getenv("WEAWARE_EXTRACT_ENABLED", "true").lower() == "false":
        return {"enabled": False}

    max_items = int(os.getenv("WEAWARE_EXTRACT_MAX", "1000"))
    delay     = float(os.getenv("WEAWARE_EXTRACT_DELAY", "0.5"))
    api_key   = os.getenv("JINA_API_KEY", "").strip() or None

    items = store.get_pending_extraction_items(limit=max_items)
    if not items:
        return {"attempted": 0, "ok": 0, "still_short": 0, "failed": 0}

    summary = {"attempted": len(items), "ok": 0, "still_short": 0, "failed": 0, "total_jina_time": 0.0, "total_discarded": 0, "total_lines": 0}

    for idx, item in enumerate(items):
        url = item.get("url", "")
        if not url:
            store.resolve_review_item(item["item_hash"], "failed")
            summary["failed"] += 1
            continue

        text, error, image_url, fetch_time, discarded, total = _fetch_jina(url, api_key, request_timeout)
        summary["total_jina_time"] += fetch_time
        summary["total_discarded"] += discarded
        summary["total_lines"] += total

        if error or not text:
            store.resolve_review_item(item["item_hash"], "failed")
            summary["failed"] += 1
        else:
            new_status = _extraction_status(text)
            store.update_item_extraction(item["item_hash"], text, new_status, image_url=image_url)
            queue_resolution = "resolved" if new_status == "ok" else "failed"
            store.resolve_review_item(item["item_hash"], queue_resolution)

            if new_status == "ok":
                summary["ok"] += 1
            else:
                summary["still_short"] += 1

        # Polite rate-limiting — sleep between requests (skip after last)
        if idx < len(items) - 1:
            time.sleep(delay)

    summary["avg_jina_time"] = summary["total_jina_time"] / summary["attempted"] if summary["attempted"] > 0 else 0
    summary["boilerplate_ratio"] = summary["total_discarded"] / summary["total_lines"] if summary["total_lines"] > 0 else 0
    return summary
