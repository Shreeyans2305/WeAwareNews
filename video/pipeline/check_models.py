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
from video.pipeline.scripter import generate_script, ClipScript
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

    # 3. Test Editor if flash
    if candidate.role == "flash" and results["tests"].get("scripter") == "PASS":
        try:
            decision = edit_script(
                SAMPLE_CANDIDATES[0],
                script,
                client=client,
                model=candidate.model_id,
            )
            assert isinstance(decision.passed, bool)
            results["tests"]["editor"] = "PASS"
            logger.info(f"  [PASS] Editor: passed={decision.passed}")
        except Exception as e:
            results["tests"]["editor"] = f"FAIL: {e}"
            logger.error(f"  [FAIL] Editor: {e}")

    return results


def main():
    all_results = []
    logger.info("Running check_models across all candidate models...")
    for role, candidates in DEFAULT_CANDIDATES.items():
        for c in candidates:
            res = test_candidate_model(c)
            all_results.append(res)

    print("\n" + "="*60)
    print("CHECK_MODELS SUMMARY REPORT")
    print("="*60)
    for r in all_results:
        print(f"Model: {r['model_id']:<24} Location: {r['location']:<12} Role: {r['role']}")
        for tname, tstatus in r["tests"].items():
            print(f"   - {tname:<12}: {tstatus}")
    print("="*60)


if __name__ == "__main__":
    from typing import Dict
    main()
