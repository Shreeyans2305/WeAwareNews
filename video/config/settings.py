"""
Configuration settings and tunables for WeAware Late Night video pipeline.
"""

import os
from typing import List, Dict
from pydantic import BaseModel, Field


class Settings(BaseModel):
    # GCP Environment
    project_id: str = os.getenv("GOOGLE_CLOUD_PROJECT", "project-9ba21d45-1dfd-4108-b69")
    location: str = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
    gcs_bucket: str = os.getenv("VIDEO_BUCKET_NAME", f"weaware-video-assets-{os.getenv('GOOGLE_CLOUD_PROJECT', 'project-9ba21d45')}")

    # Video Pipeline Durations & Clip Plan
    # Default [8, 8, 8, 8] = 32s (Veo 3.1 discrete durations: 4, 6, 8s)
    clip_plan: List[int] = [8, 8, 8, 8]
    words_per_second: float = 2.5  # ~20 words for 8s clip, ~15 for 6s

    # Model Selection
    veo_model_tier: str = os.getenv("VEO_MODEL_TIER", "fast")  # 'fast' or 'standard'
    veo_model_fast: str = "veo-3.1-fast-generate-001"
    veo_model_standard: str = "veo-3.1-generate-001"
    gemini_flash_model: str = "gemini-2.5-flash"
    gemini_pro_model: str = "gemini-2.5-pro"
    image_bootstrap_model: str = "gemini-2.5-flash-image"

    # Pricing rates (USD) for cost tracking
    rate_veo_fast_per_sec: float = 0.15
    rate_veo_standard_per_sec: float = 0.40
    rate_gemini_input_per_m: float = 0.10
    rate_gemini_output_per_m: float = 0.40

    # Guardrails & Cost Limits
    max_cost_usd_per_run: float = float(os.getenv("MAX_COST_USD_PER_RUN", "25.00"))
    max_runs_per_day: int = int(os.getenv("MAX_RUNS_PER_DAY", "4"))
    max_veo_seconds_per_day: int = int(os.getenv("MAX_VEO_SECONDS_PER_DAY", "250"))
    video_dedupe_days: int = int(os.getenv("VIDEO_DEDUPE_DAYS", "14"))

    # Pipeline Operation
    max_editor_fallbacks: int = 2
    max_clip_retries: int = 2
    claim_timeout_minutes: int = 45
    publish_timeout_minutes: int = 15

    # API Connection
    video_api_url: str = os.getenv("VIDEO_API_URL", "http://localhost:8080")
    api_key: str = os.getenv("API_KEY", "")

    # Review Notifications
    pubsub_topic_name: str = os.getenv("REVIEW_PUBSUB_TOPIC", "weaware-video-reviews")
    webhook_secret_name: str = "video-notification-webhook"

    # Brand voice & metadata
    brand_name: str = "WeAware Late Night"
    brand_tagline: str = "Corroborated news, satirical conclusions."
    satire_disclosure: str = "AI-generated political satire grounded in verified multi-source news reporting."

    @property
    def active_veo_model(self) -> str:
        if self.veo_model_tier == "standard":
            return self.veo_model_standard
        return self.veo_model_fast

    @property
    def active_veo_rate(self) -> float:
        if self.veo_model_tier == "standard":
            return self.rate_veo_standard_per_sec
        return self.rate_veo_fast_per_sec


settings = Settings()
