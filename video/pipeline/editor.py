"""
Editor Pass: Second-pass validation using Gemini Pro (or Flash fallback) to verify
factual grounding against source texts and enforce strict broadcast news neutrality.
"""

import json
import logging
from typing import List, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from video.config.settings import settings
from video.api.models import VideoCandidateResponse
from video.pipeline.scripter import ClaimLedger, ScriptOutput, deterministic_script_violations, generate_content_with_retry

logger = logging.getLogger("weaware-video.editor")


class EditorDecision(BaseModel):
    passed: bool = Field(description="True if script meets all factual grounding and broadcast neutrality standards")
    factual_distortion_flag: bool = Field(description="True if any claim contradicts, distorts, or lacks support in source texts")
    neutrality_violations: List[str] = Field(
        default_factory=list,
        description="List of specific neutrality violations found (humor, satire, loaded language, unattributed claims, opinion, one-sided framing). Empty if clean.",
    )
    flags: List[str] = Field(default_factory=list, description="Specific factual concerns or discrepancies found (empty if clean)")
    unmapped_claims: List[str] = Field(default_factory=list, description="Dialogue claims without an allowed claim-ledger mapping")
    causal_implication_violations: List[str] = Field(default_factory=list, description="Event juxtapositions that imply an unsupported causal link")
    critique_reason: str = Field(description="Detailed editorial assessment explaining the verdict")


_EDITOR_SYSTEM_PROMPT = """You are the Senior Standards & Practices Editor for "WeAware News", a strictly objective, straight broadcast television news program.
Your job is to conduct a rigorous, two-pillar editorial audit of a proposed 4-clip television news script against the underlying news source texts:
Pillar 1: FACTUAL GROUNDING AUDIT
Pillar 2: STRICT BROADCAST NEUTRALITY AUDIT

AUDIT CRITERIA:

1. PILLAR 1: FACTUAL GROUNDING (ZERO TOLERANCE FOR FABRICATION OR DISTORTION):
   - Every factual claim, number, statistic, quote, and event made in the dialogue must be supported by the provided source articles.
   - If the script invents statistics, names, events, quotes, or details not found in the source text, set `factual_distortion_flag = True`, add the issue to `flags`, and set `passed = False`.
   - If the script contradicts the source articles, set `factual_distortion_flag = True`, add to `flags`, and set `passed = False`.
   - Every dialogue claim must map to a supplied claim-ledger entry typed reported_event or named_person_statement. List missing or prohibited mappings in `unmapped_claims`.
   - Preserve material action distinctions. For example, easing sanctions is not purchasing goods, and reporting chronology is not reporting causation.

2. PILLAR 2: BROADCAST NEUTRALITY AUDIT (ZERO TOLERANCE FOR EDITORIALIZING OR HUMOR):
   - NO HUMOR OR SATIRE: Reject scripts with jokes, puns, sarcasm, irony, punchlines, comedic tags, or "late night" comedic framing.
   - NO LOADED LANGUAGE: Dialogue must use neutral broadcast language. Reject loaded, dramatic, or judgmental verbs such as "slammed", "blasted", "admitted", "claimed", "lashed out", "boasted", or sensational descriptors. Officials must be quoted or paraphrased with neutral verbs ("said", "stated", "reported").
   - NO UNATTRIBUTED CLAIMS: Significant claims, accusations, casualties, or major policy statements must be explicitly attributed to a reporting source (e.g. "according to Reuters", "officials told The Guardian"). Unattributed assertions must be flagged.
   - NO OPINION OR MOTIVE CHARACTERIZATION: The script must not express editorial opinions, speculate, characterize motives, or adopt a one-sided framing. Where sources report conflicting accounts or competing sides, both must be presented neutrally and attributed.
   - OUTLET CHARACTERIZATIONS ARE PROHIBITED: Never adopt an outlet's characterization or opinion, even with attribution. A source phrase such as "blaming the victim" must not appear in the script.
   - CAUSAL IMPLICATION: Reject juxtaposed events that imply a link through wording such as "the day after", "following", or "amid" unless a ledger entry explicitly supports the causal link. List these in `causal_implication_violations`.
   - If ANY neutrality violation is present, you MUST list each specific offending word, phrase, or sentence in `neutrality_violations` and set `passed = False`.

VERDICT RULE:
- If `factual_distortion_flag == True` OR `len(neutrality_violations) > 0`, you MUST set `passed = False`.
- If `unmapped_claims` or `causal_implication_violations` is non-empty, you MUST set `passed = False`.
- Set `passed = True` ONLY if the script is 100% factually grounded AND 100% neutral.
- Return valid JSON strictly matching the requested schema.
"""

_EDITOR_SYSTEM_PROMPT_STRICT = """You are the Senior Standards & Practices Editor for "WeAware News", conducting a strict adversarial audit of a proposed 4-clip broadcast news script against the underlying news source texts.
NOTE: Strict fallback audit mode is ACTIVE. Because a fallback model is running the fact-check and neutrality safety gate, you must perform an explicit claim-by-claim check of every single dialogue line against the source text.

AUDIT CRITERIA (STRICT CLAIM-BY-CLAIM FALLBACK MODE):

1. EXPLICIT CLAIM-BY-CLAIM FACTUAL VERIFICATION:
   - Check every single assertion in the dialogue and `claims` list individually against the source text.
   - Every fact must have direct, verifiable textual support in the source texts.
   - If any claim, statistic, quote, name, or detail lacks explicit corroboration, extrapolates beyond the text, or contradicts the text, you MUST set `factual_distortion_flag = True` and `passed = False`.
   - List each failed or uncorroborated claim specifically in `flags`.

2. ADVERSARIAL NEUTRALITY AUDIT:
   - Check every word for humor, jokes, sarcasm, irony, or punchlines.
   - Check every verb and adjective for loaded, dramatic, or biased language (e.g. "slammed", "blasted", "admitted", "claimed", "conceded", "lashed out").
   - Check that all major assertions are explicitly attributed to their sources.
   - Check that no opinions, motives, or one-sided characterizations are present.
   - If any violation is found, list it specifically in `neutrality_violations` and set `passed = False`.

VERDICT RULE:
- Set `passed = True` ONLY if every assertion is fully supported by the sources AND completely free of neutrality violations (`neutrality_violations` is empty and `factual_distortion_flag == False`).
- Return valid JSON strictly matching the requested schema.
"""


def edit_script(
    candidate: VideoCandidateResponse,
    script: ScriptOutput,
    client: Optional[genai.Client] = None,
    model: Optional[str] = None,
    is_fallback: bool = False,
) -> EditorDecision:
    ledger = ClaimLedger(
        entries=script.claim_ledger,
        has_counter_voice=any(entry.is_response for entry in script.claim_ledger),
        balance_note="Derived from script claim ledger for editor verification.",
    )
    deterministic = deterministic_script_violations(script, ledger)
    loaded_phrases = [
        phrase
        for phrase in ("blaming the victim", "slammed", "blasted", "admitted", "lashed out", "boasted", "condemned", "criticized")
        if any(phrase in clip.dialogue.lower() for clip in script.clips)
    ]
    unmapped = [issue for issue in deterministic if "ledger entry" in issue or "source URL" in issue or "prohibited outlet" in issue or "changes" in issue]
    causal = [issue for issue in deterministic if "causal link" in issue]
    other_deterministic = [issue for issue in deterministic if issue not in unmapped and issue not in causal]
    if loaded_phrases or unmapped or causal or other_deterministic:
        neutrality = [f"Loaded or judgmental phrase is prohibited: {phrase}" for phrase in loaded_phrases]
        neutrality.extend(issue for issue in other_deterministic if "response" in issue)
        factual_flags = [issue for issue in other_deterministic if "response" not in issue]
        factual_flags.extend(unmapped)
        return EditorDecision(
            passed=False,
            factual_distortion_flag=bool(factual_flags or unmapped or causal),
            neutrality_violations=neutrality,
            flags=factual_flags,
            unmapped_claims=unmapped,
            causal_implication_violations=causal,
            critique_reason="Deterministic pre-editor checks rejected the script before model review.",
        )

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
    ledger_summary = json.dumps([entry.model_dump() for entry in script.claim_ledger], indent=2)

    if is_fallback:
        prompt = (
            f"PROPOSED SCRIPT:\n{script_summary}\n\n"
            f"VERIFIED SOURCE ARTICLES:\n{sources_summary}\n\n"
            f"CLAIM LEDGER:\n{ledger_summary}\n\n"
            "STRICT CLAIM-BY-CLAIM AND NEUTRALITY AUDIT INSTRUCTION: "
            "Conduct an explicit claim-by-claim verification of every dialogue line and claim against the source text. "
            "Examine each asserted fact for source support, and examine tone for humor, loaded language, unattributed claims, or bias. "
            "If any detail is uncorroborated or biased, set passed=False and list the specific issues in flags or neutrality_violations. "
            "Render your verdict."
        )
        system_instruction = _EDITOR_SYSTEM_PROMPT_STRICT
        logger.info(f"Running Editor pass in STRICT CLAIM-BY-CLAIM FALLBACK mode with model={target_model}...")
    else:
        prompt = (
            f"PROPOSED SCRIPT:\n{script_summary}\n\n"
            f"VERIFIED SOURCE ARTICLES:\n{sources_summary}\n\n"
            f"CLAIM LEDGER:\n{ledger_summary}\n\n"
            "Audit this script against the source texts. Conduct both the Factual Grounding audit and the Broadcast Neutrality audit. "
            "Verify factual support for all claims, verify strict neutrality (no humor, no loaded verbs, explicit attribution, no opinions), "
            "and render your verdict."
        )
        system_instruction = _EDITOR_SYSTEM_PROMPT
        logger.info(f"Running Editor pass with model={target_model}...")

    resp = generate_content_with_retry(
        client,
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

    # Post-validation safety enforcement: if any violations exist, passed must be False
    if decision.factual_distortion_flag or decision.neutrality_violations or decision.unmapped_claims or decision.causal_implication_violations:
        decision.passed = False

    if decision.passed:
        logger.info(f"Editor pass PASSED: {decision.critique_reason}")
    else:
        logger.warning(
            f"Editor pass FAILED (distortion={decision.factual_distortion_flag}, neutrality_violations={decision.neutrality_violations}): "
            f"{decision.flags} - {decision.critique_reason}"
        )

    return decision
