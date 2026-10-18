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
import shutil
import sys
import time
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from video.config.settings import settings
from video.config.model_selector import select_model
from video.pipeline.picker import pick_story
from video.pipeline.scripter import ScriptOutput, ScriptRejected, StoryIneligible, generate_script, assemble_veo_prompt, spoken_tokens
from video.pipeline.editor import edit_script
from video.pipeline.veo_client import VeoClient, BudgetExceededError, ClaimCancelledError, VeoGenerationError
from video.pipeline.processor import process_video_and_metadata, trim_clip_to_speech_end
from video.pipeline.media_gates import inspect_clip_media
from video.pipeline.notifier import send_review_notifications
from video.bootstrap_assets import load_anchors_config
from video.api.models import VideoCandidateResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("weaware-video.runner")


def fail_scripting_run(
    api_url: str,
    api_key: str,
    run_id: str,
    candidate: VideoCandidateResponse,
    reason: str,
    gemini_models_used: Optional[Dict[str, str]] = None,
) -> None:
    """Fail the run, thereby releasing its active story claim, and notify downstream systems."""
    clear_reason = f"Script rejected: {reason}"[:2000]
    update_status_via_api(
        api_url,
        api_key,
        run_id,
        "scripting",
        "failed",
        error_message=clear_reason,
    )
    send_review_notifications(
        event="failed",
        run_id=run_id,
        story_id=candidate.story_id,
        headline=candidate.headline,
        sources=[article.source_name for article in candidate.articles],
        error_message=clear_reason,
        gemini_models_used=gemini_models_used or {},
        api_base_url=api_url,
    )


def fail_active_run(
    api_url: str,
    api_key: str,
    run_id: str,
    candidate: VideoCandidateResponse,
    expected_status: str,
    reason: str,
    estimated_cost: float = 0.0,
    veo_seconds_used: int = 0,
    gemini_models_used: Optional[Dict[str, str]] = None,
) -> None:
    """Fail any active pipeline stage and always dispatch the stable failed event."""
    clear_reason = str(reason)[:2000]
    update_status_via_api(
        api_url,
        api_key,
        run_id,
        expected_status,
        "failed",
        error_message=clear_reason,
        estimated_cost_usd=estimated_cost,
        veo_seconds_used=veo_seconds_used,
    )
    send_review_notifications(
        event="failed",
        run_id=run_id,
        story_id=candidate.story_id,
        headline=candidate.headline,
        sources=[article.source_name for article in candidate.articles],
        error_message=clear_reason,
        estimated_cost=estimated_cost,
        gemini_models_used=gemini_models_used or {},
        api_base_url=api_url,
    )


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
        return [token.lower().replace("’", "'") for token in spoken_tokens(text)]

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
    approved_diagnostic_report: Optional[Path] = None,
    reuse_clip_dir: Optional[Path] = None,
):
    if tier:
        settings.veo_model_tier = tier

    # Model Selection
    flash_selection = select_model("flash")
    pro_selection = select_model("pro")
    is_pro_fallback = (pro_selection.reason == "pro_unavailable_flash_fallback")

    logger.info("=" * 65)
    logger.info(f"STARTING WEAWARE LATE NIGHT PIPELINE (dry_run={dry_run}, tier={settings.veo_model_tier})")
    logger.info(f"Selected Models: Flash={flash_selection.model_id} ({flash_selection.reason}), Pro={pro_selection.model_id} ({pro_selection.reason})")
    if is_pro_fallback:
        logger.warning(
            "STARTUP LOG: pro_unavailable_flash_fallback - No GA candidate remains for 'pro'. "
            f"Editor and pro-role calls falling back to Flash model {pro_selection.model_id} ({pro_selection.location})."
        )
    logger.info("=" * 65)

    anchors_config = load_anchors_config()
    api_url = settings.video_api_url
    api_key = settings.api_key

    # 1. Fetch Candidates
    # A direct story override bypasses ranking, not candidate/API eligibility or
    # any downstream claim-ledger, neutrality, word-budget, or editor gate.
    candidates = fetch_candidates_from_api(api_url, api_key, limit=50 if story_id_override else 10)
    if not candidates:
        logger.info("No eligible corroborated video candidates found. Exiting cleanly.")
        return

    # Handle story_id override if requested
    if story_id_override:
        matching = [c for c in candidates if c.story_id == story_id_override]
        if not matching:
            logger.error(f"Specified story_id {story_id_override} not found in eligible candidates.")
            sys.exit(1)
        chosen_candidate = matching[0]
        fallbacks = []
        logger.info(
            "Picker bypassed by explicit --story-id=%s; all Phase 1 editorial gates remain enabled.",
            story_id_override,
        )
    else:
        # 2. Story Selection
        chosen_candidate, _picker_decision, fallbacks = pick_story(candidates, model=flash_selection.model_id)
    logger.info(f"Selected Candidate: {chosen_candidate.headline} (Story ID: {chosen_candidate.story_id})")

    # 3. Dry-run Mode check
    if dry_run:
        logger.info("\n[DRY RUN MODE] Testing script generation and editor pass against chosen candidate...")
        script = generate_script(chosen_candidate, anchors_config=anchors_config, model=pro_selection.model_id)
        editor_decision = edit_script(chosen_candidate, script, model=pro_selection.model_id, is_fallback=is_pro_fallback)
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

    update_status_via_api(api_url, api_key, run_id, "claimed", "scripting")

    approved_script: Optional[ScriptOutput] = None
    if approved_diagnostic_report:
        report = json.loads(approved_diagnostic_report.read_text(encoding="utf-8"))
        row = next((item for item in report.get("results", []) if item.get("story_id") == current_candidate.story_id), None)
        if not row or not row.get("script"):
            fail_scripting_run(
                api_url, api_key, run_id, current_candidate,
                "Approved diagnostic report does not contain the selected story script",
                {"flash": flash_selection.model_id, "pro": pro_selection.model_id},
            )
            return
        approved_script = ScriptOutput.model_validate(row["script"])
        logger.info("Loaded the user-approved script verbatim from %s", approved_diagnostic_report)

    # 5. Script & Editor Loop with fallback
    script_attempts = 1 if approved_script else settings.max_editor_fallbacks + 1
    for attempt in range(script_attempts):
        try:
            if approved_script:
                script = approved_script
            else:
                logger.info(
                    "Writing neutral broadcast script for %s (attempt %s, model=%s)...",
                    current_candidate.headline, attempt + 1, pro_selection.model_id,
                )
                script = generate_script(current_candidate, anchors_config=anchors_config, model=pro_selection.model_id)
        except (ScriptRejected, StoryIneligible) as exc:
            logger.error("Scripting failed closed: %s", exc)
            fail_scripting_run(
                api_url,
                api_key,
                run_id,
                current_candidate,
                str(exc),
                {"flash": flash_selection.model_id, "pro": pro_selection.model_id},
            )
            return

        logger.info(f"Conducting Standards & Practices Editor pass (model={pro_selection.model_id}, fallback={is_pro_fallback})...")
        editor_decision = edit_script(current_candidate, script, model=pro_selection.model_id, is_fallback=is_pro_fallback)

        if editor_decision.passed:
            logger.info("✓ Script passed editor review.")
            break
        else:
            logger.warning(f"Editor flagged script: {editor_decision.critique_reason}")
            if fallback_pool and not approved_script:
                current_candidate = fallback_pool.pop(0)
                logger.info(f"Falling back to candidate: {current_candidate.headline}")
            else:
                logger.error("No more fallback candidates available.")
                fail_scripting_run(
                    api_url,
                    api_key,
                    run_id,
                    current_candidate,
                    f"Editor rejected script: {editor_decision.critique_reason}",
                    {"flash": flash_selection.model_id, "pro": pro_selection.model_id},
                )
                return

    # 6. Veo Video Generation
    update_status_via_api(api_url, api_key, run_id, "scripting", "generating_video")
    veo_client = VeoClient(run_id=run_id, heartbeat_callback=send_heartbeat)

    run_dir = Path("video/scratch") / f"run_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    clip_paths = []
    media_checks = []
    try:
        from google import genai
        media_client = genai.Client(
            vertexai=True,
            project=settings.project_id,
            location=flash_selection.location,
        )
        for clip in script.clips:
            # Resolve conditioning plate for this clip
            speaker = getattr(clip, "speaker", "marcus") or "marcus"
            framing = "medium" if "medium" in (getattr(clip, "camera", "") or "").lower() else "wide"
            candidate_plate_paths = [
                *([Path("video/assets/anchors/maya_medium_cool_studio_v3_safe.png")] if speaker == "maya" else []),
                *([Path("video/assets/anchors/maya_medium_cool_studio_v2.png")] if speaker == "maya" else []),
                Path(f"video/assets/anchors/{speaker}_{framing}.png"),
                Path(f"video/assets/anchors/{speaker}_medium.png"),
                Path("video/assets/anchors/marcus_medium.png"),
                Path("video/scratch/anchor_plate.png"),
                Path("video/assets/sets/studio_main.png"),
            ]
            anchor_bytes = b""
            for p in candidate_plate_paths:
                if p.exists():
                    anchor_bytes = p.read_bytes()
                    break

            clip_prompt = assemble_veo_prompt(clip, anchors_config)
            reusable_clip = reuse_clip_dir / f"clip_{clip.clip_index}_attempt_1.mp4" if reuse_clip_dir else None
            if reusable_clip and reusable_clip.exists():
                reused_file = run_dir / f"clip_{clip.clip_index}_reused.mp4"
                shutil.copy2(reusable_clip, reused_file)
                inspection = inspect_clip_media(
                    reused_file,
                    clip.dialogue,
                    client=media_client,
                    model=flash_selection.model_id,
                )
                inspection.update({
                    "clip_index": clip.clip_index,
                    "speaker": clip.speaker,
                    "generation_attempt": 0,
                    "reused_from": str(reusable_clip),
                })
                media_checks.append(inspection)
                logger.info(
                    "Reused clip %s gates: transcript=%.3f audio_passed=%s prohibited=%s",
                    clip.clip_index,
                    inspection["match_ratio"],
                    inspection["audio_passed"],
                    inspection["prohibited_audio"],
                )
                if inspection["transcript_passed"] and inspection["audio_passed"]:
                    trimmed = trim_clip_to_speech_end(reused_file, inspection["speech_end_seconds"], tail_seconds=0.3)
                    clip_paths.append(trimmed)
                    continue
                logger.warning("Reusable clip %s failed current media gates; generating it again.", clip.clip_index)
            for media_attempt in range(2):
                clip_file = run_dir / f"clip_{clip.clip_index}_attempt_{media_attempt + 1}.mp4"
                logger.info(
                    "Generating clip %s/4 (%ss), media attempt %s/2...",
                    clip.clip_index, clip.duration_seconds, media_attempt + 1,
                )
                veo_client.generate_single_clip(
                    prompt=clip_prompt,
                    anchor_plate_bytes=anchor_bytes,
                    duration_seconds=clip.duration_seconds,
                    output_path=clip_file,
                    mock_mode=False,
                )
                inspection = inspect_clip_media(
                    clip_file,
                    clip.dialogue,
                    client=media_client,
                    model=flash_selection.model_id,
                )
                inspection["clip_index"] = clip.clip_index
                inspection["speaker"] = clip.speaker
                inspection["generation_attempt"] = media_attempt + 1
                media_checks.append(inspection)
                logger.info(
                    "Clip %s gates: transcript=%.3f audio_passed=%s prohibited=%s",
                    clip.clip_index,
                    inspection["match_ratio"],
                    inspection["audio_passed"],
                    inspection["prohibited_audio"],
                )
                if inspection["transcript_passed"] and inspection["audio_passed"]:
                    trimmed = trim_clip_to_speech_end(clip_file, inspection["speech_end_seconds"], tail_seconds=0.3)
                    clip_paths.append(trimmed)
                    break
                if media_attempt == 0:
                    logger.warning("Clip %s failed a media gate; regenerating once.", clip.clip_index)
                    continue
                raise VeoGenerationError(
                    f"Clip {clip.clip_index} failed after one regeneration: "
                    f"transcript_match={inspection['match_ratio']:.3f}, "
                    f"prohibited_audio={inspection['prohibited_audio']}"
                )

    except Exception as e:
        logger.error(f"Video generation aborted: {e}")
        fail_active_run(
            api_url, api_key, run_id, current_candidate, "generating_video", str(e),
            veo_client.total_cost_usd,
            veo_client.total_veo_seconds_spent,
            {"flash": flash_selection.model_id, "pro": pro_selection.model_id},
        )
        return

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
        "transcript_checks": media_checks,
        "audio_gate_passed": all(check["audio_passed"] for check in media_checks),
        "pro_model": pro_selection.model_id,
        "flash_model": flash_selection.model_id,
        "pro_selection_reason": pro_selection.reason,
        "pro_unavailable_flash_fallback": is_pro_fallback,
        "editor_fallback_active": is_pro_fallback,
        **({"model_fallback_reason": "pro_unavailable_flash_fallback"} if is_pro_fallback else {}),
    }

    try:
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
    except Exception as exc:
        logger.error("Post-processing or upload failed: %s", exc)
        fail_active_run(
            api_url, api_key, run_id, current_candidate, "post_processing", str(exc),
            veo_client.total_cost_usd,
            veo_client.total_veo_seconds_spent,
            {"flash": flash_selection.model_id, "pro": pro_selection.model_id},
        )
        return

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
    notification_result = send_review_notifications(
        run_id=run_id,
        story_id=current_candidate.story_id,
        headline=script.headline,
        video_url=final_video_gcs,
        thumbnail_url=final_thumb_gcs,
        caption=script.caption,
        hashtags=script.hashtags,
        sources=source_names,
        estimated_cost=veo_client.total_cost_usd,
        gemini_models_used={"flash": flash_selection.model_id, "pro": pro_selection.model_id},
        veo_model=settings.active_veo_model,
        veo_resolution=settings.veo_resolution,
        transcript_min_match_ratio=min(check["match_ratio"] for check in media_checks),
        transcript_mismatch_count=sum(not check["transcript_passed"] for check in media_checks),
    )

    if notification_result.get("review_url"):
        logger.info("REVIEW LINK (terminal only): %s", notification_result["review_url"])

    logger.info(f"✓ Pipeline run {run_id} completed successfully and is ready for review!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WeAware Late Night Video Pipeline Runner")
    parser.add_argument(
        "--story-id",
        help="Bypass picker ranking for this eligible story_id; all editorial gates still run",
    )
    parser.add_argument("--dry-run", action="store_true", help="Mocks Veo and tests selection + script generation read-only")
    parser.add_argument("--tier", choices=["fast", "standard"], help="Veo model tier (fast | standard)")
    parser.add_argument(
        "--approved-diagnostic-report",
        type=Path,
        help="Load the exact approved script for --story-id from a diagnostic JSON report; editor gates still run",
    )
    parser.add_argument(
        "--reuse-clip-dir",
        type=Path,
        help="Reinspect and reuse passing clip_N_attempt_1.mp4 files before generating missing clips",
    )
    args = parser.parse_args()

    run_pipeline(
        story_id_override=args.story_id,
        dry_run=args.dry_run,
        tier=args.tier,
        approved_diagnostic_report=args.approved_diagnostic_report,
        reuse_clip_dir=args.reuse_clip_dir,
    )
