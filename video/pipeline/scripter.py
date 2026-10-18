"""
Script Generator: Generates strict Pydantic JSON scripts for WeAware News.
Enforces neutral broadcast news register, calm pacing, word budget limits,
explicit source attributions, and structured claim mapping.
"""

import json
import logging
import re
import time
from typing import List, Dict, Any, Optional, Literal, Tuple
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from video.config.settings import settings
from video.api.models import VideoCandidateResponse
from video.pipeline.text_utils import clamp_caption

logger = logging.getLogger("weaware-video.scripter")


def generate_content_with_retry(client: genai.Client, **kwargs):
    """Retry transient Vertex quota/server failures without relaxing validation."""
    for attempt in range(3):
        try:
            return client.models.generate_content(**kwargs)
        except Exception as exc:
            transient = any(marker in str(exc) for marker in ("429", "500", "RESOURCE_EXHAUSTED", "INTERNAL"))
            if not transient or attempt == 2:
                raise
            delay = 2 ** (attempt + 1)
            logger.warning("Transient model error; retrying in %s seconds (attempt %s/3)", delay, attempt + 2)
            time.sleep(delay)


class ScriptRejected(RuntimeError):
    """Raised when deterministic script requirements fail after all retries."""


class StoryIneligible(RuntimeError):
    """Raised when the source ledger cannot support a balanced neutral report."""


ClaimType = Literal["reported_event", "named_person_statement", "outlet_characterization"]


class ClaimLedgerEntry(BaseModel):
    claim_id: str = Field(description="Stable short identifier such as C1")
    claim_text: str = Field(description="Atomic neutral description of the sourced claim")
    source_outlet: str
    source_url: str
    source_snippet: str = Field(description="Short verbatim snippet copied from the supplied source excerpt")
    claim_type: ClaimType
    named_person: Optional[str] = Field(default=None, description="Full title and name for a named-person statement")
    is_response: bool = Field(default=False, description="True when this is a response or materially different party's statement")
    causal_link_explicit: bool = Field(default=False, description="True only when the source explicitly states a causal link between events")


class ClaimLedger(BaseModel):
    entries: List[ClaimLedgerEntry]
    has_counter_voice: bool = Field(description="Whether sources contain a response or materially different party's statement")
    balance_note: str = Field(description="Short explanation of the available response/counter-voice evidence")


class ClaimItem(BaseModel):
    claim_text: str = Field(description="Exact factual statement made in the dialogue")
    source_url: str = Field(description="The source URL from the provided text verifying this fact")
    ledger_id: str = Field(default="", description="claim_id of the supporting claim-ledger entry")


class ClipScript(BaseModel):
    clip_index: int = Field(description="1-based index (1 to 4)")
    duration_seconds: int = Field(default=8, description="Duration in seconds (default 8)")
    speaker: str = Field(description="Anchor id: 'marcus' (Lead Anchor) or 'maya' (Co-Anchor)")
    dialogue: str = Field(description="Spoken broadcast news line with calm pacing and explicit source attribution, under word budget")
    action: str = Field(description="Professional anchor posture: upright, neutral/serious expression, measured minimal gestures, steady eye contact with camera")
    camera: str = Field(description="Camera framing: 'Medium close-up shot' or 'Wide desk shot'")
    claims: List[ClaimItem] = Field(default_factory=list, description="List of factual claims asserted in this dialogue")


class ScriptOutput(BaseModel):
    headline: str = Field(description="Neutral, descriptive broadcast news headline with no editorial angle or sensationalism")
    caption: str = Field(description="Social caption under 2,200 chars including source attribution")
    hashtags: List[str] = Field(description="3 to 5 news-appropriate hashtags (e.g. #News #WorldNews and topic tags; NEVER satire or comedy tags)")
    ai_disclosure: str = Field(
        default="Presenters and visuals are AI-generated.",
        description="Mandatory AI disclosure statement: 'Presenters and visuals are AI-generated. Report based on {sources}.'",
    )
    clips: List[ClipScript] = Field(description="Exact 4-clip broadcast news script plan")
    claim_ledger: List[ClaimLedgerEntry] = Field(default_factory=list, description="Immutable source claim ledger used to write the script")

    def __init__(self, **data):
        if "satire_disclosure" in data and "ai_disclosure" not in data:
            data["ai_disclosure"] = data["satire_disclosure"]
        super().__init__(**data)

    @property
    def satire_disclosure(self) -> str:
        """Backward-compatible alias for ai_disclosure."""
        return self.ai_disclosure


_SCRIPTER_SYSTEM_PROMPT = """You are the Senior Broadcast News Writer for "WeAware News", an objective, straight broadcast television news program.
Write a 4-clip television news report using ONLY the supplied claim ledger.

CORE EDITORIAL REGISTER (STRICT NEUTRALITY & OBJECTIVITY):
1. ABSOLUTELY NO JOKES, SATIRE, SARCASM, IRONY, PUNCHLINES, RHETORICAL QUESTIONS, OR OPINIONS.
2. NO "PUNCHING UP", NO EDITORIALIZING, NO SNARK, AND NO PERSONAL COMMENTARY.
3. REMOVE ALL "LATE NIGHT / DAILY SHOW" FRAMING, STRUCTURE NAMES, AND COMEDIC LANGUAGE EVERYWHERE.
4. STRICT SOURCE ATTRIBUTION:
   - Attribute every major factual claim to its source (e.g. "according to The Guardian", "Reuters reported", "The Associated Press reported", "officials told BBC").
   - Quote or paraphrase officials and spokespeople using the neutral verb "said", "stated", or "reported".
   - NEVER use loaded, dramatic, or judgmental verbs such as "admitted", "slammed", "blasted", "claimed", "conceded", "lashed out", or "boasted".
   - DO NOT use loaded adjectives, sensational descriptors, speculation, or predictions beyond what sources report.
   - DO NOT characterize motives, feelings, or psychology of public figures.
   - Every claims[] item MUST contain the supporting ledger entry's claim_id in ledger_id.
   - Use only ledger entries typed reported_event or named_person_statement. Never use outlet_characterization, even with attribution.
   - A named person's statement may appear only as a short verbatim quote or a neutral paraphrase using "said", and must name that person with title and full name every time it appears.
   - Never replace "said" with characterization verbs such as "condemned", "criticized", "attacked", "praised", or "welcomed" unless those exact words are inside a short direct quote.
   - Do not say an action was a purchase, sanction change, agreement, attack, response, or other materially different action unless the ledger entry says exactly that.
5. BALANCED REPORTING:
   - Where sources conflict, report the conflicting accounts neutrally and attribute each version to its respective source.
   - If sources do not support a fact, leave it out entirely. Do NOT extrapolate or infer unstated facts.
   - Include at least one ledger entry marked is_response=true when one exists.
   - Do not juxtapose events with "after", "following", "the next day", "amid", or similar language in a way that implies a link unless causal_link_explicit=true.
6. HEADLINE:
   - Neutral and descriptive, with no editorial angle, puns, or sensationalism.

CLIP STRUCTURE (Exactly 4 clips, 8 seconds each = 32s total):
- Clip 1 (8s, speaker: "marcus"): Lead: who, what, where, and when. State the verified breaking news event with primary attribution.
- Clip 2 (8s, speaker: "marcus"): Key details and figures. Specific corroborated numbers, dates, locations, or formal official statements.
- Clip 3 (8s, speaker: "maya"): Context and reactions. Other sides, official responses, or broader context, with each perspective attributed.
- Clip 4 (8s, speaker: "marcus"): Include what happens next only if the ledger supports it; otherwise omit it. End with: "Reporting for WeAware News, I'm Marcus Vance."

LEAD RULE:
- The first sentence must be explicitly attributed, or be a plain verifiable event that includes a date and place.

WORD BUDGET & PACING (CRITICAL FOR CALM BROADCAST DELIVERY):
- Pacing budget is ~2.5 words per second.
- For each 8-second clip, dialogue MUST be between 16 and 22 words MAXIMUM (hard ceiling: 22 words per clip, 88 words maximum across all 4 clips).
- Maintain a calm, measured broadcast delivery cadence.

PRONUNCIATION-SAFE BROADCAST RULES:
1. Use clear, accessible words suitable for standard broadcast speech.
2. Avoid convoluted phrasing, tongue-twisters, technical jargon, and obscure acronyms.
3. ALWAYS write numbers as spoken words (e.g. "twenty-five", "one point two million", "fifteen percent").
4. Never include letter-spelling hints or bracketed pronunciation in dialogue.

HASHTAGS & DISCLOSURE:
- Hashtags: 3 to 5 news-appropriate hashtags only (e.g. #News #WorldNews plus relevant topic tags like #Diplomacy #Geopolitics). NEVER include #Satire, #LateNight, #Comedy, or entertainment hashtags.
- AI Disclosure: Mandatory format: "Presenters and visuals are AI-generated. Report based on {sources}." (insert the comma-separated names of the provided sources).
"""


_SPOKEN_TOKEN_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?|\d+(?:[.,]\d+)*")


def spoken_tokens(text: str) -> List[str]:
    """Tokenize dialogue the same way for pacing, captions, and transcript checks."""
    return _SPOKEN_TOKEN_RE.findall(text or "")


def count_words(text: str) -> int:
    # Hyphenated number words count as separately spoken words: twenty-five -> two.
    return len(spoken_tokens(text))


def dialogue_number_violations(script: ScriptOutput) -> List[str]:
    return [
        f"clip {clip.clip_index} contains numeric digits: {clip.dialogue!r}"
        for clip in script.clips
        if re.search(r"\d", clip.dialogue)
    ]


def word_budget_details(script: ScriptOutput, words_per_sec: float = 2.5) -> List[Tuple[int, int, int]]:
    return [
        (clip.clip_index, count_words(clip.dialogue), int(clip.duration_seconds * words_per_sec) + 2)
        for clip in script.clips
    ]


def validate_and_trim_word_budget(script: ScriptOutput, words_per_sec: float = 2.5) -> bool:
    """
    Validates word count per clip. Returns True if all clips pass.
    """
    details = word_budget_details(script, words_per_sec)
    total_words = sum(count for _, count, _ in details)
    passed = True
    for clip_index, w_count, max_allowed in details:
        if w_count > max_allowed:
            logger.warning(
                f"Clip {clip_index} exceeds word budget: {w_count} words (max {max_allowed})."
            )
            passed = False
    if total_words > 88:
        logger.warning(f"Script total word count exceeds 88: {total_words} words.")
        passed = False
    return passed


_LEDGER_SYSTEM_PROMPT = """You extract a strict claim ledger from only the supplied article excerpts.
Split material into atomic claims and copy a short verbatim supporting snippet for each.
Classify every entry as exactly one of:
- reported_event: an event the outlet reports as having occurred;
- named_person_statement: a direct quote or an explicit statement introduced by neutral reporting language such as said, stated, told, or wrote, with title and full name in named_person;
- outlet_characterization: the outlet's framing, characterization, analysis, opinion, loaded description, or inferred motive.
Do not convert outlet characterization into an event or named-person statement. Phrases such as "blaming the victim", "betrayed", "rewarded", "furious", "condemned", or causal analysis belong in outlet_characterization unless they are a named person's short verbatim quote.
Set is_response=true only for a response from a materially different party than the main actor in the reported event. A later statement by the same main actor is not a counter-voice. Set causal_link_explicit=true only if the excerpt explicitly asserts causation, not merely chronology such as "after" or "the next day".
Snippets must be verbatim substrings of the supplied excerpt. Return only the requested JSON schema."""


def extract_claim_ledger(
    candidate: VideoCandidateResponse,
    client: genai.Client,
    model: str,
) -> ClaimLedger:
    source_payload = [article.model_dump() for article in candidate.articles]
    resp = generate_content_with_retry(
        client,
        model=model,
        contents=(
            "Extract the atomic claim ledger from these source excerpts. Preserve material distinctions such as "
            "purchase versus easing sanctions, and identify responses from other parties.\n\n"
            + json.dumps(source_payload, indent=2)
        ),
        config=types.GenerateContentConfig(
            system_instruction=_LEDGER_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=ClaimLedger,
            temperature=0.0,
        ),
    )
    return ClaimLedger.model_validate_json(resp.text)


def validate_story_eligibility(ledger: ClaimLedger) -> None:
    allowed = [entry for entry in ledger.entries if entry.claim_type in ("reported_event", "named_person_statement")]
    if not allowed:
        raise StoryIneligible("Claim ledger contains no usable reported events or named-person statements")
    usable_responses = [entry for entry in allowed if entry.is_response]
    if not ledger.has_counter_voice or not usable_responses:
        raise StoryIneligible(f"No counter-voice in source excerpts: {ledger.balance_note}")


def deterministic_script_violations(script: ScriptOutput, ledger: ClaimLedger) -> List[str]:
    violations: List[str] = []
    ledger_map = {entry.claim_id: entry for entry in ledger.entries}
    used_ids: set[str] = set()

    if len(script.clips) != 4:
        violations.append(f"expected exactly four clips, received {len(script.clips)}")
    if not validate_and_trim_word_budget(script, settings.words_per_second):
        for index, count, maximum in word_budget_details(script, settings.words_per_second):
            if count > maximum:
                violations.append(f"clip {index} has {count} words; maximum is {maximum}")
        total = sum(count for _, count, _ in word_budget_details(script, settings.words_per_second))
        if total > 88:
            violations.append(f"script has {total} words; maximum is 88")
    violations.extend(dialogue_number_violations(script))

    for clip in script.clips:
        for claim in clip.claims:
            entry = ledger_map.get(claim.ledger_id)
            if entry is None:
                violations.append(f"clip {clip.clip_index} claim has no matching ledger entry: {claim.claim_text}")
                continue
            used_ids.add(entry.claim_id)
            if entry.claim_type == "outlet_characterization":
                violations.append(f"clip {clip.clip_index} uses prohibited outlet characterization {entry.claim_id}")
            if entry.claim_type == "named_person_statement" and entry.named_person:
                if entry.named_person.lower() not in clip.dialogue.lower():
                    violations.append(
                        f"clip {clip.clip_index} does not name {entry.named_person} with title and full name for {entry.claim_id}"
                    )
            if claim.source_url != entry.source_url:
                violations.append(f"clip {clip.clip_index} source URL does not match ledger entry {entry.claim_id}")
            claim_lower = claim.claim_text.lower()
            ledger_lower = entry.claim_text.lower()
            purchase_terms = ("purchase", "purchased", "buy", "bought")
            sanctions_terms = ("sanction", "sanctions", "eased", "lifted")
            if any(term in claim_lower for term in purchase_terms) and not any(term in ledger_lower for term in purchase_terms):
                violations.append(f"clip {clip.clip_index} changes {entry.claim_id} into a purchase")
            if any(term in claim_lower for term in sanctions_terms) and not any(term in ledger_lower for term in sanctions_terms):
                violations.append(f"clip {clip.clip_index} changes {entry.claim_id} into a sanctions action")

        causal_markers = ("the day after", "the next day", "following", "after ", "amid ", "therefore", "as a result")
        if any(marker in clip.dialogue.lower() for marker in causal_markers):
            referenced = [ledger_map.get(claim.ledger_id) for claim in clip.claims]
            if referenced and not any(entry and entry.causal_link_explicit for entry in referenced):
                violations.append(f"clip {clip.clip_index} implies a causal link not explicit in the ledger")
        loaded_statement_verbs = ("condemned", "criticized", "attacked", "praised", "welcomed")
        for verb in loaded_statement_verbs:
            if re.search(rf"\b{verb}\b", clip.dialogue, re.IGNORECASE):
                violations.append(f"clip {clip.clip_index} uses non-neutral statement verb: {verb}")

    response_ids = {entry.claim_id for entry in ledger.entries if entry.is_response and entry.claim_type != "outlet_characterization"}
    if response_ids and not (used_ids & response_ids):
        violations.append("script omits the available response or counter-voice")
    return violations


def generate_script(
    candidate: VideoCandidateResponse,
    client: Optional[genai.Client] = None,
    anchors_config: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
    ledger: Optional[ClaimLedger] = None,
) -> ScriptOutput:
    target_model = model or settings.gemini_pro_model
    if client is None:
        client = genai.Client(
            vertexai=True,
            project=settings.project_id,
            location=settings.location,
        )

    if ledger is None:
        ledger = extract_claim_ledger(candidate, client, target_model)
    validate_story_eligibility(ledger)

    source_names_list = []
    for art in candidate.articles:
        if art.source_name and art.source_name not in source_names_list:
            source_names_list.append(art.source_name)

    sources_str = ", ".join(source_names_list) if source_names_list else "corroborated sources"
    expected_disclosure = f"Presenters and visuals are AI-generated. Report based on {sources_str}."

    user_prompt = (
        f"STORY HEADLINE: {candidate.headline}\n"
        f"APPROVED CLAIM LEDGER (outlet_characterization entries are context-only and MUST NOT be used):\n{ledger.model_dump_json(indent=2)}\n\n"
        f"Write a neutral, objective 4-clip broadcast news script adhering strictly to the ~20-word budget per 8s clip (88 words max total). "
        f"Map every factual assertion to its source URL. "
        f"Use disclosure: \"{expected_disclosure}\". "
        f"Use news-appropriate hashtags only."
    )

    last_violations: List[str] = []
    for attempt in range(3):
        logger.info(f"Generating neutral news script with {target_model} (attempt {attempt + 1})...")
        resp = generate_content_with_retry(
            client,
            model=target_model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=_SCRIPTER_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=ScriptOutput,
                temperature=0.2,
            ),
        )

        script = ScriptOutput.model_validate_json(resp.text)
        script.claim_ledger = ledger.entries
        # Ensure correct disclosure format
        if not script.ai_disclosure or "AI-generated" not in script.ai_disclosure:
            script.ai_disclosure = expected_disclosure

        script.caption = clamp_caption(script.caption, script.hashtags, script.ai_disclosure, 2200)
        last_violations = deterministic_script_violations(script, ledger)
        if not last_violations:
            logger.info(f"Script generated successfully on attempt {attempt + 1}")
            return script
        counts = ", ".join(
            f"clip {index}: {count} words (max {maximum})"
            for index, count, maximum in word_budget_details(script, settings.words_per_second)
        )
        logger.warning("Draft rejected deterministically on attempt %s: %s", attempt + 1, last_violations)
        user_prompt += (
            f"\n\nREJECTED DRAFT FEEDBACK FOR ATTEMPT {attempt + 2}: Exact counts were {counts}. "
            f"Correct every issue: {json.dumps(last_violations)}. Return a fully new compliant draft."
        )

    raise ScriptRejected("Script rejected after 3 attempts: " + "; ".join(last_violations))


def assemble_veo_prompt(
    clip: ClipScript,
    anchors_config: Dict[str, Any],
) -> str:
    """
    Assembles the final Veo prompt strictly from code templates for neutral broadcast news.
    Template:
      [SHOT/CAMERA] + [SET DESCRIPTION] + [ANCHOR DESCRIPTION] + [ACTION] +
      Dialogue: "<line>" + [VOICE NOTE] + [AUDIO DIRECTION] + [STYLE]
    """
    set_desc = anchors_config.get("set", {}).get(
        "description",
        "Broadcast newsroom television studio with warm curved anchor desk, soft professional studio lighting, blurred newsroom with monitors in deep background.",
    )

    # Find speaker config
    anchors = {a["id"]: a for a in anchors_config.get("anchors", [])}
    anchor = anchors.get(clip.speaker, anchors.get("marcus", {}))

    anchor_name = anchor.get("name", "Marcus Vance")
    anchor_desc = anchor.get(
        "description",
        "Professional television news anchor in business attire, upright posture, neutral serious expression, steady eye contact with camera.",
    )
    voice_note = anchor.get("voice_description", "Calm measured broadcast articulation, neutral news cadence.")

    # Clean dialogue
    dialogue_clean = clip.dialogue.strip().strip('"').strip("'")

    audio_direction = "quiet newsroom room tone only, no laughter, no applause, no audience, no music, no sound effects, only the presenter's voice"

    prompt = (
        f"{clip.camera} of {anchor_name} seated at the anchor desk in the WeAware News television studio. "
        f"{set_desc} {anchor_desc} "
        f"{clip.action}. The presenter speaks aloud clearly with calm broadcast delivery: \"{dialogue_clean}\" "
        f"Voice style: {voice_note} "
        f"Audio environment: {audio_direction}. "
        f"Broadcast quality television production, vertical 9:16 framing, synchronized lip-sync, "
        f"no subtitles, no watermarks, no on-screen text."
    )
    return prompt
