#!/usr/bin/env python3
"""Read-only picker and Phase 1 diagnosis for recent video candidates."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from google import genai

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from video.api.models import VideoCandidateResponse
from video.bootstrap_assets import load_anchors_config
from video.config.model_selector import select_model
from video.config.settings import settings
from video.pipeline.editor import edit_script
from video.pipeline.picker import has_wire_service, pick_story
from video.pipeline.runner import fetch_candidates_from_api
from video.pipeline.scripter import (
    ClaimLedger,
    ScriptRejected,
    StoryIneligible,
    extract_claim_ledger,
    generate_script,
    validate_story_eligibility,
    word_budget_details,
)


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_stale(candidate: VideoCandidateResponse, hours: int) -> bool:
    published = [parse_timestamp(article.published_at) for article in candidate.articles]
    known = [value for value in published if value is not None]
    return bool(known) and max(known) < datetime.now(timezone.utc) - timedelta(hours=hours)


def secure_secret(secret_name: str, project: str) -> str:
    result = subprocess.run(
        [
            "gcloud",
            "secrets",
            "versions",
            "access",
            "latest",
            f"--secret={secret_name}",
            f"--project={project}",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class _ThrottledModels:
    def __init__(self, models: Any, minimum_interval: float):
        self._models = models
        self._minimum_interval = minimum_interval
        self._last_call = 0.0

    def generate_content(self, *args: Any, **kwargs: Any) -> Any:
        remaining = self._minimum_interval - (time.monotonic() - self._last_call)
        if remaining > 0:
            time.sleep(remaining)
        self._last_call = time.monotonic()
        return self._models.generate_content(*args, **kwargs)


class _ThrottledClient:
    def __init__(self, client: genai.Client, minimum_interval: float):
        self.models = _ThrottledModels(client.models, minimum_interval)


def diagnose(
    candidate: VideoCandidateResponse,
    pro_client: genai.Client,
    pro_model: str,
    existing_ledger: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "story_id": candidate.story_id,
        "headline": candidate.headline,
        "source_count": candidate.source_count,
        "sources": [article.source_name for article in candidate.articles],
        "wire_service": has_wire_service(candidate),
        "stale_over_72h": is_stale(candidate, 72),
    }
    if candidate.source_count < 2 or len({a.source_name.strip().lower() for a in candidate.articles}) < 2:
        result.update(primary_result="rejected", primary_reason="single source")
        return result

    try:
        ledger = ClaimLedger.model_validate(existing_ledger) if existing_ledger else extract_claim_ledger(candidate, pro_client, pro_model)
        result["claim_ledger"] = ledger.model_dump()
        result["claim_type_counts"] = dict(Counter(entry.claim_type for entry in ledger.entries))
        validate_story_eligibility(ledger)
    except StoryIneligible as exc:
        entries = result.get("claim_ledger", {}).get("entries", [])
        characterized_response = any(
            entry.get("is_response") and entry.get("claim_type") == "outlet_characterization"
            for entry in entries
        )
        reason = "only outlet characterization" if characterized_response else "no counter-voice"
        result.update(primary_result="rejected", primary_reason=reason, detail=str(exc))
        return result
    except Exception as exc:  # Diagnostic must continue through the whole candidate set.
        result.update(primary_result="rejected", primary_reason="other", detail=f"ledger error: {exc}")
        return result

    try:
        script = generate_script(
            candidate,
            client=pro_client,
            anchors_config=load_anchors_config(),
            model=pro_model,
            ledger=ledger,
        )
        result["script"] = script.model_dump()
        result["word_counts"] = [
            {"clip": clip, "words": words, "maximum": maximum}
            for clip, words, maximum in word_budget_details(script)
        ]
    except ScriptRejected as exc:
        reason = "word budget" if "word" in str(exc).lower() else "other"
        result.update(primary_result="rejected", primary_reason=reason, detail=str(exc))
        return result
    except Exception as exc:
        result.update(primary_result="rejected", primary_reason="other", detail=f"script error: {exc}")
        return result

    try:
        editor = edit_script(candidate, script, client=pro_client, model=pro_model)
        result["editor"] = editor.model_dump()
        if not editor.passed:
            result.update(primary_result="rejected", primary_reason="other", detail=editor.critique_reason)
            return result
    except Exception as exc:
        result.update(primary_result="rejected", primary_reason="other", detail=f"editor error: {exc}")
        return result

    result.update(primary_result="passed", primary_reason="passed")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--secret-project", default=settings.project_id)
    parser.add_argument("--secret-name", default="video-api-key")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume-quota-errors", action="store_true")
    parser.add_argument("--minimum-call-interval", type=float, default=0.0)
    args = parser.parse_args()

    api_key = secure_secret(args.secret_name, args.secret_project)
    candidates = fetch_candidates_from_api(args.api_url, api_key, limit=args.limit)
    flash = select_model("flash")
    pro = select_model("pro")
    flash_client = genai.Client(vertexai=True, project=settings.project_id, location=flash.location)
    raw_pro_client = genai.Client(vertexai=True, project=settings.project_id, location=pro.location)
    pro_client: Any = _ThrottledClient(raw_pro_client, args.minimum_call_interval)

    if args.resume_quota_errors:
        report = json.loads(args.output.read_text(encoding="utf-8"))
        candidate_map = {candidate.story_id: candidate for candidate in candidates}
        quota_rows = [
            row for row in report["results"]
            if "429" in row.get("detail", "") or "RESOURCE_EXHAUSTED" in row.get("detail", "")
        ]
        for index, row in enumerate(quota_rows, 1):
            candidate = candidate_map.get(row["story_id"])
            if candidate is None:
                continue
            print(f"[quota rerun {index}/{len(quota_rows)}] {candidate.story_id} {candidate.headline[:80]}", flush=True)
            replacement = diagnose(candidate, pro_client, pro.model_id, row.get("claim_ledger"))
            report["results"][report["results"].index(row)] = replacement
            args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        report["primary_reason_totals"] = dict(Counter(row["primary_reason"] for row in report["results"]))
        report["diagnostic_flag_totals"] = {
            "no wire service": sum(not row["wire_service"] for row in report["results"]),
            "stale": sum(row["stale_over_72h"] for row in report["results"]),
        }
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({
            "quota_rows_remaining": sum(
                "429" in row.get("detail", "") or "RESOURCE_EXHAUSTED" in row.get("detail", "")
                for row in report["results"]
            ),
            "primary_reason_totals": report["primary_reason_totals"],
        }, indent=2))
        return 0

    chosen, picker, _fallbacks = pick_story(candidates, client=flash_client, model=flash.model_id)
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_count": len(candidates),
        "models": {"picker": flash.model_id, "phase1": pro.model_id},
        "picker": picker.model_dump(),
        "picker_chosen_story_id": chosen.story_id,
        "results": [],
    }
    for index, candidate in enumerate(candidates, 1):
        print(f"[{index}/{len(candidates)}] {candidate.story_id} {candidate.headline[:80]}", flush=True)
        report["results"].append(diagnose(candidate, pro_client, pro.model_id))

    report["primary_reason_totals"] = dict(Counter(row["primary_reason"] for row in report["results"]))
    report["diagnostic_flag_totals"] = {
        "no wire service": sum(not row["wire_service"] for row in report["results"]),
        "stale": sum(row["stale_over_72h"] for row in report["results"]),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({
        "candidate_count": report["candidate_count"],
        "picker_chosen_story_id": report["picker_chosen_story_id"],
        "primary_reason_totals": report["primary_reason_totals"],
        "diagnostic_flag_totals": report["diagnostic_flag_totals"],
        "output": str(args.output),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
