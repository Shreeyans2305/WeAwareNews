"""
CLI tool: check_models
Runs regression tests against every candidate Gemini model in model_selector.DEFAULT_CANDIDATES:
- Story Picker (structured decision)
- Script Generation (structured 4-clip script)
- Editorial Verification (structured approval/edits)
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
from video.pipeline.scripter import generate_script, ClipScript, ScriptOutput, ClaimItem
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
                excerpt="NASA telescope data reveals an asteroid approaching Earth orbit contains rare platinum group metals valued in trillions.",
            ),
            CandidateArticle(
                source_name="AP News",
                title="Scientists assess commercial potential of near-Earth asteroid",
                url="https://apnews.com/news/2",
                excerpt="Mining experts and space scientists debate whether retrieving materials from the newly mapped asteroid is economically viable.",
            ),
        ],
        source_urls=["https://reuters.com/news/1", "https://apnews.com/news/2"],
        combined_story_text="NASA telescope data reveals an asteroid approaching Earth orbit contains rare platinum group metals valued in trillions. Mining experts and space scientists debate whether retrieving materials from the newly mapped asteroid is economically viable.",
    )
]

SCRIPT_CLEAN = ScriptOutput(
    headline="Asteroid Platinum Rush Debated",
    caption="Astronomers locate multi-trillion dollar asteroid #space #news",
    hashtags=["#space", "#news", "#satire"],
    satire_disclosure="AI satire",
    clips=[
        ClipScript(
            clip_index=1,
            duration_seconds=8,
            speaker="marcus",
            dialogue="Good evening. Astronomers have tracked an asteroid approaching Earth orbit carrying trillions in rare platinum metals.",
            action="Deadpan look",
            camera="Medium close-up shot",
            claims=[ClaimItem(claim_text="Asteroid approaching Earth orbit contains rare platinum metals valued in trillions", source_url="https://reuters.com/news/1")],
        ),
        ClipScript(
            clip_index=2,
            duration_seconds=8,
            speaker="marcus",
            dialogue="NASA telescope data confirms the mineral wealth, leaving Wall Street eager to short space rocks.",
            action="Smirks",
            camera="Medium close-up shot",
            claims=[ClaimItem(claim_text="NASA telescope data confirms mineral wealth", source_url="https://reuters.com/news/1")],
        ),
        ClipScript(
            clip_index=3,
            duration_seconds=8,
            speaker="maya",
            dialogue="Mining experts and space scientists are actively debating if retrieving the materials is economically viable.",
            action="Nods",
            camera="Wide desk shot",
            claims=[ClaimItem(claim_text="Mining experts debate if retrieving materials is economically viable", source_url="https://apnews.com/news/2")],
        ),
        ClipScript(
            clip_index=4,
            duration_seconds=8,
            speaker="marcus",
            dialogue="Until then, it remains trillions safely out of executive reach. Corroborated news, satirical conclusions.",
            action="Waves pen",
            camera="Medium close-up shot",
            claims=[],
        ),
    ],
)

SCRIPT_CONTRADICTORY = ScriptOutput(
    headline="Asteroid Proved Completely Worthless",
    caption="NASA says zero minerals in new asteroid #space",
    hashtags=["#space", "#news"],
    satire_disclosure="AI satire",
    clips=[
        ClipScript(
            clip_index=1,
            duration_seconds=8,
            speaker="marcus",
            dialogue="NASA scientists confirmed today that the asteroid contains zero platinum and has no mineral value whatsoever.",
            action="Shakes head",
            camera="Medium close-up shot",
            claims=[ClaimItem(claim_text="NASA confirmed the asteroid contains zero platinum and no mineral value", source_url="https://reuters.com/news/1")],
        ),
        ClipScript(
            clip_index=2,
            duration_seconds=8,
            speaker="marcus",
            dialogue="Telescope readings proved the celestial body is actually entirely composed of compressed space dust.",
            action="Chuckles",
            camera="Medium close-up shot",
            claims=[ClaimItem(claim_text="Telescope readings proved asteroid is entirely space dust with no minerals", source_url="https://reuters.com/news/1")],
        ),
        ClipScript(
            clip_index=3,
            duration_seconds=8,
            speaker="maya",
            dialogue="Mining experts unanimously declared space commercialization completely dead and finished.",
            action="Sighs",
            camera="Wide desk shot",
            claims=[ClaimItem(claim_text="Mining experts declared space commercialization completely dead", source_url="https://apnews.com/news/2")],
        ),
        ClipScript(
            clip_index=4,
            duration_seconds=8,
            speaker="marcus",
            dialogue="Back to Earth problems. Corroborated news, satirical conclusions.",
            action="Shuffles papers",
            camera="Medium close-up shot",
            claims=[],
        ),
    ],
)

SCRIPT_ABSENT = ScriptOutput(
    headline="Asteroid Claimed by French Bureaucracy",
    caption="France buys asteroid for fifty euros #satire",
    hashtags=["#space", "#satire"],
    satire_disclosure="AI satire",
    clips=[
        ClipScript(
            clip_index=1,
            duration_seconds=8,
            speaker="marcus",
            dialogue="Good evening. Astronomers tracked an asteroid approaching Earth orbit containing rare platinum group metals.",
            action="Nods",
            camera="Medium close-up shot",
            claims=[ClaimItem(claim_text="Asteroid approaching Earth orbit contains rare platinum metals", source_url="https://reuters.com/news/1")],
        ),
        ClipScript(
            clip_index=2,
            duration_seconds=8,
            speaker="marcus",
            dialogue="Meanwhile, the French government announced yesterday that it purchased the asteroid for fifty euros and named it Pierre.",
            action="Raises eyebrow",
            camera="Medium close-up shot",
            claims=[ClaimItem(claim_text="The French government purchased the asteroid for fifty euros and named it Pierre", source_url="https://reuters.com/news/1")],
        ),
        ClipScript(
            clip_index=3,
            duration_seconds=8,
            speaker="maya",
            dialogue="Mining experts and scientists debate whether commercial extraction from the rock is economically viable.",
            action="Smiles",
            camera="Wide desk shot",
            claims=[ClaimItem(claim_text="Mining experts debate whether commercial extraction is economically viable", source_url="https://apnews.com/news/2")],
        ),
        ClipScript(
            clip_index=4,
            duration_seconds=8,
            speaker="marcus",
            dialogue="Good luck collecting taxes on Pierre. Corroborated news, satirical conclusions.",
            action="Taps desk",
            camera="Medium close-up shot",
            claims=[],
        ),
    ],
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

    # 2. Test Scripter
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

    # 3. Comprehensive Editor Tests: Negative (a, b) and Clean (c) in Normal and Pro-Role Strict Modes
    # (a) Contradictory Script: Must fail audit (passed == False)
    # (b) Absent Claim Script: Must fail audit (passed == False)
    # (c) Clean Script: Must pass audit (passed == True)

    modes = [("normal", False), ("pro_strict", True)]
    for mode_name, is_fallback in modes:
        # (a) Negative: Contradictory claim
        try:
            dec_contra = edit_script(
                SAMPLE_CANDIDATES[0],
                SCRIPT_CONTRADICTORY,
                client=client,
                model=candidate.model_id,
                is_fallback=is_fallback,
            )
            if not dec_contra.passed:
                results["tests"][f"editor_{mode_name}_neg_contradict"] = "PASS (rejected contradiction)"
                logger.info(f"  [PASS] Editor {mode_name} Negative Contradiction: correctly rejected")
            else:
                results["tests"][f"editor_{mode_name}_neg_contradict"] = "FAIL (accepted contradiction)"
                logger.error(f"  [FAIL] Editor {mode_name} Negative Contradiction: incorrectly PASSED")
        except Exception as e:
            results["tests"][f"editor_{mode_name}_neg_contradict"] = f"ERROR: {e}"

        # (b) Negative: Absent claim
        try:
            dec_absent = edit_script(
                SAMPLE_CANDIDATES[0],
                SCRIPT_ABSENT,
                client=client,
                model=candidate.model_id,
                is_fallback=is_fallback,
            )
            if not dec_absent.passed:
                results["tests"][f"editor_{mode_name}_neg_absent"] = "PASS (rejected absent claim)"
                logger.info(f"  [PASS] Editor {mode_name} Negative Absent: correctly rejected")
            else:
                results["tests"][f"editor_{mode_name}_neg_absent"] = "FAIL (accepted absent claim)"
                logger.error(f"  [FAIL] Editor {mode_name} Negative Absent: incorrectly PASSED")
        except Exception as e:
            results["tests"][f"editor_{mode_name}_neg_absent"] = f"ERROR: {e}"

        # (c) Clean: Well-grounded script
        try:
            dec_clean = edit_script(
                SAMPLE_CANDIDATES[0],
                SCRIPT_CLEAN,
                client=client,
                model=candidate.model_id,
                is_fallback=is_fallback,
            )
            if dec_clean.passed:
                results["tests"][f"editor_{mode_name}_clean"] = "PASS (approved clean script)"
                logger.info(f"  [PASS] Editor {mode_name} Clean Script: correctly approved")
            else:
                results["tests"][f"editor_{mode_name}_clean"] = f"FAIL (rejected clean script: {dec_clean.critique_reason})"
                logger.error(f"  [FAIL] Editor {mode_name} Clean Script: incorrectly REJECTED ({dec_clean.critique_reason})")
        except Exception as e:
            results["tests"][f"editor_{mode_name}_clean"] = f"ERROR: {e}"

    return results


def main():
    all_results = []
    logger.info("Running check_models across all candidate models...")
    for role, candidates in DEFAULT_CANDIDATES.items():
        for c in candidates:
            res = test_candidate_model(c)
            all_results.append(res)

    print("\n" + "="*80)
    print("CHECK_MODELS SUMMARY REPORT: NEGATIVE & CLEAN EDITOR TEST MATRIX")
    print("="*80)
    header = f"{'Model ID':<22} {'Role':<6} {'Picker':<7} {'Script':<7} | {'Norm (a)':<9} {'Norm (b)':<9} {'Norm (c)':<9} | {'Strict (a)':<10} {'Strict (b)':<10} {'Strict (c)':<10}"
    print(header)
    print("-" * 115)

    flash_neg_failures = []

    for r in all_results:
        m_id = r["model_id"]
        role = r["role"]
        t = r["tests"]
        picker_s = "PASS" if "PASS" in t.get("picker", "") else ("-" if role != "flash" else "FAIL")
        scripter_s = "PASS" if "PASS" in t.get("scripter", "") else "FAIL"

        # Normal mode tests
        norm_a = "PASS" if "PASS" in t.get("editor_normal_neg_contradict", "") else "FAIL"
        norm_b = "PASS" if "PASS" in t.get("editor_normal_neg_absent", "") else "FAIL"
        norm_c = "PASS" if "PASS" in t.get("editor_normal_clean", "") else "FAIL"

        # Strict mode tests
        strict_a = "PASS" if "PASS" in t.get("editor_pro_strict_neg_contradict", "") else "FAIL"
        strict_b = "PASS" if "PASS" in t.get("editor_pro_strict_neg_absent", "") else "FAIL"
        strict_c = "PASS" if "PASS" in t.get("editor_pro_strict_clean", "") else "FAIL"

        row = f"{m_id:<22} {role:<6} {picker_s:<7} {scripter_s:<7} | {norm_a:<9} {norm_b:<9} {norm_c:<9} | {strict_a:<10} {strict_b:<10} {strict_c:<10}"
        print(row)

        if role == "flash":
            if norm_a != "PASS" or norm_b != "PASS" or strict_a != "PASS" or strict_b != "PASS":
                flash_neg_failures.append((m_id, norm_a, norm_b, strict_a, strict_b))

    print("-" * 115)
    print("Legend: (a) Contradictory Claim, (b) Absent Claim, (c) Clean Grounded Script")
    print("        PASS on (a) & (b) means the editor CORRECTLY REJECTED the factual distortion.")
    print("        PASS on (c) means the editor CORRECTLY APPROVED the factual script.")
    print("="*80)

    if flash_neg_failures:
        print("\n⚠️ ALERT: One or more Flash candidates FAILED the negative editor test(s) (accepted distortions):")
        for m_id, na, nb, sa, sb in flash_neg_failures:
            print(f"   - {m_id}: normal(a)={na}, normal(b)={nb}, strict(a)={sa}, strict(b)={sb}")
        print("DO NOT call Flash safe. Mitigation required (e.g. second Flash verification pass or mandatory human checklist).\n")
    else:
        print("\n✓ VERIFIED: All Flash candidates passed all negative editor tests (a & b) and clean test (c) in both normal and strict modes.\n")


if __name__ == "__main__":
    main()
