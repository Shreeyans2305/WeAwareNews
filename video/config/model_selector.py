"""
Automatic, date-aware Gemini model selection and lifecycle management.
Evaluates candidate models by retirement date, GA status, availability probe,
and estimated per-run token cost.
"""

import os
import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Callable

logger = logging.getLogger("weaware-video.model_selector")


@dataclass
class ModelCandidate:
    model_id: str
    role: str  # "flash" or "pro"
    location: str  # "us-central1" or "global"
    retirement_date: date  # UTC date from official lifecycle page
    price_input_per_1m: Optional[float]  # USD per 1M input tokens
    price_output_per_1m: Optional[float]  # USD per 1M output tokens
    is_preview: bool
    order_rank: int  # Higher number = newer model generation
    source_url: str = "https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions"


# Typical token counts per run per role for cost estimation
TYPICAL_TOKENS = {
    "flash": {"input": 10_000, "output": 3_000},  # picker, editor, transcript checks
    "pro": {"input": 5_000, "output": 2_000},     # scriptwriter
}

# Candidate lists per role
# Sources:
# Lifecycle: https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions
# Pricing: https://cloud.google.com/vertex-ai/generative-ai/pricing (read 2026-09-29)
DEFAULT_CANDIDATES: Dict[str, List[ModelCandidate]] = {
    "flash": [
        # 1. Gemini 2.5 Flash (GA, retiring Oct 20, 2026)
        # Pricing: $0.30 in / $2.50 out per 1M tokens (Table 4)
        ModelCandidate(
            model_id="gemini-2.5-flash",
            role="flash",
            location="us-central1",
            retirement_date=date(2026, 10, 20),
            price_input_per_1m=0.30,
            price_output_per_1m=2.50,
            is_preview=False,
            order_rank=1,
            source_url="https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions",
        ),
        # 2. Gemini 3.8 Flash (GA, promotional pricing through Dec 31, 2026)
        # Pricing: $0.75 in / $3.75 out per 1M tokens (Table 0)
        # Retirement: "No retirement date announced" (set conservatively to 2028-01-01)
        ModelCandidate(
            model_id="gemini-3.8-flash",
            role="flash",
            location="global",
            retirement_date=date(2028, 1, 1),
            price_input_per_1m=0.75,
            price_output_per_1m=3.75,
            is_preview=False,
            order_rank=3,
            source_url="https://cloud.google.com/vertex-ai/generative-ai/pricing",
        ),
        # 3. Gemini 3.5 Flash (GA, global endpoint)
        # Pricing: $1.50 in / $9.00 out per 1M tokens (Table 0)
        # Retirement: "May 19, 2027 or later"
        ModelCandidate(
            model_id="gemini-3.5-flash",
            role="flash",
            location="global",
            retirement_date=date(2027, 5, 19),
            price_input_per_1m=1.50,
            price_output_per_1m=9.00,
            is_preview=False,
            order_rank=2,
            source_url="https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions",
        ),
    ],
    "pro": [
        # 1. Gemini 2.5 Pro (GA, retiring Oct 20, 2026)
        # Pricing: $1.25 in / $10.00 out per 1M tokens (Table 4)
        ModelCandidate(
            model_id="gemini-2.5-pro",
            role="pro",
            location="us-central1",
            retirement_date=date(2026, 10, 20),
            price_input_per_1m=1.25,
            price_output_per_1m=10.00,
            is_preview=False,
            order_rank=1,
            source_url="https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions",
        ),
        # 2. Gemini 3.1 Pro Preview (Preview, global endpoint)
        # Pricing: $2.00 in / $12.00 out per 1M tokens (Table 0)
        # Retirement: "May 28, 2027 or later"
        ModelCandidate(
            model_id="gemini-3.1-pro-preview",
            role="pro",
            location="global",
            retirement_date=date(2027, 5, 28),
            price_input_per_1m=2.00,
            price_output_per_1m=12.00,
            is_preview=True,
            order_rank=2,
            source_url="https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions",
        ),
    ],
}


@dataclass
class SelectionResult:
    model_id: str
    location: str
    reason: str  # "cheapest" | "date switch" | "runtime fallback"
    days_until_switch: int
    estimated_cost_usd: float
    candidate: ModelCandidate


def calculate_estimated_cost(candidate: ModelCandidate, role: str) -> float:
    """Calculates estimated per-run cost in USD based on typical token counts."""
    if candidate.price_input_per_1m is None or candidate.price_output_per_1m is None:
        return float("inf")  # Unknown pricing treated as infinite / not cheaper
    tokens = TYPICAL_TOKENS.get(role, {"input": 10_000, "output": 3_000})
    input_cost = (tokens["input"] / 1_000_000.0) * candidate.price_input_per_1m
    output_cost = (tokens["output"] / 1_000_000.0) * candidate.price_output_per_1m
    return input_cost + output_cost


def select_model(
    role: str,
    candidates: Optional[List[ModelCandidate]] = None,
    today: Optional[date] = None,
    allow_preview: Optional[bool] = None,
    probe_func: Optional[Callable[[ModelCandidate], bool]] = None,
    excluded_models: Optional[List[str]] = None,
    is_runtime_fallback: bool = False,
    fallback_candidates: Optional[List[ModelCandidate]] = None,
) -> SelectionResult:
    """
    Selects the optimal model candidate based on retirement dates, availability, and cost.
    Pins the result for the run.
    """
    if candidates is None:
        candidates = DEFAULT_CANDIDATES.get(role, [])
    
    if today is None:
        today = datetime.now(timezone.utc).date()
        
    if allow_preview is None:
        allow_preview = os.getenv("ALLOW_PREVIEW_MODELS", "false").lower() in ("true", "1", "yes")

    excluded = set(excluded_models or [])

    # Filter candidates
    surviving: List[tuple[ModelCandidate, float]] = []
    date_switch_occurred = False

    for c in candidates:
        if c.model_id in excluded:
            continue
        if c.is_preview and not allow_preview:
            continue
        
        # Rule 2: Drop candidates where today >= retirement_date - 1 day
        switch_date = c.retirement_date - timedelta(days=1)
        if today >= switch_date:
            date_switch_occurred = True
            logger.info(
                f"Candidate {c.model_id} dropped: retirement switch date reached "
                f"(today={today} >= switch_date={switch_date})"
            )
            continue
            
        # Rule 1: Drop candidates failing startup availability probe
        if probe_func is not None:
            if not probe_func(c):
                logger.warning(f"Candidate {c.model_id} ({c.location}) failed availability probe. Dropping.")
                continue

        cost = calculate_estimated_cost(c, role)
        surviving.append((c, cost))

    if not surviving:
        # Fallback for 'pro' role to best available GA Flash when no GA Pro candidates remain
        if role == "pro":
            logger.warning("No GA candidate remains for role 'pro'. Evaluating fallback to GA Flash models...")
            if fallback_candidates is None:
                flash_cands = [c for c in candidates if c.role == "flash"]
                if not flash_cands:
                    flash_cands = DEFAULT_CANDIDATES.get("flash", [])
            else:
                flash_cands = fallback_candidates

            surviving_flash: List[tuple[ModelCandidate, float]] = []
            for fc in flash_cands:
                if fc.model_id in excluded:
                    continue
                if fc.is_preview and not allow_preview:
                    continue
                f_switch_date = fc.retirement_date - timedelta(days=1)
                if today >= f_switch_date:
                    continue
                if probe_func is not None and not probe_func(fc):
                    logger.warning(f"Flash fallback candidate {fc.model_id} ({fc.location}) failed probe. Dropping.")
                    continue
                f_cost = calculate_estimated_cost(fc, "pro")
                surviving_flash.append((fc, f_cost))

            if not surviving_flash:
                raise RuntimeError(
                    f"No available Gemini models for role '{role}' and Flash fallback is also unavailable. "
                    "All candidates retired, excluded, or failed probes."
                )

            # Rule 3: Choose cheapest by estimated per-run cost
            surviving_flash.sort(key=lambda item: (item[1], -item[0].order_rank))
            chosen, chosen_cost = surviving_flash[0]
            days_until_switch = (chosen.retirement_date - timedelta(days=1) - today).days

            logger.warning(
                f"pro_unavailable_flash_fallback: Active for role 'pro'. Using best GA Flash model {chosen.model_id} ({chosen.location})."
            )

            return SelectionResult(
                model_id=chosen.model_id,
                location=chosen.location,
                reason="pro_unavailable_flash_fallback",
                days_until_switch=days_until_switch,
                estimated_cost_usd=chosen_cost,
                candidate=chosen,
            )

        raise RuntimeError(
            f"No available Gemini models for role '{role}'. All candidates retired, excluded, or failed probes."
        )

    # Rule 3: Choose cheapest by estimated per-run cost. If pricing unknown, prefer newest GA (highest order_rank).
    surviving.sort(key=lambda item: (item[1], -item[0].order_rank))
    chosen, chosen_cost = surviving[0]

    days_until_switch = (chosen.retirement_date - timedelta(days=1) - today).days

    if days_until_switch <= 14:
        logger.warning(
            f"MODEL LIFECYCLE ALERT: Selected model {chosen.model_id} is within {days_until_switch} days "
            f"of its switch date ({chosen.retirement_date - timedelta(days=1)})."
        )

    if is_runtime_fallback:
        reason = "runtime fallback"
        logger.error(f"RUNTIME_FALLBACK: Switched to candidate model {chosen.model_id} ({chosen.location}).")
    elif date_switch_occurred:
        reason = "date switch"
    else:
        reason = "cheapest"

    return SelectionResult(
        model_id=chosen.model_id,
        location=chosen.location,
        reason=reason,
        days_until_switch=days_until_switch,
        estimated_cost_usd=chosen_cost,
        candidate=chosen,
    )


def check_veo_lifecycle(today: Optional[date] = None) -> None:
    """Warns if Veo 3.1 models are within 14 days of retirement date (Nov 17, 2026 or later).
    Source: https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions
    Baseline stays locked at veo-3.1-fast-generate-001 (720p); changing requires user approval.
    """
    if today is None:
        today = datetime.now(timezone.utc).date()
    veo_retirement = date(2026, 11, 17)
    days_left = (veo_retirement - today).days
    if days_left <= 14:
        logger.warning(
            f"VEO LIFECYCLE ALERT: Veo 3.1 baseline models are within {days_left} days of retirement "
            f"date ({veo_retirement}). Baseline stays locked; human approval required to update."
        )

