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


def test_pro_selector_before_oct_19():
    """Before Oct 19, pro role selects GA gemini-2.5-pro."""
    today = date(2026, 10, 18)
    res = select_model("pro", today=today, allow_preview=False)
    assert res.model_id == "gemini-2.5-pro"
    assert res.location == "us-central1"
    assert res.reason in ("cheapest", "date switch")


def test_pro_selector_on_and_after_oct_19():
    """On and after Oct 19, no GA Pro exists; pro role falls back to best available GA Flash."""
    # On Oct 19 (switch date: 2026-10-20 minus 1 day)
    today_on = date(2026, 10, 19)
    res_on = select_model("pro", today=today_on, allow_preview=False)
    # 2.5-flash is also at switch date on Oct 19, so gemini-3.8-flash is chosen
    assert res_on.model_id == "gemini-3.8-flash"
    assert res_on.location == "global"
    assert res_on.reason == "pro_unavailable_flash_fallback"

    # After Oct 19 (e.g. Oct 25)
    today_after = date(2026, 10, 25)
    res_after = select_model("pro", today=today_after, allow_preview=False)
    assert res_after.model_id == "gemini-3.8-flash"
    assert res_after.reason == "pro_unavailable_flash_fallback"


def test_pro_selector_flash_also_unavailable():
    """When pro is retired and Flash candidates are also unavailable, fails early with a clear error."""
    today = date(2026, 10, 19)
    # Probe fails all models
    with pytest.raises(RuntimeError, match=r"role 'pro'.*Flash fallback is also unavailable"):
        select_model("pro", today=today, probe_func=lambda c: False, allow_preview=False)

    # All flash models excluded
    with pytest.raises(RuntimeError, match=r"role 'pro'.*Flash fallback is also unavailable"):
        select_model(
            "pro",
            today=today,
            excluded_models=["gemini-2.5-flash", "gemini-3.8-flash", "gemini-3.5-flash"],
            allow_preview=False,
        )


def test_price_effective_until_gemini_38_flash():
    """Verify that gemini-3.8-flash uses promotional pricing through Dec 31, 2026 and transitions on Jan 1, 2027."""
    c = next(cand for cand in DEFAULT_CANDIDATES["flash"] if cand.model_id == "gemini-3.8-flash")
    assert c.price_effective_until == date(2027, 1, 1)

    # 1. On Dec 31, 2026 (last day of promo): $0.75 in / $3.75 out
    today_promo = date(2026, 12, 31)
    cost_promo = calculate_estimated_cost(c, "flash", today=today_promo)
    # (10k / 1M) * 0.75 + (3k / 1M) * 3.75 = 0.0075 + 0.01125 = 0.01875
    assert round(cost_promo, 5) == 0.01875

    # 2. On Jan 1, 2027 (promotional pricing expires): $1.50 in / $6.00 out
    today_post_promo = date(2027, 1, 1)
    cost_post = calculate_estimated_cost(c, "flash", today=today_post_promo)
    # (10k / 1M) * 1.50 + (3k / 1M) * 6.00 = 0.015 + 0.018 = 0.033
    assert round(cost_post, 5) == 0.033

    # 3. In select_model: on Dec 31, 2026, estimated cost matches promo price
    res_promo = select_model("flash", today=today_promo, allow_preview=False)
    assert res_promo.model_id == "gemini-3.8-flash"
    assert round(res_promo.estimated_cost_usd, 5) == 0.01875

    # On Jan 1, 2027, estimated cost matches post-promo price
    res_post = select_model("flash", today=today_post_promo, allow_preview=False)
    assert res_post.model_id == "gemini-3.8-flash"
    assert round(res_post.estimated_cost_usd, 5) == 0.033


