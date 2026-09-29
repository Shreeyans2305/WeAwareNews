"""
Editor Pass: Second-pass validation using Gemini Pro to verify
factual grounding against source texts, tone, word budget, and safety.
"""

import json
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from video.config.settings import settings
from video.api.models import VideoCandidateResponse
from video.pipeline.scripter import ScriptOutput

logger = logging.getLogger("weaware-video.editor")


class EditorDecision(BaseModel):
    passed: bool = Field(description="True if script meets all editorial, factual, and safety standards")
    factual_distortion_flag: bool = Field(description="True if any claim contradicts or distorts source facts")
    flags: List[str] = Field(description="Specific concerns or issues found (empty if passed)")
    critique_reason: str = Field(description="Detailed editorial assessment")


_EDITOR_SYSTEM_PROMPT = """You are the Standards & Practices Senior Editor for "WeAware Late Night".
Your job is to conduct a strict editorial audit of a proposed 4-clip comedy script against the underlying news source texts.

AUDIT CRITERIA:
1. FACTUAL GROUNDING (ZERO TOLERANCE FOR HALLUCINATION):
   - Every factual claim made in the dialogue must be supported by the provided source articles.
   - Satirical commentary and punchlines are welcome, but the underlying news facts must be accurate.
   - If the script invents fake statistics, quotes, or distorted events, flag `factual_distortion_flag = True` and set `passed = False`.
2. TONE & TARGET:
   - Jokes must punch at ideas, institutions, policies, corporations, and situations.
   - NEVER attack or mock private individuals or protected demographic groups.
3. OUTPUT FORMAT:
   Return valid JSON strictly matching the requested schema.
"""


def edit_script(
    candidate: VideoCandidateResponse,
    script: ScriptOutput,
    client: Optional[genai.Client] = None,
    model: Optional[str] = None,
) -> EditorDecision:
    target_model = model or settings.gemini_flash_model
    if client is None:
        client = genai.Client(
            vertexai=True,
            project=settings.project_id,
            location=settings.location,
        )

    sources_summary = "\n\n".join([
        f"[{a.source_name}] ({a.url}):\n{a.excerpt}"
        for a in candidate.articles
    ])

    script_summary = json.dumps(script.model_dump(), indent=2)

    prompt = (
        f"PROPOSED SCRIPT:\n{script_summary}\n\n"
        f"VERIFIED SOURCE ARTICLES:\n{sources_summary}\n\n"
        "Audit this script against the source texts. Verify factual support for all claims, "
        "check satirical tone, and render your verdict."
    )

    resp = client.models.generate_content(
        model=target_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_EDITOR_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=EditorDecision,
            temperature=0.1,
        ),
    )

    decision = EditorDecision.model_validate_json(resp.text)
    if decision.passed:
        logger.info(f"Editor pass PASSED: {decision.critique_reason}")
    else:
        logger.warning(
            f"Editor pass FAILED (distortion={decision.factual_distortion_flag}): {decision.flags} - {decision.critique_reason}"
        )

    return decision
