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

_EDITOR_SYSTEM_PROMPT_STRICT = """You are the Standards & Practices Senior Editor for "WeAware Late Night".
Your job is to conduct a strict, adversarial editorial audit of a proposed 4-clip comedy script against the underlying news source texts.
NOTE: Strict fallback audit mode is ACTIVE. Because a fallback model is running the fact-check safety gate, you must perform an explicit claim-by-claim check against the source text.

AUDIT CRITERIA (STRICT CLAIM-BY-CLAIM FALLBACK MODE):
1. EXPLICIT CLAIM-BY-CLAIM CHECK AGAINST SOURCE TEXT:
   - Check every single claim in the `claims` list and every assertion in the dialogue individually against the provided source articles.
   - Every factual assertion must have direct, verifiable textual support in the source texts.
   - If any claim, statistic, quote, name, or detail lacks explicit corroboration in the source text, or extrapolates beyond the reported facts, you MUST set `factual_distortion_flag = True` and `passed = False`.
   - List each failed or uncorroborated claim specifically in `flags` and explain the exact issue in `critique_reason`.
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
    is_fallback: bool = False,
) -> EditorDecision:
    if model is None:
        try:
            from video.config.model_selector import select_model
            pro_sel = select_model("pro")
            target_model = pro_sel.model_id
            if pro_sel.reason == "pro_unavailable_flash_fallback":
                is_fallback = True
        except Exception:
            target_model = settings.gemini_pro_model
    else:
        target_model = model

    if client is None:
        client = genai.Client(
            vertexai=True,
            project=settings.project_id,
            location=settings.location,
        )

    sources_summary = "\n\n".join([
        f"[{a.source_name}] ({a.url}) - Title: {a.title}\n{a.excerpt}"
        for a in candidate.articles
    ])

    script_summary = json.dumps(script.model_dump(), indent=2)

    if is_fallback:
        prompt = (
            f"PROPOSED SCRIPT:\n{script_summary}\n\n"
            f"VERIFIED SOURCE ARTICLES:\n{sources_summary}\n\n"
            "STRICT CLAIM-BY-CLAIM AUDIT INSTRUCTION: Conduct an explicit claim-by-claim verification of every dialogue line and claim against the source text. "
            "Examine each asserted fact individually. If any detail is uncorroborated by the sources, reject immediately (passed=False, factual_distortion_flag=True). "
            "Render your verdict."
        )
        system_instruction = _EDITOR_SYSTEM_PROMPT_STRICT
        logger.info(f"Running Editor pass in STRICT CLAIM-BY-CLAIM FALLBACK mode with model={target_model}...")
    else:
        prompt = (
            f"PROPOSED SCRIPT:\n{script_summary}\n\n"
            f"VERIFIED SOURCE ARTICLES:\n{sources_summary}\n\n"
            "Audit this script against the source texts. Verify factual support for all claims, "
            "check satirical tone, and render your verdict."
        )
        system_instruction = _EDITOR_SYSTEM_PROMPT
        logger.info(f"Running Editor pass with model={target_model}...")

    resp = client.models.generate_content(
        model=target_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
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
