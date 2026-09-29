"""
Script Generator: Generates strict Pydantic JSON scripts grounded entirely
in WeAware news items, validates word budget, maps claims to source URLs,
and builds Veo prompts from code templates.
"""

import json
import logging
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
from google import genai
from google.genai import types

from video.config.settings import settings
from video.api.models import VideoCandidateResponse

logger = logging.getLogger("weaware-video.scripter")


class ClaimItem(BaseModel):
    claim_text: str = Field(description="Exact factual statement made in the dialogue")
    source_url: str = Field(description="The source URL from the provided text verifying this fact")


class ClipScript(BaseModel):
    clip_index: int = Field(description="1-based index (1 to 4)")
    duration_seconds: int = Field(description="Duration in seconds (default 8)")
    speaker: str = Field(description="Anchor id: 'marcus' (Host) or 'maya' (Correspondent)")
    dialogue: str = Field(description="The spoken dialogue line, in quotes, under the word budget")
    action: str = Field(description="Physical comedic reaction or gesture at the desk")
    camera: str = Field(description="Camera framing: 'Medium close-up shot' or 'Wide desk shot'")
    claims: List[ClaimItem] = Field(description="List of factual claims asserted in this dialogue")


class ScriptOutput(BaseModel):
    headline: str = Field(description="Punchy satirical headline")
    caption: str = Field(description="Social caption under 2,200 chars including source attribution")
    hashtags: List[str] = Field(description="3 to 5 relevant hashtags")
    satire_disclosure: str = Field(description="Mandatory AI satire disclosure")
    clips: List[ClipScript] = Field(description="Exact 4-clip script plan")


_SCRIPTER_SYSTEM_PROMPT = """You are the Lead Writer for "WeAware Late Night", a vertical 9:16 broadcast comedy news show.
Write a 4-clip satirical news script grounded 100% in the provided verified news facts.

STRICT GROUNDING RULES:
1. Every factual statement made in the dialogue MUST come directly from the provided source articles.
2. DO NOT hallucinate facts, statistics, names, or quotes from your internal memory.
3. Every factual assertion must be cited in the `claims` list with its matching source_url.
4. Editorial voice: Punch UP at systems, corporate PR, bureaucracy, and absurd situations. Never punch at private individuals or marginalized groups.
5. Refer to public figures by title/role rather than personal attacks.

CLIP STRUCTURE (Exactly 4 clips, 8 seconds each = 32s total):
- Clip 1 (8s, speaker: "marcus"): Hook + The headline. The corroboration hook (e.g. "Reuters and BBC both confirm...").
- Clip 2 (8s, speaker: "marcus"): Setup / The most absurd factual detail.
- Clip 3 (8s, speaker: "maya"): Escalation / Punchline cut to senior satirical correspondent Maya Lin.
- Clip 4 (8s, speaker: "marcus"): Sign-off, punchy kicker, and brand tagline ("Corroborated news, satirical conclusions").

WORD BUDGET RULE (CRITICAL FOR LIP-SYNC & PACING):
- Pacing budget is ~2.5 words per second.
- For an 8-second clip, the dialogue MUST be between 16 and 22 words MAXIMUM.
- Keep lines concise, snappy, and comedic.
"""


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def validate_and_trim_word_budget(script: ScriptOutput, words_per_sec: float = 2.5) -> bool:
    """
    Validates word count per clip. Returns True if all clips pass.
    """
    passed = True
    for clip in script.clips:
        w_count = count_words(clip.dialogue)
        max_allowed = int(clip.duration_seconds * words_per_sec) + 2
        if w_count > max_allowed:
            logger.warning(
                f"Clip {clip.clip_index} exceeds word budget: {w_count} words (max {max_allowed}). Dialogue: '{clip.dialogue}'"
            )
            passed = False
    return passed


def generate_script(
    candidate: VideoCandidateResponse,
    client: Optional[genai.Client] = None,
    anchors_config: Optional[Dict[str, Any]] = None,
) -> ScriptOutput:
    if client is None:
        client = genai.Client(
            vertexai=True,
            project=settings.project_id,
            location=settings.location,
        )

    # Prepare grounding context
    sources_text = ""
    for idx, art in enumerate(candidate.articles, start=1):
        sources_text += f"\nSOURCE {idx} ({art.source_name}) - URL: {art.url}\nTitle: {art.title}\nExcerpt:\n{art.excerpt}\n"

    user_prompt = (
        f"STORY HEADLINE: {candidate.headline}\n"
        f"VERIFIED SOURCE ARTICLES:\n{sources_text}\n\n"
        f"Write the 4-clip script adhering strictly to the ~20-word budget per 8s clip, "
        f"and map every claim to its source URL."
    )

    # Up to 2 attempts for strict word budget adherence
    for attempt in range(2):
        resp = client.models.generate_content(
            model=settings.gemini_flash_model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SCRIPTER_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=ScriptOutput,
                temperature=0.3,
            ),
        )

        script = ScriptOutput.model_validate_json(resp.text)
        if validate_and_trim_word_budget(script, settings.words_per_second):
            logger.info(f"Script generated successfully on attempt {attempt + 1}")
            return script
        else:
            logger.info("Script slightly over word budget; requesting tightening...")
            user_prompt += "\n\nNOTE: Prior attempt exceeded word limits. Keep all clips under 20 words!"

    return script


def assemble_veo_prompt(
    clip: ClipScript,
    anchors_config: Dict[str, Any],
) -> str:
    """
    Assembles the final Veo prompt strictly from code templates.
    Template:
      [SHOT/CAMERA] + [SET DESCRIPTION] + [ANCHOR DESCRIPTION] + [ACTION] +
      Dialogue: "<line>" + [VOICE NOTE] + [STYLE]
    """
    set_desc = anchors_config.get("set", {}).get("description", "Late-night satirical newsroom desk, modern studio.")

    # Find speaker config
    anchors = {a["id"]: a for a in anchors_config.get("anchors", [])}
    anchor = anchors.get(clip.speaker, anchors.get("marcus", {}))

    anchor_name = anchor.get("name", "Marcus Vance")
    anchor_desc = anchor.get("description", "Late night news anchor in suit.")
    voice_note = anchor.get("voice_description", "Broadcast delivery.")

    # Clean dialogue
    dialogue_clean = clip.dialogue.strip().strip('"').strip("'")

    prompt = (
        f"{clip.camera} of {anchor_name} in the late night talk show studio. "
        f"{set_desc} {anchor_desc} "
        f"{clip.action}. He speaks aloud clearly with broadcast comedic timing: \"{dialogue_clean}\" "
        f"Voice style: {voice_note} "
        f"Broadcast quality television production, vertical 9:16 framing, synchronized lip-sync, "
        f"no subtitles, no watermarks, no on-screen text."
    )
    return prompt
