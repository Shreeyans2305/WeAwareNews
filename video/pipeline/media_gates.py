"""Fail-closed transcript, word-timing, and prohibited-audio checks."""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Any, List, Optional

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from video.config.settings import settings
from video.pipeline.scripter import generate_content_with_retry, spoken_tokens


class WordTiming(BaseModel):
    word: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(ge=0)


class MediaInspection(BaseModel):
    transcript: str
    word_timestamps: List[WordTiming] = Field(default_factory=list)
    laughter_detected: bool = False
    applause_detected: bool = False
    music_detected: bool = False
    crowd_detected: bool = False
    audio_notes: str = ""


_SMALL_NUMBERS = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
    "eighteen", "nineteen",
]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def _integer_words(value: int) -> list[str]:
    """Return deterministic spoken words for a non-negative integer."""
    if value < 20:
        return [_SMALL_NUMBERS[value]]
    if value < 100:
        return [_TENS[value // 10]] + (_integer_words(value % 10) if value % 10 else [])
    if value < 1_000:
        return _integer_words(value // 100) + ["hundred"] + (_integer_words(value % 100) if value % 100 else [])
    for scale, word in ((1_000_000_000, "billion"), (1_000_000, "million"), (1_000, "thousand")):
        if value >= scale:
            return _integer_words(value // scale) + [word] + (_integer_words(value % scale) if value % scale else [])
    return [str(value)]


def _expand_numeric_token(token: str) -> list[str]:
    normalized = token.replace(",", "")
    if not re.fullmatch(r"\d+(?:\.\d+)?", normalized):
        return [token]
    whole, dot, fraction = normalized.partition(".")
    words = _integer_words(int(whole))
    if dot:
        words.extend(["point", *(_SMALL_NUMBERS[int(digit)] for digit in fraction)])
    return words


def _split_joined_compounds(tokens: list[str], reference: list[str]) -> list[str]:
    """Align harmless transcript compounds such as ``airbase`` with ``air base``."""
    expanded: list[str] = []
    for token in tokens:
        match: list[str] | None = None
        for width in range(2, min(5, len(reference) + 1)):
            for start in range(len(reference) - width + 1):
                candidate = reference[start:start + width]
                if "".join(candidate) == token:
                    match = candidate
                    break
            if match:
                break
        expanded.extend(match or [token])
    return expanded


def _join_split_compounds(tokens: list[str], reference: list[str]) -> list[str]:
    """Align transcript splits such as ``we aware`` with scripted ``WeAware``."""
    joined: list[str] = []
    index = 0
    while index < len(tokens):
        match: str | None = None
        match_width = 1
        for width in range(min(4, len(tokens) - index), 1, -1):
            candidate = "".join(tokens[index:index + width])
            if candidate in reference:
                match = candidate
                match_width = width
                break
        joined.append(match or tokens[index])
        index += match_width
    return joined


def transcript_tokens(text: str, reference: list[str] | None = None) -> list[str]:
    """Canonical tokens for transcript comparison, preserving semantic omissions."""
    tokens: list[str] = []
    for token in spoken_tokens(text):
        tokens.extend(_expand_numeric_token(token.lower().replace("’", "'")))
    reference_tokens = reference or []
    tokens = _split_joined_compounds(tokens, reference_tokens)
    return _join_split_compounds(tokens, reference_tokens)


def inspect_clip_media(
    clip_path: Path,
    scripted_dialogue: str,
    client: Optional[Any] = None,
    model: Optional[str] = None,
) -> dict[str, Any]:
    """Inspect one generated clip and return a fail-closed media-gate result."""
    if client is None:
        client = genai.Client(vertexai=True, project=settings.project_id, location=settings.location)
    target_model = model or settings.gemini_flash_model
    response = generate_content_with_retry(
        client,
        model=target_model,
        contents=[
            types.Part.from_bytes(data=clip_path.read_bytes(), mime_type="video/mp4"),
            (
                "Inspect the audio track. Transcribe only the presenter's spoken words verbatim and provide a start and "
                "end time in seconds for every spoken word. Independently detect any audible laughter, applause, music, "
                "or crowd noise, including faint background instances. Do not infer from visuals. Return the requested JSON."
            ),
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=MediaInspection,
            temperature=0.0,
        ),
    )
    inspection = MediaInspection.model_validate_json(response.text)
    expected = transcript_tokens(scripted_dialogue)
    heard = transcript_tokens(inspection.transcript, reference=expected)
    matcher = difflib.SequenceMatcher(None, expected, heard)
    prohibited = {
        "laughter": inspection.laughter_detected,
        "applause": inspection.applause_detected,
        "music": inspection.music_detected,
        "crowd": inspection.crowd_detected,
    }
    speech_end = max((word.end_seconds for word in inspection.word_timestamps), default=0.0)
    ratio = matcher.ratio()
    return {
        **inspection.model_dump(),
        "scripted": scripted_dialogue,
        "match_ratio": round(ratio, 4),
        "transcript_passed": ratio >= 0.90,
        "audio_passed": not any(prohibited.values()),
        "prohibited_audio": [name for name, detected in prohibited.items() if detected],
        "speech_end_seconds": speech_end,
    }
