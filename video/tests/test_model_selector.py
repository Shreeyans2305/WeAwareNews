"""
Unit tests for automatic date-aware model selector (video.config.model_selector).
Tests lifecycle switch boundaries, pricing evaluation, probe filtering, and runtime fallback.
All tests inject 'today' to be fully clock-independent.
"""

from datetime import date, timedelta
import pytest

from video.config.model_selector import (
    ModelCandidate,
    select_model,
    calculate_estimated_cost,
    DEFAULT_CANDIDATES,
)


@pytest.fixture
def mock_flash_candidates():
    return [
        ModelCandidate(
            model_id="mock-2.5-flash",
            role="flash",
            location="us-central1",
            retirement_date=date(2026, 10, 20),
            price_input_per_1m=0.30,
            price_output_per_1m=2.50,
            is_preview=False,
            order_rank=1,
        ),
        ModelCandidate(
            model_id="mock-3.5-flash",
            role="flash",
            location="global",
            retirement_date=date(2027, 6, 30),
            price_input_per_1m=0.50,
            price_output_per_1m=3.00,
            is_preview=False,
            order_rank=2,
        ),
        ModelCandidate(
            model_id="mock-3.8-flash",
            role="flash",
            location="global",
            retirement_date=date(2027, 12, 31),
            price_input_per_1m=0.75,
            price_output_per_1m=3.75,
            is_preview=False,
            order_rank=3,
        ),
        ModelCandidate(
            model_id="mock-preview-flash",
            role="flash",
            location="global",
            retirement_date=date(2028, 1, 1),
            price_input_per_1m=0.10,
            price_output_per_1m=0.50,
            is_preview=True,
            order_rank=4,
        ),
    ]


def test_selector_before_switch_date(mock_flash_candidates):
    """Before retirement switch date, selects the cheapest active GA candidate."""
    today = date(2026, 10, 1)
    result = select_model("flash", candidates=mock_flash_candidates, today=today, allow_preview=False)
    assert result.model_id == "mock-2.5-flash"
    assert result.location == "us-central1"
    assert result.reason == "cheapest"
    # Switch date is 2026-10-19 (10-20 minus 1 day). 10-19 minus 10-01 = 18 days
    assert result.days_until_switch == 18


def test_selector_on_switch_date_minus_1(mock_flash_candidates):
    """On switch date minus 1 (2026-10-18), 2.5-flash is still eligible on its final day."""
    today = date(2026, 10, 18)
    result = select_model("flash", candidates=mock_flash_candidates, today=today, allow_preview=False)
    assert result.model_id == "mock-2.5-flash"
    assert result.days_until_switch == 1


def test_selector_on_switch_date(mock_flash_candidates):
    """On switch date (retirement_date minus 1 day = 2026-10-19), 2.5 is dropped and automatically switches."""
    today = date(2026, 10, 19)
    result = select_model("flash", candidates=mock_flash_candidates, today=today, allow_preview=False)
    assert result.model_id == "mock-3.5-flash"
    assert result.location == "global"
    assert result.reason == "date switch"


def test_selector_after_retirement(mock_flash_candidates):
    """Well after retirement, 2.5 is dropped and 3.5 remains the active GA model."""
    today = date(2026, 10, 25)
    result = select_model("flash", candidates=mock_flash_candidates, today=today, allow_preview=False)
    assert result.model_id == "mock-3.5-flash"
    assert result.reason == "date switch"


def test_selector_unknown_pricing(mock_flash_candidates):
    """A candidate with unknown pricing is treated as not cheaper and only chosen if no priced candidates exist."""
    unpriced_candidates = [
        ModelCandidate(
            model_id="mock-unpriced-old",
            role="flash",
            location="us-central1",
            retirement_date=date(2028, 1, 1),
            price_input_per_1m=None,
            price_output_per_1m=None,
            is_preview=False,
            order_rank=1,
        ),
        ModelCandidate(
            model_id="mock-unpriced-new",
            role="flash",
            location="us-central1",
            retirement_date=date(2028, 1, 1),
            price_input_per_1m=None,
            price_output_per_1m=None,
            is_preview=False,
            order_rank=2,
        ),
    ]
    today = date(2026, 10, 1)
    result = select_model("flash", candidates=unpriced_candidates, today=today, allow_preview=False)
    # Prefer newest GA (highest order_rank) when unpriced
    assert result.model_id == "mock-unpriced-new"
    assert result.estimated_cost_usd == float("inf")


def test_selector_all_candidates_unavailable(mock_flash_candidates):
    """When all candidates fail probe or are retired, raises descriptive RuntimeError."""
    today = date(2026, 10, 1)
    probe_fail = lambda c: False
    with pytest.raises(RuntimeError, match="No available Gemini models for role 'flash'"):
        select_model("flash", candidates=mock_flash_candidates, today=today, probe_func=probe_fail)


def test_selector_runtime_fallback(mock_flash_candidates):
    """When runtime fallback occurs, excluded model is bypassed and reason is 'runtime fallback'."""
    today = date(2026, 10, 1)
    result = select_model(
        "flash",
        candidates=mock_flash_candidates,
        today=today,
        excluded_models=["mock-2.5-flash"],
        is_runtime_fallback=True,
    )
    assert result.model_id == "mock-3.5-flash"
    assert result.reason == "runtime fallback"


def test_selector_preview_filter(mock_flash_candidates):
    """Preview models are excluded by default, but included if allow_preview=True."""
    today = date(2026, 10, 1)
    # Exclude preview
    res_no_preview = select_model("flash", candidates=mock_flash_candidates, today=today, allow_preview=False)
    assert res_no_preview.model_id == "mock-2.5-flash"

    # Allow preview: mock-preview-flash has lower price ($0.10 / $0.50)
    res_with_preview = select_model("flash", candidates=mock_flash_candidates, today=today, allow_preview=True)
    assert res_with_preview.model_id == "mock-preview-flash"
