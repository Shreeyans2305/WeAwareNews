"""
Story Picker: Evaluates candidate stories from WeAware API and selects
the best candidate based on comedy potential, satire suitability,
and strict safety filtering.
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from video.config.settings import settings
from video.api.models import VideoCandidateResponse

logger = logging.getLogger("weaware-video.picker")


class StoryPickerDecision(BaseModel):
    chosen_story_id: str = Field(description="The story_id of the best candidate for satire")
    one_line_reason: str = Field(description="One line explanation of why this story has the highest comedic potential")
    ranking_order: List[str] = Field(description="Ordered list of candidate story_ids from best to worst")
    rejected_stories: Dict[str, str] = Field(description="Map of rejected story_id to rejection reason (e.g., tragedy, violence)")


_SYSTEM_PROMPT = """You are the Senior Executive Producer for "WeAware Late Night", a satirical comedy news show.
Your role is to pick the single best news story from a list of corroborated news candidates.

EDITORIAL RULES:
1. REJECT ANYTHING TRAGIC OR SENSITIVE:
   - Deaths, casualties, fatal accidents, illness, terminal disease, health scares.
   - Ongoing violent conflict, war casualties, military strikes causing harm.
   - Abuse, assault, domestic violence, human trafficking.
   - Active court cases involving private individuals or criminal trials of non-public figures.
   - Natural disasters with humanitarian impact.
2. LOOK FOR COMEDIC & SATIRICAL HOOKS:
   - Absurd bureaucracy, corporate hubris, bizarre tech announcements, eccentric government policies.
   - Irony, unintended consequences, cultural quirks, over-hyped trends.
   - Corroboration hook: stories where multiple serious outlets (e.g. Reuters, BBC) report on something inherently hilarious or ridiculous.
3. OUTPUT FORMAT:
   Return valid JSON strictly matching the requested schema.
"""


def pick_story(
    candidates: List[VideoCandidateResponse],
    client: Optional[genai.Client] = None,
) -> Tuple[VideoCandidateResponse, StoryPickerDecision, List[VideoCandidateResponse]]:
    """
    Ranks candidates and returns (chosen_candidate, decision_metadata, fallback_candidates).
    """
    if not candidates:
        raise ValueError("No candidates provided to story picker.")

    if len(candidates) == 1:
        # Trivial single candidate
        decision = StoryPickerDecision(
            chosen_story_id=candidates[0].story_id,
            one_line_reason="Single eligible candidate available.",
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
            "sample_text": c.combined_story_text[:600],
        })

    prompt = (
        f"Here are {len(candidates)} corroborated news candidates:\n\n"
        f"{json.dumps(candidates_payload, indent=2)}\n\n"
        "Evaluate each candidate according to the editorial rules. Reject sensitive/tragic topics, "
        "rank the safe candidates by comedic potential, and select the winner."
    )

    resp = client.models.generate_content(
        model=settings.gemini_flash_model,
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
