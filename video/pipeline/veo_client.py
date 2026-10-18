"""
Veo Client: Manages video clip generation using Vertex AI Veo 3.1,
long-running operation polling with exponential backoff, safety rewording retries,
cost-budget caps, and heartbeats.
"""

import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from google import genai
from google.genai import types

from video.config.settings import settings
from video.pipeline.scripter import ClipScript

logger = logging.getLogger("weaware-video.veo_client")


class BudgetExceededError(Exception):
    pass


class ClaimCancelledError(Exception):
    pass


class VeoGenerationError(Exception):
    pass


class VeoClient:
    def __init__(
        self,
        client: Optional[genai.Client] = None,
        run_id: Optional[str] = None,
        heartbeat_callback: Optional[Callable[[], bool]] = None,
    ):
        self.client = client or genai.Client(
            vertexai=True,
            project=settings.project_id,
            location=settings.location,
        )
        self.run_id = run_id
        self.heartbeat_callback = heartbeat_callback
        self.total_veo_seconds_spent = 0
        self.total_cost_usd = 0.0

    @property
    def model_name(self) -> str:
        return settings.active_veo_model

    def check_budget_and_claim(self, upcoming_seconds: int = 8) -> None:
        """
        Validates that spending will not exceed MAX_COST_USD_PER_RUN,
        and executes the heartbeat callback to verify the claim is still active.
        """
        projected_cost = self.total_cost_usd + (upcoming_seconds * settings.active_veo_rate)
        if projected_cost > settings.max_cost_usd_per_run:
            raise BudgetExceededError(
                f"Projected cost ${projected_cost:.2f} exceeds max cost limit of ${settings.max_cost_usd_per_run:.2f}"
            )

        if self.heartbeat_callback:
            is_active = self.heartbeat_callback()
            if not is_active:
                raise ClaimCancelledError(f"Claim for run {self.run_id} is no longer active. Aborting spend.")

    def generate_single_clip(
        self,
        prompt: str,
        anchor_plate_bytes: bytes,
        duration_seconds: int = 8,
        output_path: Optional[Path] = None,
        mock_mode: bool = False,
    ) -> Path:
        """
        Generates one clip with first-frame image conditioning and native audio.
        Supports up to 2 safety-rewording retries.
        """
        self.check_budget_and_claim(upcoming_seconds=duration_seconds)

        if mock_mode:
            logger.info(f"[MOCK MODE] Simulating Veo generation for prompt: {prompt[:60]}...")
            time.sleep(1)
            self.total_veo_seconds_spent += duration_seconds
            self.total_cost_usd += duration_seconds * settings.active_veo_rate
            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(b"MOCK_MP4_CONTENT")
                return output_path
            return Path("mock_clip.mp4")

        first_frame = types.Image(image_bytes=anchor_plate_bytes, mime_type="image/png") if anchor_plate_bytes else None
        current_prompt = prompt
        last_error = None

        for attempt in range(settings.max_clip_retries + 1):
            if attempt > 0:
                self.check_budget_and_claim(upcoming_seconds=duration_seconds)
                logger.info(f"Retrying clip with softened safety wording (attempt {attempt + 1})...")

            try:
                config = types.GenerateVideosConfig(
                    aspect_ratio="9:16",
                    duration_seconds=duration_seconds,
                    person_generation="allow_adult",
                    generate_audio=True,
                    resolution=settings.veo_resolution,
                    negative_prompt=(
                        "laughter, applause, audience, crowd, music, soundtrack, sound effects, comedy, "
                        "late-night talk show, smirking, exaggerated gestures, reaction shots"
                    ),
                )

                logger.info(f"Submitting to {settings.active_veo_model}: {current_prompt[:80]}...")
                operation = self.client.models.generate_videos(
                    model=settings.active_veo_model,
                    prompt=current_prompt,
                    image=first_frame,
                    config=config,
                )

                # Track usage
                self.total_veo_seconds_spent += duration_seconds
                self.total_cost_usd += duration_seconds * settings.active_veo_rate

                # Poll long-running operation
                start_time = time.time()
                poll_delay = 10
                max_timeout = 300  # 5 minutes per clip

                while not operation.done:
                    if time.time() - start_time > max_timeout:
                        raise TimeoutError(f"Veo operation timed out after {max_timeout}s")

                    time.sleep(poll_delay)
                    operation = self.client.operations.get(operation)

                    # Trigger heartbeat every poll
                    if self.heartbeat_callback:
                        self.heartbeat_callback()

                    poll_delay = min(poll_delay * 1.2, 20)

                if operation.error:
                    error_msg = str(operation.error)
                    logger.warning(f"Veo operation returned error on attempt {attempt + 1}: {error_msg}")
                    last_error = error_msg
                    # Reword prompt for next attempt (soften comedic sarcasm/controversial words)
                    current_prompt = current_prompt.replace("shorting", "evaluating").replace("unhinged", "unexpected")
                    continue

                generated_video = operation.response.generated_videos[0]
                video_data = generated_video.video.video_bytes

                if not video_data and hasattr(generated_video.video, "uri"):
                    # Download from URI if needed
                    logger.info(f"Video returned URI: {generated_video.video.uri}")

                if output_path:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(video_data)
                    logger.info(f"✓ Saved clip to {output_path} ({len(video_data)} bytes)")
                    return output_path

                temp_path = Path(f"/tmp/clip_{int(time.time())}.mp4")
                temp_path.write_bytes(video_data)
                return temp_path

            except Exception as e:
                logger.error(f"Error during Veo generation (attempt {attempt + 1}): {e}")
                last_error = str(e)
                # Reword and retry
                time.sleep(5)

        raise VeoGenerationError(f"Failed to generate clip after {settings.max_clip_retries + 1} attempts: {last_error}")
