"""
Image URL validation for the WeAware ingestion pipeline.

Filters out non-editorial images that would spoil Instagram posts:
  - Bluesky profile avatars (news org logos masquerading as article images)
  - Site logos, favicons, and brand assets
  - Generic placeholders and default images
  - Tiny images (tracking pixels, icons)

Usage:
    from ingestion.image_filter import is_valid_editorial_image

    if is_valid_editorial_image(url):
        item["image_url"] = url
"""

import re
from typing import Optional
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Blocklist patterns — URL substrings / regexes that indicate non-editorial images
# ---------------------------------------------------------------------------

# Exact substring matches (case-insensitive) — fast first pass
_BLOCKLIST_SUBSTRINGS = (
    # Bluesky profile avatars — the #1 offender
    "avatar_thumbnail",
    "avatar/plain",
    "/img/avatar",
    # Generic non-editorial patterns
    "/favicon",
    "/brand/",
    "/branding/",
    "placeholder",
    "no-image",
    "noimage",
    "default-image",
    "default_image",
    "fallback-image",
    "fallback_image",
    "generic-image",
    "site-logo",
    "site_logo",
    "header-logo",
    "header_logo",
    "nav-logo",
    "nav_logo",
    "company-logo",
    "company_logo",
    # Tracking pixels and beacons
    "/pixel",
    "/beacon",
    "/track",
    "1x1",
    # Social media profile pictures (not post content)
    "/profile_images/",
    "/profile_banners/",
    "/default_profile",
    # TOI's resize URL exposes its embedded publisher badge in this marker.
    "overlay-toi",
)

# Regex patterns for more nuanced matching
_BLOCKLIST_REGEXES = [
    # Pure logo filenames — match "logo" as a distinct word in the filename
    # but NOT in path segments like "/logos-in-article.jpg"
    re.compile(r"/[^/]*\blogo\b[^/]*\.(jpe?g|png|gif|svg|webp)", re.IGNORECASE),
    # Icon files (standalone, not part of article content)
    re.compile(r"/[^/]*\bicon\b[^/]*\.(jpe?g|png|gif|svg|webp|ico)", re.IGNORECASE),
    # Very small declared dimensions in URL params (tracking pixels, tiny icons)
    # Matches patterns like width=32, w=16, height=1, h=1
    re.compile(r"[?&](width|w|height|h)=(1|[2-9]|[1-5]\d)\b", re.IGNORECASE),
    # Tiny image dimensions in path (e.g., /32x32/, /1x1/)
    re.compile(r"/(\d{1,2})x(\d{1,2})/"),
]


# ---------------------------------------------------------------------------
# Allowlist — known editorial photo CDNs that should never be blocked
# (even if their URLs happen to match a blocklist pattern, e.g. CBC's
#  "default.jpg" is actually a real photo with a misleading path segment)
# ---------------------------------------------------------------------------

_ALLOWLIST_DOMAINS = {
    # Major news photo CDNs — images from these are almost always editorial
    "ichef.bbci.co.uk",          # BBC
    "images.indianexpress.com",  # Indian Express
    "i.cbc.ca",                  # CBC News
    "npr.brightspotcdn.com",     # NPR
    "media.zenfs.com",           # Yahoo News
    "dims.apnews.com",           # AP
    "s.yimg.com",                # Yahoo
    "c.files.bbci.co.uk",        # BBC files
    "image.cnbcfm.com",          # CNBC
}

# Domains whose og:image is frequently a logo / site branding, not editorial
_LOGO_PRONE_DOMAINS = {
    "cdn.bsky.app",  # Bluesky — og:image is always the poster's profile pic
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_valid_editorial_image(url: Optional[str]) -> bool:
    """
    Return True if `url` appears to be a real editorial/news photograph
    suitable for use in an Instagram post.

    Return False for logos, avatars, favicons, placeholders, tracking
    pixels, and other non-editorial images.

    Returns False for None or empty strings.
    """
    if not url or not url.strip():
        return False

    url_lower = url.lower()

    # Fast-path: check domain allowlist first
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
    except Exception:
        return False

    # If the domain is in the allowlist, skip blocklist checks
    # (CBC images have "default.jpg" in the path but they're real photos)
    if hostname in _ALLOWLIST_DOMAINS:
        return True

    # If the domain is known to serve logos as og:image, reject
    if hostname in _LOGO_PRONE_DOMAINS:
        return False

    # Check substring blocklist (fast)
    for pattern in _BLOCKLIST_SUBSTRINGS:
        if pattern in url_lower:
            return False

    # Check regex blocklist (slower, but more precise)
    for regex in _BLOCKLIST_REGEXES:
        if regex.search(url):
            return False

    # Passed all checks — assume it's a valid editorial image
    return True
