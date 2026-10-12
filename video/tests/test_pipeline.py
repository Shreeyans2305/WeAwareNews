"""
Unit tests for Video Pipeline Components:
- Word budget validation
- Prompt template assembly
- Claim-to-source mapping
- Story picker safety rejection
- Veo budget cap enforcement
- Processor SRT generation
"""

import sys
import pytest
from pathlib import Path

from video.pipeline.scripter import (
    ClipScript,
    ClaimItem,
    ScriptOutput,
    count_words,
    validate_and_trim_word_budget,
    assemble_veo_prompt,
)
from video.pipeline.picker import StoryPickerDecision
from video.pipeline.veo_client import VeoClient, BudgetExceededError
from video.pipeline.processor import generate_subtitles_file
from video.config.settings import settings


# ---------------------------------------------------------------------------
# 1. Word Budget Tests
# ---------------------------------------------------------------------------

def test_word_count():
    assert count_words("Hello, world! This is late night news.") == 7
    assert count_words("") == 0


def test_word_budget_validation_pass():
    script = ScriptOutput(
        headline="Test Headline",
        caption="Test caption",
        hashtags=["test", "comedy"],
        satire_disclosure="AI satire",
        clips=[
            ClipScript(
                clip_index=1,
                duration_seconds=8,
                speaker="marcus",
                dialogue="Good evening. Today scientists confirmed that time travel is real, but only backwards by three seconds. You're welcome.",
                action="Nods wryly",
                camera="Medium close-up shot",
                claims=[ClaimItem(claim_text="Scientists confirmed time travel", source_url="https://example.com/1")],
            ),
            ClipScript(
                clip_index=2,
                duration_seconds=8,
                speaker="marcus",
                dialogue="Wall Street immediately responded by shorting yesterday's decaf futures with great enthusiasm.",
                action="Taps pen",
                camera="Medium close-up shot",
                claims=[],
            ),
        ],
    )
    # Both clips have under 22 words
    assert validate_and_trim_word_budget(script, words_per_sec=2.5) is True


def test_word_budget_validation_fail_over_budget():
    script = ScriptOutput(
        headline="Test Headline",
        caption="Test caption",
        hashtags=["test"],
        satire_disclosure="AI satire",
        clips=[
            ClipScript(
                clip_index=1,
                duration_seconds=8,
                speaker="marcus",
                # 35 words (far exceeds 2.5 * 8 = 20 words)
                dialogue="This is an extremely long dialogue line that goes on and on without any comedic conciseness, exceeding the natural broadcast pacing of television news and ruining the lip-sync quality of our generative video pipeline completely.",
                action="Talks too much",
                camera="Medium shot",
                claims=[],
            )
        ],
    )
    assert validate_and_trim_word_budget(script, words_per_sec=2.5) is False


# ---------------------------------------------------------------------------
# 2. Prompt Assembly Tests
# ---------------------------------------------------------------------------

def test_assemble_veo_prompt():
    clip = ClipScript(
        clip_index=1,
        duration_seconds=8,
        speaker="marcus",
        dialogue="Welcome back to WeAware Late Night.",
        action="He raises an eyebrow with a deadpan smirk",
        camera="Medium close-up shot",
        claims=[],
    )
    mock_anchors_config = {
        "set": {"description": "Modern walnut desk with blue rim lighting."},
        "anchors": [
            {
                "id": "marcus",
                "name": "Marcus Vance",
                "description": "Charismatic host in navy blazer.",
                "voice_description": "Crisp baritone delivery.",
            }
        ],
    }
    prompt = assemble_veo_prompt(clip, mock_anchors_config)

    assert "Medium close-up shot" in prompt
    assert "Marcus Vance" in prompt
    assert "Modern walnut desk" in prompt
    assert "He raises an eyebrow" in prompt
    assert 'Dialogue: "Welcome back to WeAware Late Night."' in prompt or '"Welcome back to WeAware Late Night."' in prompt
    assert "vertical 9:16 framing" in prompt
    assert "no subtitles" in prompt


# ---------------------------------------------------------------------------
# 3. Veo Budget Cap Enforcement Tests
# ---------------------------------------------------------------------------

def test_veo_budget_cap_enforcement():
    client = VeoClient()
    # Set current spend just under cap
    client.total_cost_usd = 24.50

    # settings.max_cost_usd_per_run is $25.00
    # An upcoming 8s clip at $0.15/s = $1.20 -> $24.50 + $1.20 = $25.70 > $25.00
    with pytest.raises(BudgetExceededError):
        client.check_budget_and_claim(upcoming_seconds=8)


# ---------------------------------------------------------------------------
# 4. Processor Subtitle File Generation Tests
# ---------------------------------------------------------------------------

def test_generate_subtitles_file(tmp_path):
    script = ScriptOutput(
        headline="Headline",
        caption="Caption",
        hashtags=["news"],
        satire_disclosure="Satire",
        clips=[
            ClipScript(
                clip_index=1,
                duration_seconds=8,
                speaker="marcus",
                dialogue="First line of dialogue.",
                action="Action 1",
                camera="Medium",
                claims=[],
            ),
            ClipScript(
                clip_index=2,
                duration_seconds=8,
                speaker="maya",
                dialogue="Second line of dialogue.",
                action="Action 2",
                camera="Medium",
                claims=[],
            ),
        ],
    )
    srt_path = tmp_path / "captions.srt"
    generate_subtitles_file(script, srt_path)

    assert srt_path.exists()
    content = srt_path.read_text()
    assert "00:00:00,000 --> 00:00:08,000" in content
    assert "First line of dialogue." in content
    assert "00:00:08,000 --> 00:00:16,000" in content
    assert "Second line of dialogue." in content


def test_check_clip_transcript_diff(tmp_path):
    from unittest.mock import MagicMock
    from video.pipeline.runner import check_clip_transcript

    dummy_clip = tmp_path / "test_clip.mp4"
    dummy_clip.write_bytes(b"fake video data")

    # Mock GenAI client returning exact transcription
    mock_resp = MagicMock()
    mock_resp.text = "Good evening Welcome back to WeAware Late Night"
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_resp

    scripted = "Good evening! Welcome back to WeAware Late Night."
    res = check_clip_transcript(dummy_clip, scripted, genai_client=mock_client)
    assert res["match_ratio"] == 100.0
    assert len(res["mismatches"]) == 0

    # Mock GenAI client returning slight mismatch (e.g. number vs word or missed word)
    mock_resp.text = "Good evening Welcome back to Night"
    res_mismatch = check_clip_transcript(dummy_clip, scripted, genai_client=mock_client)
    assert res_mismatch["match_ratio"] < 100.0
    assert len(res_mismatch["mismatches"]) > 0
    assert "[-weaware late-]" in res_mismatch["diff"]


# ---------------------------------------------------------------------------
# 7. Caption Clamp & 2,200 Char Social Budget Tests
# ---------------------------------------------------------------------------

def test_clamp_caption_under_limit():
    from video.pipeline.text_utils import clamp_caption, format_full_caption

    caption = "A short punchy social caption about the absurd news cycle."
    hashtags = ["#Satire", "#LateNight", "#WeAware"]
    disclosure = "⚠️ AI-generated political satire grounded in verified multi-source news reporting."

    clamped = clamp_caption(caption, hashtags, disclosure, max_total_chars=2200)
    assert clamped == caption

    full = format_full_caption(caption, hashtags, disclosure, max_total_chars=2200)
    assert len(full) <= 2200
    assert caption in full
    assert disclosure in full
    for tag in hashtags:
        assert tag in full


def test_clamp_caption_over_limit_truncates_body_only():
    from video.pipeline.text_utils import clamp_caption, format_full_caption

    # Generate a massive caption (3,000 chars)
    long_caption = " ".join(["Breaking satirical coverage of today's events!"] * 100)
    hashtags = ["#Satire", "#LateNight", "#WeAware", "#ComedyNews"]
    disclosure = "⚠️ AI-generated political satire grounded in verified multi-source news reporting."

    clamped_body = clamp_caption(long_caption, hashtags, disclosure, max_total_chars=2200)
    # The body must be truncated with an ellipsis
    assert clamped_body.endswith("...")
    assert len(clamped_body) < len(long_caption)

    # Combined full post must strictly not exceed 2200 chars
    full_post = format_full_caption(long_caption, hashtags, disclosure, max_total_chars=2200)
    assert len(full_post) <= 2200

    # Critical rule: disclosure and hashtags must NEVER be truncated
    assert disclosure in full_post
    for tag in hashtags:
        assert tag in full_post


# ---------------------------------------------------------------------------
# 8. Notifier & Runner Call Signature & Payload Keys Test
# ---------------------------------------------------------------------------

def test_send_review_notifications_runner_call_signature(monkeypatch):
    from unittest.mock import MagicMock
    from video.pipeline.notifier import send_review_notifications
    import video.pipeline.notifier as notifier_mod

    captured_payloads = []

    def mock_send_webhook(webhook_url, payload, hmac_secret=None, max_retries=3, timeout_sec=10.0):
        captured_payloads.append(payload)
        return True

    monkeypatch.setattr(notifier_mod, "get_secret_value", lambda name: "https://example.com/webhook" if "webhook" in name else "dummy-hmac")
    monkeypatch.setattr(notifier_mod, "send_webhook_with_retry", mock_send_webhook)

    # Mock pubsub
    mock_pubsub = MagicMock()
    mock_pubsub_client = MagicMock()
    mock_future = MagicMock()
    mock_future.result.return_value = "msg-12345"
    mock_pubsub_client.publish.return_value = mock_future
    mock_pubsub.PublisherClient.return_value = mock_pubsub_client
    monkeypatch.setitem(sys.modules, "google.cloud.pubsub_v1", mock_pubsub)

    # Call send_review_notifications EXACTLY with the parameters runner.py passes
    result = send_review_notifications(
        run_id="c0a80101-0000-0000-0000-000000000001",
        story_id="test-story-id-456",
        headline="Astronomers Discover Asteroid Mining Rush",
        video_url="gs://bucket/runs/1/final.mp4",
        thumbnail_url="gs://bucket/runs/1/thumbnail.jpg",
        caption="When the asteroid mining rush begins, will space lawyers take a 30% cut?",
        hashtags=["#Satire", "#LateNight", "#Space"],
        sources=["Reuters", "BBC News"],
        estimated_cost=3.2450,
        gemini_models_used={"flash": "gemini-2.5-flash", "pro": "gemini-2.5-pro"},
        veo_model="veo-3.1-fast-generate-001",
        veo_resolution="720p",
    )

    assert result["webhook"] is True
    assert len(captured_payloads) == 1

    payload = captured_payloads[0]
    expected_keys = {
        "schema_version",
        "event",
        "run_id",
        "story_id",
        "headline",
        "caption",
        "hashtags",
        "sources",
        "review_url",
        "video_preview_url",
        "thumbnail_url",
        "estimated_cost_usd",
        "veo_model",
        "veo_resolution",
        "gemini_models_used",
        "transcript_min_match_ratio",
        "transcript_mismatch_count",
        "error_message",
        "created_at",
    }
    # All 19 JSON keys sent by notifier.py must be present
    assert expected_keys.issubset(set(payload.keys()))
    assert payload["run_id"] == "c0a80101-0000-0000-0000-000000000001"
    assert payload["story_id"] == "test-story-id-456"
    assert payload["estimated_cost_usd"] == 3.2450
    assert payload["veo_model"] == "veo-3.1-fast-generate-001"
    assert payload["gemini_models_used"]["pro"] == "gemini-2.5-pro"

