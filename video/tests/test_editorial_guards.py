import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from video.api.models import CandidateArticle, VideoCandidateResponse
from video.pipeline.editor import edit_script
from video.pipeline.picker import pick_story
from video.pipeline.runner import fail_scripting_run
from video.pipeline.scripter import (
    ClaimItem,
    ClaimLedger,
    ClaimLedgerEntry,
    ClipScript,
    ScriptOutput,
    ScriptRejected,
    count_words,
    generate_script,
    validate_story_eligibility,
    StoryIneligible,
)


SOURCE_URL = "https://example.com/wire"


def candidate() -> VideoCandidateResponse:
    return VideoCandidateResponse(
        story_id="story-1",
        headline="Sanctions changed as leaders exchanged statements",
        source_count=2,
        articles=[
            CandidateArticle(
                source_name="Reuters",
                title="Government eases diesel sanctions",
                url=SOURCE_URL,
                excerpt=(
                    "The government eased sanctions on diesel exports. "
                    "President Alex Smith said prices remained a concern."
                ),
            ),
            CandidateArticle(
                source_name="AP News",
                title="Opposition responds to sanctions change",
                url="https://example.com/ap",
                excerpt="Opposition leader Jordan Lee said the sanctions change should be reviewed.",
            ),
        ],
        source_urls=[SOURCE_URL, "https://example.com/ap"],
        combined_story_text="Sanctions changed and two leaders gave statements.",
    )


def test_picker_appends_candidates_omitted_by_model_ranking():
    first = candidate().model_copy(update={"story_id": "story-1"})
    second = candidate().model_copy(update={"story_id": "story-2", "headline": "Second candidate"})
    response = SimpleNamespace(
        text=json.dumps(
            {
                "chosen_story_id": "story-1",
                "one_line_reason": "First candidate ranked higher.",
                "ranking_order": ["story-1"],
                "rejected_stories": {},
            }
        )
    )
    client = SimpleNamespace(models=SimpleNamespace(generate_content=MagicMock(return_value=response)))

    chosen, decision, fallbacks = pick_story([first, second], client=client, model="test-model")

    assert chosen.story_id == "story-1"
    assert decision.ranking_order == ["story-1", "story-2"]
    assert [item.story_id for item in fallbacks] == ["story-2"]


def ledger() -> ClaimLedger:
    return ClaimLedger(
        entries=[
            ClaimLedgerEntry(
                claim_id="C1",
                claim_text="The government eased sanctions on diesel exports",
                source_outlet="Reuters",
                source_url=SOURCE_URL,
                source_snippet="The government eased sanctions on diesel exports",
                claim_type="reported_event",
            ),
            ClaimLedgerEntry(
                claim_id="C2",
                claim_text="President Alex Smith said prices remained a concern",
                source_outlet="Reuters",
                source_url=SOURCE_URL,
                source_snippet="President Alex Smith said prices remained a concern",
                claim_type="named_person_statement",
                named_person="President Alex Smith",
            ),
            ClaimLedgerEntry(
                claim_id="C3",
                claim_text="Opposition leader Jordan Lee said the sanctions change should be reviewed",
                source_outlet="AP News",
                source_url="https://example.com/ap",
                source_snippet="Opposition leader Jordan Lee said the sanctions change should be reviewed",
                claim_type="named_person_statement",
                named_person="Opposition leader Jordan Lee",
                is_response=True,
            ),
            ClaimLedgerEntry(
                claim_id="C4",
                claim_text="The policy was blaming the victim",
                source_outlet="Example Opinion Desk",
                source_url="https://example.com/opinion",
                source_snippet="blaming the victim",
                claim_type="outlet_characterization",
            ),
        ],
        has_counter_voice=True,
        balance_note="The AP excerpt contains a response from opposition leader Jordan Lee.",
    )


def clip(index: int, dialogue: str, claims: list[ClaimItem]) -> ClipScript:
    return ClipScript(
        clip_index=index,
        duration_seconds=8,
        speaker="maya" if index == 3 else "marcus",
        dialogue=dialogue,
        action="Neutral posture and steady eye contact",
        camera="Medium close-up shot",
        claims=claims,
    )


def script_with(dialogue: str, claim: ClaimItem) -> ScriptOutput:
    return ScriptOutput(
        headline="Neutral headline",
        caption="Neutral caption",
        hashtags=["#News", "#Policy"],
        ai_disclosure="Presenters and visuals are AI-generated. Report based on Reuters, AP News.",
        clips=[
            clip(1, dialogue, [claim]),
            clip(2, "Reuters reported that diesel export sanctions were eased by the government.", [ClaimItem(claim_text="The government eased sanctions on diesel exports", source_url=SOURCE_URL, ledger_id="C1")]),
            clip(3, "Opposition leader Jordan Lee said the sanctions change should be reviewed.", [ClaimItem(claim_text="Opposition leader Jordan Lee said the sanctions change should be reviewed", source_url="https://example.com/ap", ledger_id="C3")]),
            clip(4, "President Alex Smith said prices remained a concern. Reporting for WeAware News, I'm Marcus Vance.", [ClaimItem(claim_text="President Alex Smith said prices remained a concern", source_url=SOURCE_URL, ledger_id="C2")]),
        ],
        claim_ledger=ledger().entries,
    )


def test_count_words_treats_written_numbers_as_spoken_words():
    assert count_words("twenty-five people") == 3
    assert count_words("25 people") == 2


def test_blame_the_victim_characterization_is_rejected():
    script = script_with(
        "The outlet described the policy as blaming the victim.",
        ClaimItem(
            claim_text="The policy was blaming the victim",
            source_url="https://example.com/opinion",
            ledger_id="C4",
        ),
    )
    decision = edit_script(candidate(), script, client=MagicMock(), model="test-model")
    assert decision.passed is False
    assert any("blaming the victim" in item.lower() for item in decision.neutrality_violations)
    assert any("prohibited outlet characterization" in item for item in decision.unmapped_claims)


def test_purchase_when_source_only_says_eased_sanctions_is_rejected():
    script = script_with(
        "Reuters reported the government purchased Russian diesel.",
        ClaimItem(
            claim_text="The government purchased Russian diesel",
            source_url=SOURCE_URL,
            ledger_id="C1",
        ),
    )
    decision = edit_script(candidate(), script, client=MagicMock(), model="test-model")
    assert decision.passed is False
    assert any("changes C1 into a purchase" in item for item in decision.unmapped_claims)


def test_the_day_after_implied_link_is_rejected():
    script = script_with(
        "The day after sanctions were eased, another event occurred, Reuters reported.",
        ClaimItem(
            claim_text="The government eased sanctions on diesel exports",
            source_url=SOURCE_URL,
            ledger_id="C1",
        ),
    )
    decision = edit_script(candidate(), script, client=MagicMock(), model="test-model")
    assert decision.passed is False
    assert decision.causal_implication_violations


def test_over_budget_script_retries_three_times_then_raises():
    long_line = " ".join(["word"] * 23)
    draft = ScriptOutput(
        headline="Neutral headline",
        caption="Neutral caption",
        hashtags=["#News"],
        ai_disclosure="Presenters and visuals are AI-generated. Report based on Reuters, AP News.",
        clips=[
            clip(1, long_line, [ClaimItem(claim_text="The government eased sanctions on diesel exports", source_url=SOURCE_URL, ledger_id="C1")]),
            clip(2, long_line, [ClaimItem(claim_text="President Alex Smith said prices remained a concern", source_url=SOURCE_URL, ledger_id="C2")]),
            clip(3, long_line, [ClaimItem(claim_text="Opposition leader Jordan Lee said the sanctions change should be reviewed", source_url="https://example.com/ap", ledger_id="C3")]),
            clip(4, long_line, []),
        ],
    )
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = SimpleNamespace(text=draft.model_dump_json())

    with pytest.raises(ScriptRejected, match="after 3 attempts"):
        generate_script(candidate(), client=mock_client, model="test-model", ledger=ledger())

    assert mock_client.models.generate_content.call_count == 3
    retry_prompt = mock_client.models.generate_content.call_args_list[1].kwargs["contents"]
    assert "clip 1: 23 words (max 22)" in retry_prompt


def test_script_rejection_marks_failed_releases_claim_and_notifies(monkeypatch):
    import video.pipeline.runner as runner

    updates = []
    notifications = []
    monkeypatch.setattr(runner, "update_status_via_api", lambda *args, **kwargs: updates.append((args, kwargs)))
    monkeypatch.setattr(runner, "send_review_notifications", lambda **kwargs: notifications.append(kwargs))

    fail_scripting_run(
        "https://video-api.example",
        "redacted-key",
        "run-1",
        candidate(),
        "Script rejected after 3 attempts: clip 1 has 23 words",
        {"pro": "test-model"},
    )

    assert updates[0][0][3:5] == ("scripting", "failed")
    assert "Script rejected after 3 attempts" in updates[0][1]["error_message"]
    assert notifications[0]["event"] == "failed"
    assert notifications[0]["error_message"] == updates[0][1]["error_message"]


def test_generated_script_cannot_use_characterization_from_ledger():
    clean = script_with(
        "Reuters reported the government eased sanctions on diesel exports.",
        ClaimItem(
            claim_text="The government eased sanctions on diesel exports",
            source_url=SOURCE_URL,
            ledger_id="C1",
        ),
    )
    clean.claim_ledger = []
    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = SimpleNamespace(text=clean.model_dump_json())

    result = generate_script(candidate(), client=mock_client, model="test-model", ledger=ledger())
    assert "blaming the victim" not in " ".join(item.dialogue.lower() for item in result.clips)
    prompt = mock_client.models.generate_content.call_args.kwargs["contents"]
    assert '"claim_type":"outlet_characterization"' in prompt.replace(" ", "")


def test_outlet_characterization_does_not_count_as_counter_voice():
    only_outlet_response = ClaimLedger(
        entries=[
            ClaimLedgerEntry(
                claim_id="C1",
                claim_text="An event occurred",
                source_outlet="Reuters",
                source_url=SOURCE_URL,
                source_snippet="An event occurred",
                claim_type="reported_event",
            ),
            ClaimLedgerEntry(
                claim_id="C2",
                claim_text="The outlet called the event reckless",
                source_outlet="Example",
                source_url="https://example.com/opinion",
                source_snippet="reckless",
                claim_type="outlet_characterization",
                is_response=True,
            ),
        ],
        has_counter_voice=True,
        balance_note="Only an outlet characterization is available.",
    )
    with pytest.raises(StoryIneligible, match="No counter-voice"):
        validate_story_eligibility(only_outlet_response)
