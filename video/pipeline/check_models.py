"""
CLI tool: check_models
Runs regression tests against candidate Gemini models:
- Story Picker (structured decision)
- Script Generation (neutral broadcast 4-clip script)
- Comprehensive Editorial Verification Matrix:
  (1) Joke/Satire Script (MUST BE REJECTED)
  (2) Loaded Language Script (MUST BE REJECTED)
  (3) Unattributed Claims Script (MUST BE REJECTED)
  (4) Opinionated/Biased Script (MUST BE REJECTED)
  (5) Contradictory Script (MUST BE REJECTED)
  (6) Absent/Fabricated Claim Script (MUST BE REJECTED)
  (7) Clean Neutral Broadcast Script (MUST BE APPROVED)
"""

import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from google import genai
from google.genai import types
from video.config.settings import settings
from video.config.model_selector import DEFAULT_CANDIDATES, ModelCandidate
from video.api.models import VideoCandidateResponse, CandidateArticle
from video.pipeline.picker import pick_story
from video.pipeline.scripter import generate_script, ClipScript, ScriptOutput, ClaimItem, ClaimLedgerEntry
from video.pipeline.editor import edit_script
from video.bootstrap_assets import load_anchors_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("check_models")

SAMPLE_CANDIDATES = [
    VideoCandidateResponse(
        story_id="test-story-check-1",
        headline="Astronomers Discover Asteroid Containing Trillions in Rare Minerals",
        source_count=2,
        articles=[
            CandidateArticle(
                source_name="Reuters",
                title="Asteroid 2026-QA contains vast mineral wealth",
                url="https://reuters.com/news/1",
                excerpt="NASA scientist Priya Rao said telescope data showed a near-Earth asteroid contains rare platinum group metals valued in trillions.",
            ),
            CandidateArticle(
                source_name="AP News",
                title="Scientists assess commercial potential of near-Earth asteroid",
                url="https://apnews.com/news/2",
                excerpt="Mining analyst Jordan Lee said retrieval may not be economically viable, responding to the NASA assessment.",
            ),
        ],
        source_urls=["https://reuters.com/news/1", "https://apnews.com/news/2"],
        combined_story_text="NASA scientist Priya Rao described the telescope findings. Mining analyst Jordan Lee questioned commercial viability.",
    )
]

SAMPLE_LEDGER = [
    ClaimLedgerEntry(
        claim_id="C1",
        claim_text="NASA scientist Priya Rao said a near-Earth asteroid contains rare platinum group metals",
        source_outlet="Reuters",
        source_url="https://reuters.com/news/1",
        source_snippet="NASA scientist Priya Rao said telescope data showed a near-Earth asteroid contains rare platinum group metals",
        claim_type="named_person_statement",
        named_person="NASA scientist Priya Rao",
    ),
    ClaimLedgerEntry(
        claim_id="C2",
        claim_text="The metals were valued in trillions",
        source_outlet="Reuters",
        source_url="https://reuters.com/news/1",
        source_snippet="valued in trillions",
        claim_type="reported_event",
    ),
    ClaimLedgerEntry(
        claim_id="C3",
        claim_text="Mining analyst Jordan Lee said retrieval may not be economically viable",
        source_outlet="AP News",
        source_url="https://apnews.com/news/2",
        source_snippet="Mining analyst Jordan Lee said retrieval may not be economically viable",
        claim_type="named_person_statement",
        named_person="Mining analyst Jordan Lee",
        is_response=True,
    ),
]

# 1. Clean Neutral Script (MUST PASS)
SCRIPT_CLEAN_NEUTRAL = ScriptOutput(
    headline="Astronomers Track Near-Earth Asteroid Containing Rare Minerals",
    caption="Reuters reported rare metals on a near-Earth asteroid. AP reported mining analyst Jordan Lee questioned retrieval's economic viability.",
    hashtags=["#News", "#WorldNews", "#Science", "#Space"],
    ai_disclosure="Presenters and visuals are AI-generated. Report based on Reuters, AP News.",
    clips=[
        ClipScript(
            clip_index=1,
            duration_seconds=8,
            speaker="marcus",
            dialogue="Reuters reported NASA scientist Priya Rao said a near-Earth asteroid contains rare platinum group metals.",
            action="Upright posture, steady neutral gaze at the camera",
            camera="Medium close-up shot",
            claims=[ClaimItem(claim_text="NASA scientist Priya Rao said a near-Earth asteroid contains rare platinum group metals", source_url="https://reuters.com/news/1", ledger_id="C1")],
        ),
        ClipScript(
            clip_index=2,
            duration_seconds=8,
            speaker="marcus",
            dialogue="Reuters reported the asteroid's metals were valued in trillions.",
            action="Calm neutral delivery, hands resting on desk",
            camera="Medium close-up shot",
            claims=[ClaimItem(claim_text="The metals were valued in trillions", source_url="https://reuters.com/news/1", ledger_id="C2")],
        ),
        ClipScript(
            clip_index=3,
            duration_seconds=8,
            speaker="maya",
            dialogue="AP reported mining analyst Jordan Lee said retrieving the metals may not be economically viable.",
            action="Upright posture, steady news-desk eye contact with camera",
            camera="Wide desk shot",
            claims=[ClaimItem(claim_text="Mining analyst Jordan Lee said retrieval may not be economically viable", source_url="https://apnews.com/news/2", ledger_id="C3")],
        ),
        ClipScript(
            clip_index=4,
            duration_seconds=8,
            speaker="marcus",
            dialogue="AP reported mining analyst Jordan Lee said retrieval may not be economically viable. Reporting for WeAware News, I'm Marcus Vance.",
            action="Neutral sign-off posture, looking directly into camera",
            camera="Medium close-up shot",
            claims=[ClaimItem(claim_text="Mining analyst Jordan Lee said retrieval may not be economically viable", source_url="https://apnews.com/news/2", ledger_id="C3")],
        ),
    ],
    claim_ledger=SAMPLE_LEDGER,
)

# 2. Joke / Satire Script (MUST BE REJECTED)
SCRIPT_JOKE = ScriptOutput(
    headline="Billionaires Drool Over Multi-Trillion Space Rock",
    caption="Astronomers locate asteroid filled with cash for billionaires #LateNight #Satire",
    hashtags=["#Satire", "#LateNight", "#ComedyNews"],
    ai_disclosure="Presenters and visuals are AI-generated. Report based on Reuters, AP News.",
    clips=[
        ClipScript(
            clip_index=1,
            duration_seconds=8,
            speaker="marcus",
            dialogue="Astronomers spotted an asteroid worth trillions, giving Wall Street executives a brand new reason to shoot rockets at money.",
            action="Smirks at camera",
            camera="Medium close-up shot",
            claims=[ClaimItem(claim_text="Asteroid approaching Earth orbit contains rare platinum group metals", source_url="https://reuters.com/news/1")],
        ),
        ClipScript(
            clip_index=2,
            duration_seconds=8,
            speaker="marcus",
            dialogue="NASA confirmed the platinum cache, though billionaire tech CEOs are already filing copyright lawsuits over the cosmic dust.",
            action="Chuckles and rolls eyes",
            camera="Medium close-up shot",
            claims=[ClaimItem(claim_text="NASA telescope data indicates metals valued in trillions", source_url="https://reuters.com/news/1")],
        ),
        ClipScript(
            clip_index=3,
            duration_seconds=8,
            speaker="maya",
            dialogue="Our senior orbital comedy correspondent Maya Lin reports live from outside the atmosphere on this wild mining craze.",
            action="Grins with pen",
            camera="Wide desk shot",
            claims=[ClaimItem(claim_text="Mining experts debate economic viability", source_url="https://apnews.com/news/2")],
        ),
        ClipScript(
            clip_index=4,
            duration_seconds=8,
            speaker="marcus",
            dialogue="Until then, keep paying your terrestrial rent. For WeAware Late Night, I'm Marcus Vance.",
            action="Winks at lens",
            camera="Medium close-up shot",
            claims=[],
        ),
    ],
)

# 3. Loaded Language Script (MUST BE REJECTED)
SCRIPT_LOADED_LANGUAGE = ScriptOutput(
    headline="Scientists Slam Skeptics After Exposing Massive Space Bonanza",
    caption="NASA exposed massive mineral jackpot in orbit #News",
    hashtags=["#News", "#Space", "#Mining"],
    ai_disclosure="Presenters and visuals are AI-generated. Report based on Reuters, AP News.",
    clips=[
        ClipScript(
            clip_index=1,
            duration_seconds=8,
            speaker="marcus",
            dialogue="Astronomers slammed skeptical critics today after exposing a massive asteroid packed with trillions in rare platinum metals.",
            action="Aggressive forward lean",
            camera="Medium close-up shot",
            claims=[ClaimItem(claim_text="Asteroid approaching Earth orbit contains rare platinum group metals", source_url="https://reuters.com/news/1")],
        ),
        ClipScript(
            clip_index=2,
            duration_seconds=8,
            speaker="marcus",
            dialogue="NASA officials admitted telescope readings finally revealed unbelievable cosmic riches waiting right above us.",
            action="Nods firmly",
            camera="Medium close-up shot",
            claims=[ClaimItem(claim_text="NASA telescope data reveals metals valued in trillions", source_url="https://reuters.com/news/1")],
        ),
        ClipScript(
            clip_index=3,
            duration_seconds=8,
            speaker="maya",
            dialogue="Mining executives blasted cautious scientists who dared question whether deep space commercial extraction would triumph.",
            action="Sharp gesture",
            camera="Wide desk shot",
            claims=[ClaimItem(claim_text="Mining experts debate economic viability", source_url="https://apnews.com/news/2")],
        ),
        ClipScript(
            clip_index=4,
            duration_seconds=8,
            speaker="marcus",
            dialogue="Spokespeople conceded bitter battles lie ahead over the disputed cosmic bounty. Reporting for WeAware News.",
            action="Firm gaze",
            camera="Medium close-up shot",
            claims=[],
        ),
    ],
)

# 4. Unattributed Claims Script (MUST BE REJECTED)
SCRIPT_UNATTRIBUTED = ScriptOutput(
    headline="Private Mining Fleets Prepare to Seize Asteroid Ore",
    caption="Commercial excavation planned without verification #News",
    hashtags=["#News", "#Space"],
    ai_disclosure="Presenters and visuals are AI-generated. Report based on Reuters, AP News.",
    clips=[
        ClipScript(
            clip_index=1,
            duration_seconds=8,
            speaker="marcus",
            dialogue="An approaching asteroid contains five trillion dollars in metals, but no scientific agency has verified the claim.",
            action="Upright posture",
            camera="Medium close-up shot",
            claims=[],
        ),
        ClipScript(
            clip_index=2,
            duration_seconds=8,
            speaker="marcus",
            dialogue="Unverified industry reports say private contractors will secretly capture the asteroid without international oversight.",
            action="Neutral gaze",
            camera="Medium close-up shot",
            claims=[],
        ),
        ClipScript(
            clip_index=3,
            duration_seconds=8,
            speaker="maya",
            dialogue="Anonymous insiders claim commercial excavation fleets will depart orbit in eighteen months to seize the deposit.",
            action="Neutral expression",
            camera="Wide desk shot",
            claims=[],
        ),
        ClipScript(
            clip_index=4,
            duration_seconds=8,
            speaker="marcus",
            dialogue="Sources claim corporate syndicates have already bypassed global regulators. Reporting for WeAware News, I'm Marcus Vance.",
            action="Neutral posture",
            camera="Medium close-up shot",
            claims=[],
        ),
    ],
)

# 5. Opinionated / Biased Script (MUST BE REJECTED)
SCRIPT_OPINIONATED = ScriptOutput(
    headline="Greedy Aerospace Corporations Target Celestial Commons",
    caption="Dangerous space rush should be halted #News",
    hashtags=["#News", "#SpacePolicy"],
    ai_disclosure="Presenters and visuals are AI-generated. Report based on Reuters, AP News.",
    clips=[
        ClipScript(
            clip_index=1,
            duration_seconds=8,
            speaker="marcus",
            dialogue="Greedy aerospace conglomerates are irresponsibly eyeing an approaching asteroid that contains rare platinum group metals.",
            action="Disapproving frown",
            camera="Medium close-up shot",
            claims=[ClaimItem(claim_text="Asteroid approaching Earth orbit contains rare platinum group metals", source_url="https://reuters.com/news/1")],
        ),
        ClipScript(
            clip_index=2,
            duration_seconds=8,
            speaker="marcus",
            dialogue="NASA foolishly squandered public tax dollars chasing commercial minerals instead of solving poverty on Earth.",
            action="Shakes head",
            camera="Medium close-up shot",
            claims=[ClaimItem(claim_text="NASA telescope data reveals metals valued in trillions", source_url="https://reuters.com/news/1")],
        ),
        ClipScript(
            clip_index=3,
            duration_seconds=8,
            speaker="maya",
            dialogue="Self-interested mining executives obviously want to monopolize cosmic resources to artificially manipulate metal prices.",
            action="Skeptical look",
            camera="Wide desk shot",
            claims=[ClaimItem(claim_text="Mining experts debate economic viability", source_url="https://apnews.com/news/2")],
        ),
        ClipScript(
            clip_index=4,
            duration_seconds=8,
            speaker="marcus",
            dialogue="This reckless corporate plunder must be immediately outlawed by international treaties. For WeAware News.",
            action="Firm gaze",
            camera="Medium close-up shot",
            claims=[],
        ),
    ],
)

# 6. Contradictory Script (MUST BE REJECTED)
SCRIPT_CONTRADICTORY = ScriptOutput(
    headline="Asteroid Proven Completely Worthless",
    caption="NASA says zero minerals in new asteroid #News",
    hashtags=["#News", "#Space"],
    ai_disclosure="Presenters and visuals are AI-generated. Report based on Reuters, AP News.",
    clips=[
        ClipScript(
            clip_index=1,
            duration_seconds=8,
            speaker="marcus",
            dialogue="NASA scientists confirmed today that the asteroid contains zero platinum and has no mineral value whatsoever.",
            action="Neutral gaze",
            camera="Medium close-up shot",
            claims=[ClaimItem(claim_text="NASA confirmed the asteroid contains zero platinum and no mineral value", source_url="https://reuters.com/news/1")],
        ),
        ClipScript(
            clip_index=2,
            duration_seconds=8,
            speaker="marcus",
            dialogue="Telescope readings proved the celestial body is actually composed entirely of valueless space dust.",
            action="Neutral gaze",
            camera="Medium close-up shot",
            claims=[ClaimItem(claim_text="Telescope readings proved asteroid is entirely space dust with no minerals", source_url="https://reuters.com/news/1")],
        ),
        ClipScript(
            clip_index=3,
            duration_seconds=8,
            speaker="maya",
            dialogue="Mining experts unanimously announced space commercialization is completely dead and impossible.",
            action="Neutral gaze",
            camera="Wide desk shot",
            claims=[ClaimItem(claim_text="Mining experts declared space commercialization completely dead", source_url="https://apnews.com/news/2")],
        ),
        ClipScript(
            clip_index=4,
            duration_seconds=8,
            speaker="marcus",
            dialogue="Researchers said no further tracking will occur. Reporting for WeAware News, I'm Marcus Vance.",
            action="Neutral sign-off",
            camera="Medium close-up shot",
            claims=[],
        ),
    ],
)

# 7. Absent / Fabricated Claim Script (MUST BE REJECTED)
SCRIPT_ABSENT = ScriptOutput(
    headline="French Government Purchases Approaching Asteroid",
    caption="France buys asteroid for fifty euros #News",
    hashtags=["#News", "#Space"],
    ai_disclosure="Presenters and visuals are AI-generated. Report based on Reuters, AP News.",
    clips=[
        ClipScript(
            clip_index=1,
            duration_seconds=8,
            speaker="marcus",
            dialogue="Astronomers tracked an asteroid approaching Earth orbit containing rare platinum group metals, according to Reuters.",
            action="Neutral gaze",
            camera="Medium close-up shot",
            claims=[ClaimItem(claim_text="Asteroid approaching Earth orbit contains rare platinum metals", source_url="https://reuters.com/news/1")],
        ),
        ClipScript(
            clip_index=2,
            duration_seconds=8,
            speaker="marcus",
            dialogue="Meanwhile, the French government announced it purchased the asteroid for fifty euros and named it Pierre.",
            action="Neutral delivery",
            camera="Medium close-up shot",
            claims=[ClaimItem(claim_text="The French government purchased the asteroid for fifty euros and named it Pierre", source_url="https://reuters.com/news/1")],
        ),
        ClipScript(
            clip_index=3,
            duration_seconds=8,
            speaker="maya",
            dialogue="Scientists and mining experts debate whether commercial retrieval of materials is economically viable.",
            action="Neutral gaze",
            camera="Wide desk shot",
            claims=[ClaimItem(claim_text="Mining experts debate whether commercial extraction is economically viable", source_url="https://apnews.com/news/2")],
        ),
        ClipScript(
            clip_index=4,
            duration_seconds=8,
            speaker="marcus",
            dialogue="French officials said paperwork has been filed in Paris. For WeAware News, I'm Marcus Vance.",
            action="Neutral sign-off",
            camera="Medium close-up shot",
            claims=[],
        ),
    ],
)

SANCTIONS_CANDIDATE = VideoCandidateResponse(
    story_id="test-sanctions-distinction",
    headline="Government eases diesel sanctions",
    source_count=2,
    articles=[
        CandidateArticle(
            source_name="Reuters",
            title="Government eases diesel sanctions",
            url="https://reuters.com/sanctions",
            excerpt=(
                "The government eased sanctions on diesel exports. President Alex Smith said prices remained a concern. "
                "The report described the policy as blaming the victim."
            ),
        ),
        CandidateArticle(
            source_name="AP News",
            title="Opposition responds",
            url="https://apnews.com/response",
            excerpt="Opposition leader Jordan Lee said the sanctions change should be reviewed.",
        ),
    ],
    source_urls=["https://reuters.com/sanctions", "https://apnews.com/response"],
    combined_story_text="Sanctions were eased and two named leaders gave statements.",
)

SANCTIONS_LEDGER = [
    ClaimLedgerEntry(
        claim_id="S1", claim_text="The government eased sanctions on diesel exports", source_outlet="Reuters",
        source_url="https://reuters.com/sanctions", source_snippet="The government eased sanctions on diesel exports",
        claim_type="reported_event",
    ),
    ClaimLedgerEntry(
        claim_id="S2", claim_text="President Alex Smith said prices remained a concern", source_outlet="Reuters",
        source_url="https://reuters.com/sanctions", source_snippet="President Alex Smith said prices remained a concern",
        claim_type="named_person_statement", named_person="President Alex Smith",
    ),
    ClaimLedgerEntry(
        claim_id="S3", claim_text="Opposition leader Jordan Lee said the sanctions change should be reviewed", source_outlet="AP News",
        source_url="https://apnews.com/response", source_snippet="Opposition leader Jordan Lee said the sanctions change should be reviewed",
        claim_type="named_person_statement", named_person="Opposition leader Jordan Lee", is_response=True,
    ),
    ClaimLedgerEntry(
        claim_id="S4", claim_text="The policy was blaming the victim", source_outlet="Reuters",
        source_url="https://reuters.com/sanctions", source_snippet="blaming the victim",
        claim_type="outlet_characterization",
    ),
]


def sanctions_script(first_dialogue: str, first_claim: ClaimItem) -> ScriptOutput:
    return ScriptOutput(
        headline="Government Eases Diesel Sanctions",
        caption="Reuters reported a sanctions change; AP reported an opposition response.",
        hashtags=["#News", "#Sanctions"],
        ai_disclosure="Presenters and visuals are AI-generated. Report based on Reuters, AP News.",
        clips=[
            ClipScript(clip_index=1, duration_seconds=8, speaker="marcus", dialogue=first_dialogue,
                       action="Neutral posture", camera="Medium close-up shot", claims=[first_claim]),
            ClipScript(clip_index=2, duration_seconds=8, speaker="marcus",
                       dialogue="Reuters reported President Alex Smith said prices remained a concern.",
                       action="Neutral posture", camera="Medium close-up shot",
                       claims=[ClaimItem(claim_text="President Alex Smith said prices remained a concern", source_url="https://reuters.com/sanctions", ledger_id="S2")]),
            ClipScript(clip_index=3, duration_seconds=8, speaker="maya",
                       dialogue="AP reported opposition leader Jordan Lee said the sanctions change should be reviewed.",
                       action="Neutral posture", camera="Wide desk shot",
                       claims=[ClaimItem(claim_text="Opposition leader Jordan Lee said the sanctions change should be reviewed", source_url="https://apnews.com/response", ledger_id="S3")]),
            ClipScript(clip_index=4, duration_seconds=8, speaker="marcus",
                       dialogue="President Alex Smith said prices remained a concern. Reporting for WeAware News, I'm Marcus Vance.",
                       action="Neutral sign-off", camera="Medium close-up shot",
                       claims=[ClaimItem(claim_text="President Alex Smith said prices remained a concern", source_url="https://reuters.com/sanctions", ledger_id="S2")]),
        ],
        claim_ledger=SANCTIONS_LEDGER,
    )


SCRIPT_BLAMING_VICTIM = sanctions_script(
    "Reuters described the policy as blaming the victim.",
    ClaimItem(claim_text="The policy was blaming the victim", source_url="https://reuters.com/sanctions", ledger_id="S4"),
)
SCRIPT_PURCHASE_DISTORTION = sanctions_script(
    "Reuters reported the government purchased Russian diesel.",
    ClaimItem(claim_text="The government purchased Russian diesel", source_url="https://reuters.com/sanctions", ledger_id="S1"),
)
SCRIPT_IMPLIED_CAUSATION = sanctions_script(
    "The day after sanctions were eased, another event occurred, Reuters reported.",
    ClaimItem(claim_text="The government eased sanctions on diesel exports", source_url="https://reuters.com/sanctions", ledger_id="S1"),
)


def test_candidate_model(candidate: ModelCandidate) -> Dict[str, Any]:
    logger.info(f"=== Testing Model: {candidate.model_id} (location: {candidate.location}, role: {candidate.role}) ===")
    results = {"model_id": candidate.model_id, "location": candidate.location, "role": candidate.role, "tests": {}}

    try:
        client = genai.Client(
            vertexai=True,
            project=settings.project_id,
            location=candidate.location,
        )
    except Exception as e:
        logger.error(f"Failed to initialize client for {candidate.model_id}: {e}")
        results["tests"]["client_init"] = f"FAIL: {e}"
        return results

    anchors_config = load_anchors_config()

    # 1. Test Picker if flash
    if candidate.role == "flash":
        try:
            chosen, decision, _ = pick_story(SAMPLE_CANDIDATES, client=client, model=candidate.model_id)
            assert chosen is not None
            assert decision.chosen_story_id != ""
            results["tests"]["picker"] = "PASS"
            logger.info(f"  [PASS] Picker: chosen={decision.chosen_story_id}")
        except Exception as e:
            results["tests"]["picker"] = f"FAIL: {e}"
            logger.error(f"  [FAIL] Picker: {e}")

    # 2. Test Scripter (Clean neutral script generation)
    try:
        script = generate_script(
            SAMPLE_CANDIDATES[0],
            anchors_config=anchors_config,
            client=client,
            model=candidate.model_id,
        )
        assert len(script.clips) == 4
        for c in script.clips:
            assert c.dialogue != ""
        results["tests"]["scripter"] = "PASS"
        logger.info(f"  [PASS] Scripter: 4 clips generated successfully")
    except Exception as e:
        results["tests"]["scripter"] = f"FAIL: {e}"
        logger.error(f"  [FAIL] Scripter: {e}")

    # 3. Comprehensive Editor Tests Matrix:
    # 6 Negative Cases (MUST BE REJECTED) + 1 Clean Neutral Case (MUST BE APPROVED)
    test_cases = [
        ("neg_joke", SAMPLE_CANDIDATES[0], SCRIPT_JOKE, False),
        ("neg_loaded", SAMPLE_CANDIDATES[0], SCRIPT_LOADED_LANGUAGE, False),
        ("neg_unattributed", SAMPLE_CANDIDATES[0], SCRIPT_UNATTRIBUTED, False),
        ("neg_opinion", SAMPLE_CANDIDATES[0], SCRIPT_OPINIONATED, False),
        ("neg_contradict", SAMPLE_CANDIDATES[0], SCRIPT_CONTRADICTORY, False),
        ("neg_absent", SAMPLE_CANDIDATES[0], SCRIPT_ABSENT, False),
        ("neg_blame_victim", SANCTIONS_CANDIDATE, SCRIPT_BLAMING_VICTIM, False),
        ("neg_purchase_vs_sanctions", SANCTIONS_CANDIDATE, SCRIPT_PURCHASE_DISTORTION, False),
        ("neg_implied_causation", SANCTIONS_CANDIDATE, SCRIPT_IMPLIED_CAUSATION, False),
        ("clean_neutral", SAMPLE_CANDIDATES[0], SCRIPT_CLEAN_NEUTRAL, True),
    ]

    for test_name, source_candidate, script_case, expected_pass in test_cases:
        try:
            dec = edit_script(
                source_candidate,
                script_case,
                client=client,
                model=candidate.model_id,
                is_fallback=(candidate.role == "flash"),
            )
            if expected_pass:
                if dec.passed:
                    results["tests"][test_name] = "PASS"
                    logger.info(f"  [PASS] {test_name}: correctly APPROVED clean script")
                else:
                    results["tests"][test_name] = f"FAIL (unexpected rejection: {dec.critique_reason})"
                    logger.error(f"  [FAIL] {test_name}: clean script unexpectedly REJECTED: {dec.critique_reason}")
            else:
                if not dec.passed:
                    violations = dec.neutrality_violations or dec.flags or [dec.critique_reason]
                    results["tests"][test_name] = "PASS"
                    logger.info(f"  [PASS] {test_name}: correctly REJECTED ({violations[:1]})")
                else:
                    results["tests"][test_name] = "FAIL (accepted non-compliant script)"
                    logger.error(f"  [FAIL] {test_name}: non-compliant script INCORRECTLY APPROVED")
        except Exception as e:
            results["tests"][test_name] = f"ERROR: {e}"
            logger.error(f"  [ERROR] {test_name}: {e}")

        import time
        time.sleep(1.5)

    return results


def main():
    all_results = []
    logger.info("Running check_models across all candidate models...")
    for role, candidates in DEFAULT_CANDIDATES.items():
        for c in candidates:
            res = test_candidate_model(c)
            all_results.append(res)

    print("\n" + "=" * 120)
    print("CHECK_MODELS SUMMARY REPORT: CLAIM-LEDGER & NEUTRALITY TEST MATRIX")
    print("=" * 120)
    header = f"{'Model ID':<20} {'Role':<6} {'Pick':<5} {'Script':<6} | {'Joke':<6} {'Loaded':<6} {'Unattr':<6} {'Opin':<6} {'Contra':<6} {'Absent':<6} {'Blame':<6} {'Buy/San':<7} {'Cause':<6} | {'Clean':<6}"
    print(header)
    print("-" * 120)

    all_passed = True

    for r in all_results:
        m_id = r["model_id"]
        role = r["role"]
        t = r["tests"]
        pick_s = "PASS" if "PASS" in t.get("picker", "") else ("-" if role != "flash" else "FAIL")
        script_s = "PASS" if "PASS" in t.get("scripter", "") else "FAIL"

        joke_s = "PASS" if t.get("neg_joke") == "PASS" else "FAIL"
        loaded_s = "PASS" if t.get("neg_loaded") == "PASS" else "FAIL"
        unattr_s = "PASS" if t.get("neg_unattributed") == "PASS" else "FAIL"
        opin_s = "PASS" if t.get("neg_opinion") == "PASS" else "FAIL"
        contra_s = "PASS" if t.get("neg_contradict") == "PASS" else "FAIL"
        absent_s = "PASS" if t.get("neg_absent") == "PASS" else "FAIL"
        blame_s = "PASS" if t.get("neg_blame_victim") == "PASS" else "FAIL"
        purchase_s = "PASS" if t.get("neg_purchase_vs_sanctions") == "PASS" else "FAIL"
        cause_s = "PASS" if t.get("neg_implied_causation") == "PASS" else "FAIL"
        clean_s = "PASS" if t.get("clean_neutral") == "PASS" else "FAIL"

        row = f"{m_id:<20} {role:<6} {pick_s:<5} {script_s:<6} | {joke_s:<6} {loaded_s:<6} {unattr_s:<6} {opin_s:<6} {contra_s:<6} {absent_s:<6} {blame_s:<6} {purchase_s:<7} {cause_s:<6} | {clean_s:<6}"
        print(row)

        for s in [joke_s, loaded_s, unattr_s, opin_s, contra_s, absent_s, blame_s, purchase_s, cause_s, clean_s]:
            if s != "PASS":
                all_passed = False

    print("-" * 120)
    print("Legend:")
    print("  Negative Tests: Joke, Loaded, Unattr, Opin, Contra, Absent, Blame, Buy/San, Cause")
    print("  Clean Test:     Clean Neutral Broadcast Script             (PASS = correctly approved)")
    print("=" * 120)

    if all_passed:
        print("\n✓ ALL CANDIDATE MODELS PASSED ALL NEGATIVE & CLEAN EDITORIAL REGRESSION CHECKS.\n")
    else:
        print("\n⚠️ WARNING: One or more models failed negative or clean editor regression checks.\n")


if __name__ == "__main__":
    main()
