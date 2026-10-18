"""
Story Picker: ranks corroborated stories for balanced, neutral broadcast coverage.
"""

import json
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from video.config.settings import settings
from video.api.models import VideoCandidateResponse

logger = logging.getLogger("weaware-video.picker")


class StoryPickerDecision(BaseModel):
    chosen_story_id: str = Field(description="The story_id of the best candidate for neutral broadcast coverage")
    one_line_reason: str = Field(description="One-line explanation emphasizing corroboration, balance, and public interest")
    ranking_order: List[str] = Field(description="Ordered list of candidate story_ids from best to worst")
    rejected_stories: Dict[str, str] = Field(description="Map of rejected story_id to rejection reason (e.g., tragedy, violence)")


_SYSTEM_PROMPT = """You are the Senior Executive Producer for "WeAware News", a neutral broadcast news program.
Your role is to pick the single best news story from a list of corroborated news candidates.

EDITORIAL RULES:
1. Prefer stories corroborated by Reuters or the Associated Press plus at least one additional independent outlet.
2. Deprioritize stories whose supplied excerpts contain statements from only one party or perspective.
3. Prefer stories with clearly attributable events, named-person statements, a response or counter-voice, and sourced next steps.
4. Reject candidates that cannot be reported without relying on outlet opinion, inferred motives, or unsupported causal links.
3. OUTPUT FORMAT:
   Return valid JSON strictly matching the requested schema.
"""


def has_wire_service(candidate: VideoCandidateResponse) -> bool:
    for article in candidate.articles:
        name = article.source_name.lower()
        url = article.url.lower()
        if name in {"reuters", "associated press", "ap", "ap news"} or "reuters.com" in url or "apnews.com" in url:
            return True
    return False


def has_multiple_named_perspectives(candidate: VideoCandidateResponse) -> bool:
    text = " ".join(article.excerpt for article in candidate.articles)
    markers = re.findall(r"\b(said|stated|told|according to|responded|wrote)\b", text, re.IGNORECASE)
    return len(markers) >= 2


def pick_story(
    candidates: List[VideoCandidateResponse],
    client: Optional[genai.Client] = None,
    model: Optional[str] = None,
) -> Tuple[VideoCandidateResponse, StoryPickerDecision, List[VideoCandidateResponse]]:
    """
    Ranks candidates and returns (chosen_candidate, decision_metadata, fallback_candidates).
    """
    target_model = model or settings.gemini_flash_model
    if not candidates:
        raise ValueError("No candidates provided to story picker.")

    wire_candidates = [candidate for candidate in candidates if has_wire_service(candidate)]
    if wire_candidates:
        excluded = [candidate.story_id for candidate in candidates if not has_wire_service(candidate)]
        if excluded:
            logger.info("Deprioritized candidates without Reuters/AP corroboration: %s", excluded)
        candidates = wire_candidates
    else:
        logger.warning(
            "WIRE_SERVICE_REQUIREMENT_NOT_MET: none of %s candidates includes Reuters or AP; "
            "continuing only because no wire-backed alternative is available.",
            len(candidates),
        )

    if len(candidates) == 1:
        # Trivial single candidate
        decision = StoryPickerDecision(
            chosen_story_id=candidates[0].story_id,
            one_line_reason=(
                "Single wire-corroborated candidate available."
                if has_wire_service(candidates[0])
                else "Single candidate available; Reuters/AP requirement not met and logged."
            ),
            ranking_order=[candidates[0].story_id],
            rejected_stories={},
        )
        return candidates[0], decision, []

    if client is None:
        client = genai.Client(
            vertexai=True,
            project=settings.project_id,
            location=settings.location,
        )

    # Format candidates for Gemini
    candidates_payload = []
    for c in candidates:
        candidates_payload.append({
            "story_id": c.story_id,
            "headline": c.headline,
            "source_count": c.source_count,
            "sources": [a.source_name for a in c.articles],
            "wire_service_present": has_wire_service(c),
            "multiple_perspectives_signal": has_multiple_named_perspectives(c),
            "sample_text": c.combined_story_text[:600],
        })

    prompt = (
        f"Here are {len(candidates)} corroborated news candidates:\n\n"
        f"{json.dumps(candidates_payload, indent=2)}\n\n"
        "Evaluate each candidate according to the editorial rules. Deprioritize one-sided source sets, "
        "rank candidates by corroboration and balance, and select the strongest neutral report."
    )

    resp = client.models.generate_content(
        model=target_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=StoryPickerDecision,
            temperature=0.2,
        ),
    )

    decision = StoryPickerDecision.model_validate_json(resp.text)
    candidate_map = {c.story_id: c for c in candidates}

    # Structured output validates types, but a model can still omit candidates
    # or repeat IDs. Keep its relative order, then append every missing candidate
    # so valid fallbacks are never silently dropped.
    normalized_ranking: List[str] = []
    for story_id in decision.ranking_order:
        if story_id in candidate_map and story_id not in normalized_ranking:
            normalized_ranking.append(story_id)
    omitted = [candidate.story_id for candidate in candidates if candidate.story_id not in normalized_ranking]
    if omitted:
        logger.warning("Picker ranking omitted %s candidate(s); appending them deterministically: %s", len(omitted), omitted)
        normalized_ranking.extend(omitted)
    decision.ranking_order = normalized_ranking

    # Find the chosen candidate or first ranked that exists
    chosen = candidate_map.get(decision.chosen_story_id)
    if not chosen:
        for sid in decision.ranking_order:
            if sid in candidate_map:
                chosen = candidate_map[sid]
                break

    if not chosen:
        chosen = candidates[0]

    # Prepare fallbacks in order of ranking
    fallbacks = [
        candidate_map[sid]
        for sid in decision.ranking_order
        if sid in candidate_map and sid != chosen.story_id and sid not in decision.rejected_stories
    ]

    logger.info(f"Picked story: {chosen.story_id} ({chosen.headline}) - Reason: {decision.one_line_reason}")
    return chosen, decision, fallbacks
