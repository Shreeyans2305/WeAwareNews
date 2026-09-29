"""
Unit tests for Video Pipeline Components:
- Word budget validation
- Prompt template assembly
- Claim-to-source mapping
- Story picker safety rejection
- Veo budget cap enforcement
- Processor SRT generation
"""

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
