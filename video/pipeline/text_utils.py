"""
Text utilities for captions and formatting across the WeAware video pipeline.
"""

from typing import List, Optional


def clamp_caption(
    caption: str,
    hashtags: Optional[List[str]] = None,
    ai_disclosure: Optional[str] = None,
    max_total_chars: int = 2200,
    satire_disclosure: Optional[str] = None,
) -> str:
    """
    Clamps social caption so the combined post:
      [caption_body] + [ai_disclosure] + [hashtags]
    strictly stays under or equal to max_total_chars (default 2,200 for Instagram).

    Rules:
    - Truncates caption body ONLY.
    - Never truncates the AI disclosure or hashtags.
    - Truncates cleanly at a word boundary before the budget, appending '...'.
    - Returns the clamped caption body.
    """
    raw_caption = (caption or "").strip()
    clean_disclosure = (ai_disclosure or satire_disclosure or "").strip()
    clean_hashtags = [h.strip() for h in (hashtags or []) if h.strip()]
    hashtags_str = " ".join(clean_hashtags)

    # Overhead for separators (e.g. "\n\n" between sections)
    disclosure_overhead = (len(clean_disclosure) + 2) if clean_disclosure else 0
    hashtags_overhead = (len(hashtags_str) + 2) if hashtags_str else 0
    reserved = disclosure_overhead + hashtags_overhead

    caption_budget = max_total_chars - reserved
    if caption_budget <= 0:
        return ""

    if len(raw_caption) <= caption_budget:
        return raw_caption

    cutoff = caption_budget - 3  # for "..."
    if cutoff <= 0:
        return "..."[:caption_budget]

    truncated = raw_caption[:cutoff]
    last_space = truncated.rfind(" ")
    if last_space > int(cutoff * 0.6):
        truncated = truncated[:last_space]

    return truncated.rstrip() + "..."


def format_full_caption(
    caption: str,
    hashtags: Optional[List[str]] = None,
    ai_disclosure: Optional[str] = None,
    max_total_chars: int = 2200,
    satire_disclosure: Optional[str] = None,
) -> str:
    """
    Formats the complete social post text (caption + disclosure + hashtags),
    ensuring total length <= max_total_chars by truncating caption body only.
    """
    clean_disclosure = (ai_disclosure or satire_disclosure or "").strip()
    clamped_body = clamp_caption(
        caption=caption,
        hashtags=hashtags,
        ai_disclosure=clean_disclosure,
        max_total_chars=max_total_chars,
    )
    parts = []
    if clamped_body:
        parts.append(clamped_body)
    if clean_disclosure:
        parts.append(clean_disclosure)
    if hashtags:
        clean_tags = [h.strip() for h in hashtags if h.strip()]
        if clean_tags:
            parts.append(" ".join(clean_tags))
    return "\n\n".join(parts)
