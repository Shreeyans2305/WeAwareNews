#!/usr/bin/env python3
"""
WeAware Late Night - Main Video Pipeline Runner.
Orchestrates selection, scriptwriting, editorial verification, Veo video generation,
FFmpeg post-production, and review notification.
"""

import argparse
import difflib
import json
import logging
import os
import re
import sys
import time
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from video.config.settings import settings
from video.pipeline.picker import pick_story
from video.pipeline.scripter import generate_script, assemble_veo_prompt
from video.pipeline.editor import edit_script
from video.pipeline.veo_client import VeoClient, BudgetExceededError, ClaimCancelledError
from video.pipeline.processor import process_video_and_metadata
from video.pipeline.notifier import send_review_notifications
from video.bootstrap_assets import load_anchors_config
from video.api.models import VideoCandidateResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("weaware-video.runner")


def check_clip_transcript(
    clip_path: Path,
    scripted_dialogue: str,
    genai_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Transcribes clip audio using Gemini 2.5 Flash and diffs against the scripted line.
    Informational check only (no auto-retry).
    """
    if genai_client is None:
        try:
            from google import genai
            genai_client = genai.Client(
                vertexai=True,
                project=settings.project_id,
                location=settings.location,
            )
        except Exception as e:
            logger.warning(f"Could not initialize GenAI client for transcript check: {e}")
            return {
                "scripted": scripted_dialogue,
                "transcribed": "(Client unavailable)",
                "match_ratio": 0.0,
                "mismatches": [f"GenAI init error: {e}"],
                "diff": "",
            }

    try:
        from google.genai import types
        clip_bytes = clip_path.read_bytes()
        prompt = (
            "Listen carefully to the spoken voice in this video clip. "
            "Transcribe the spoken words exactly word-for-word. "
            "Output ONLY the transcribed words with no commentary or formatting."
        )
        resp = genai_client.models.generate_content(
            model=settings.gemini_flash_model,
            contents=[
                types.Part.from_bytes(data=clip_bytes, mime_type="video/mp4"),
                prompt,
            ],
        )
        transcribed = resp.text.strip() if resp.text else ""
    except Exception as e:
        logger.warning(f"Gemini transcript check failed for {clip_path.name}: {e}")
        return {
            "scripted": scripted_dialogue,
            "transcribed": "(Transcript unavailable)",
            "match_ratio": 0.0,
            "mismatches": [f"Audio transcription error: {str(e)}"],
            "diff": "",
        }

    # Normalize tokens for comparison
    def norm_tokens(text: str) -> List[str]:
        return re.findall(r"\b[a-zA-Z0-9']+\b", text.lower())

    s_tokens = norm_tokens(scripted_dialogue)
    t_tokens = norm_tokens(transcribed)

    matcher = difflib.SequenceMatcher(None, s_tokens, t_tokens)
    ratio = matcher.ratio()

    mismatches = []
    diff_tokens = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            diff_tokens.extend(s_tokens[i1:i2])
        elif tag == "replace":
            s_sub = " ".join(s_tokens[i1:i2])
            t_sub = " ".join(t_tokens[j1:j2])
            mismatches.append(f"Expected '{s_sub}' but heard '{t_sub}'")
            diff_tokens.append(f"[-{s_sub}-]{{+{t_sub}+}}")
        elif tag == "delete":
            s_del = " ".join(s_tokens[i1:i2])
            mismatches.append(f"Omitted: '{s_del}'")
            diff_tokens.append(f"[-{s_del}-]")
        elif tag == "insert":
            t_ins = " ".join(t_tokens[j1:j2])
            mismatches.append(f"Inserted: '{t_ins}'")
            diff_tokens.append(f"{{+{t_ins}+}}")

    diff_str = " ".join(diff_tokens)

    return {
        "scripted": scripted_dialogue,
        "transcribed": transcribed,
        "match_ratio": round(ratio * 100, 1),
        "mismatches": mismatches,
        "diff": diff_str,
    }


def fetch_candidates_from_api(api_url: str, api_key: str, limit: int = 10) -> List[VideoCandidateResponse]:
    import urllib.request
    req_url = f"{api_url}/stories/video-candidates?limit={limit}&min_sources=2&dedupe_days={settings.video_dedupe_days}"
    headers = {"x-api-key": api_key} if api_key else {}
    req = urllib.request.Request(req_url, headers=headers)

    logger.info(f"Fetching candidate stories from: {req_url}")
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status == 204:
            return []
        data = json.loads(resp.read().decode("utf-8"))
        return [VideoCandidateResponse.model_validate(c) for c in data]


def claim_story_via_api(
    api_url: str,
    api_key: str,
    candidate: VideoCandidateResponse,
    claim_mode: str = "separate",
) -> Dict[str, Any]:
    import urllib.request
    req_url = f"{api_url}/stories/{candidate.story_id}/video-claim"
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    body = {
        "claim_mode": claim_mode,
        "timeout_minutes": settings.claim_timeout_minutes,
        "headline_snapshot": candidate.headline,
        "sources_snapshot": [a.model_dump() for a in candidate.articles],
        "source_urls": candidate.source_urls,
        "story_text_snapshot": candidate.combined_story_text,
    }
    req = urllib.request.Request(req_url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def update_status_via_api(
    api_url: str,
    api_key: str,
    run_id: str,
    expected_status: str,
    new_status: str,
    **kwargs,
) -> Dict[str, Any]:
    import urllib.request
    req_url = f"{api_url}/videos/{run_id}/status"
    headers = {"x-api-key": api_key, "Content-Type": "application/json"}
    payload = {
        "expected_status": expected_status,
        "new_status": new_status,
        **kwargs,
    }
    req = urllib.request.Request(req_url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def upload_to_gcs(local_path: Path, gcs_uri: str) -> None:
    cmd = ["gcloud", "storage", "cp", str(local_path), gcs_uri]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        logger.error(f"Upload to GCS failed: {res.stderr}")
        raise RuntimeError(f"GCS upload failed: {res.stderr}")


def run_pipeline(
    story_id_override: Optional[str] = None,
    dry_run: bool = False,
    tier: Optional[str] = None,
):
    if tier:
        settings.veo_model_tier = tier

    logger.info("=" * 65)
    logger.info(f"STARTING WEAWARE LATE NIGHT PIPELINE (dry_run={dry_run}, tier={settings.veo_model_tier})")
    logger.info("=" * 65)

    anchors_config = load_anchors_config()
    api_url = settings.video_api_url
    api_key = settings.api_key

    # 1. Fetch Candidates
    candidates = fetch_candidates_from_api(api_url, api_key, limit=10)
    if not candidates:
        logger.info("No eligible corroborated video candidates found. Exiting cleanly.")
        return

    # Handle story_id override if requested
    if story_id_override:
        matching = [c for c in candidates if c.story_id == story_id_override]
        if not matching:
            logger.error(f"Specified story_id {story_id_override} not found in eligible candidates.")
            sys.exit(1)
        candidates = matching

    # 2. Story Selection
    chosen_candidate, picker_decision, fallbacks = pick_story(candidates)
    logger.info(f"Selected Candidate: {chosen_candidate.headline} (Story ID: {chosen_candidate.story_id})")

    # 3. Dry-run Mode check
    if dry_run:
        logger.info("\n[DRY RUN MODE] Testing script generation and editor pass against chosen candidate...")
        script = generate_script(chosen_candidate, anchors_config=anchors_config)
        editor_decision = edit_script(chosen_candidate, script)
        logger.info(f"Generated Headline: {script.headline}")
        logger.info(f"Clips Plan Count: {len(script.clips)}")
        logger.info(f"Editor Pass Verdict: {'PASSED' if editor_decision.passed else 'FAILED'}")
        logger.info("[DRY RUN COMPLETE] Success.")
        return

    # 4. Atomic Claim
    claim_info = claim_story_via_api(api_url, api_key, chosen_candidate)
    run_id = claim_info["run_id"]
    logger.info(f"✓ Atomically claimed run_id: {run_id}")

    # Helper for heartbeats
    def send_heartbeat():
        try:
            update_status_via_api(api_url, api_key, run_id, "generating_video", "generating_video", heartbeat=True)
            return True
        except Exception as e:
            logger.warning(f"Heartbeat failed: {e}")
            return False

    current_candidate = chosen_candidate
    fallback_pool = list(fallbacks)
    script = None
    editor_decision = None

    # 5. Script & Editor Loop with fallback
    for attempt in range(settings.max_editor_fallbacks + 1):
        update_status_via_api(api_url, api_key, run_id, "claimed", "scripting")
        logger.info(f"Writing satirical script for {current_candidate.headline}...")
        script = generate_script(current_candidate, anchors_config=anchors_config)

        logger.info("Conducting Standards & Practices Editor pass...")
        editor_decision = edit_script(current_candidate, script)

        if editor_decision.passed:
            logger.info("✓ Script passed editor review.")
            break
        else:
            logger.warning(f"Editor flagged script: {editor_decision.critique_reason}")
            if fallback_pool:
                current_candidate = fallback_pool.pop(0)
                logger.info(f"Falling back to candidate: {current_candidate.headline}")
            else:
                logger.error("No more fallback candidates available.")
                update_status_via_api(api_url, api_key, run_id, "scripting", "failed", error_message="Editor rejected script, no fallbacks")
                sys.exit(1)

    # 6. Veo Video Generation
    update_status_via_api(api_url, api_key, run_id, "scripting", "generating_video")
    veo_client = VeoClient(run_id=run_id, heartbeat_callback=send_heartbeat)

    run_dir = Path("video/scratch") / f"run_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Load anchor plate
    plate_path = Path("video/scratch/anchor_plate.png")
    anchor_bytes = plate_path.read_bytes() if plate_path.exists() else b""

    clip_paths = []
    try:
        for clip in script.clips:
            clip_prompt = assemble_veo_prompt(clip, anchors_config)
            clip_file = run_dir / f"clip_{clip.clip_index}.mp4"
            logger.info(f"Generating Clip {clip.clip_index}/4 ({clip.duration_seconds}s)...")
            veo_client.generate_single_clip(
                prompt=clip_prompt,
                anchor_plate_bytes=anchor_bytes,
                duration_seconds=clip.duration_seconds,
                output_path=clip_file,
                mock_mode=False,
            )
            clip_paths.append(clip_file)

    except Exception as e:
        logger.error(f"Video generation aborted: {e}")
        update_status_via_api(
            api_url, api_key, run_id, "generating_video", "failed",
            error_message=str(e),
            estimated_cost_usd=veo_client.total_cost_usd,
            veo_seconds_used=veo_client.total_veo_seconds_spent,
        )
        sys.exit(1)

    # 6b. Automated post-generation transcript verification (Gemini Flash audio input)
    transcript_checks = []
    if not dry_run:
        logger.info("Running automatic post-generation transcript verification with Gemini Flash audio...")
        for clip, clip_file in zip(script.clips, clip_paths):
            check_res = check_clip_transcript(clip_file, clip.dialogue)
            check_res["clip_index"] = clip.clip_index
            check_res["speaker"] = clip.speaker
            transcript_checks.append(check_res)
            logger.info(
                f"Clip {clip.clip_index} Transcript Match: {check_res['match_ratio']}% "
                f"({len(check_res['mismatches'])} mismatches)"
            )

    # 7. Post-Production (FFmpeg)
    update_status_via_api(api_url, api_key, run_id, "generating_video", "post_processing")
    source_names = [a.source_name for a in current_candidate.articles]

    run_metadata = {
        "run_id": run_id,
        "story_id": current_candidate.story_id,
        "headline": script.headline,
        "caption": script.caption,
        "hashtags": script.hashtags,
        "satire_disclosure": script.satire_disclosure,
        "claims": [c.model_dump() for clip in script.clips for c in clip.claims],
        "veo_model": settings.active_veo_model,
        "estimated_cost_usd": veo_client.total_cost_usd,
        "veo_seconds_used": veo_client.total_veo_seconds_spent,
        "transcript_checks": transcript_checks,
    }

    artifacts = process_video_and_metadata(
        clip_paths=clip_paths,
        script=script,
        source_names=source_names,
        output_dir=run_dir,
        run_metadata=run_metadata,
        mock_mode=False,
    )

    # Upload final artifacts to GCS
    gcs_run_prefix = f"gs://{settings.gcs_bucket}/runs/{run_id}"
    upload_to_gcs(artifacts["video"], f"{gcs_run_prefix}/final.mp4")
    upload_to_gcs(artifacts["thumbnail"], f"{gcs_run_prefix}/thumbnail.jpg")
    upload_to_gcs(artifacts["metadata"], f"{gcs_run_prefix}/metadata.json")

    # 8. Mark Ready For Review & Notify
    final_video_gcs = f"{gcs_run_prefix}/final.mp4"
    final_thumb_gcs = f"{gcs_run_prefix}/thumbnail.jpg"

    update_status_via_api(
        api_url, api_key, run_id, "post_processing", "ready_for_review",
        video_gcs_uri=final_video_gcs,
        thumbnail_gcs_uri=final_thumb_gcs,
        caption=script.caption,
        hashtags=script.hashtags,
        script_data=script.model_dump(),
        claims_data=[c.model_dump() for clip in script.clips for c in clip.claims],
        run_metadata=run_metadata,
        estimated_cost_usd=veo_client.total_cost_usd,
        veo_seconds_used=veo_client.total_veo_seconds_spent,
    )

    logger.info("✓ Dispatched review notifications via Pub/Sub and Webhook.")
    send_review_notifications(
        run_id=run_id,
        headline=script.headline,
        video_url=final_video_gcs,
        caption=script.caption,
        estimated_cost=veo_client.total_cost_usd,
    )

    logger.info(f"✓ Pipeline run {run_id} completed successfully and is ready for review!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WeAware Late Night Video Pipeline Runner")
    parser.add_argument("--story-id", help="Override and force specific story_id")
    parser.add_argument("--dry-run", action="store_true", help="Mocks Veo and tests selection + script generation read-only")
    parser.add_argument("--tier", choices=["fast", "standard"], help="Veo model tier (fast | standard)")
    args = parser.parse_args()

    run_pipeline(
        story_id_override=args.story_id,
        dry_run=args.dry_run,
        tier=args.tier,
    )
