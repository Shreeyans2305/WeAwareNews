"""
Review Notifier for Make.com Custom Webhook and Cloud Pub/Sub.
Dispatches flat schema_version: 1 payloads with optional HMAC-SHA256 signatures.
Handles retries with exponential backoff on 5xx/timeouts without failing the video run.
"""

import sys
import json
import time
import hmac
import hashlib
import logging
import os
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List

from video.config.settings import settings
from video.api.security import generate_review_token

logger = logging.getLogger("weaware-video.notifier")


def get_secret_value(secret_name: str) -> Optional[str]:
    """Retrieves secret payload from environment or Google Cloud Secret Manager."""
    # First check env
    env_name = secret_name.upper().replace("-", "_")
    val = os.getenv(env_name)
    if val:
        return val.strip()

    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{settings.project_id}/secrets/{secret_name}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8").strip()
    except Exception as e:
        logger.debug(f"Could not load secret {secret_name} from Secret Manager: {e}")
        return None


def calculate_hmac_signature(body_bytes: bytes, secret_key: str) -> str:
    """Computes HMAC-SHA256 signature of the payload body."""
    return hmac.new(
        key=secret_key.encode("utf-8"),
        msg=body_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()


def build_webhook_payload(
    event: str,
    run_id: str,
    story_id: str,
    headline: str,
    caption: str,
    hashtags: List[str],
    sources: List[str],
    review_url: str,
    video_preview_url: str,
    thumbnail_url: str,
    estimated_cost_usd: float,
    veo_model: str,
    veo_resolution: str,
    gemini_models_used: Dict[str, str],
    transcript_min_match_ratio: float = 1.0,
    transcript_mismatch_count: int = 0,
    error_message: Optional[str] = None,
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Constructs stable, flat schema_version: 1 payload for Make.com."""
    payload: Dict[str, Any] = {
        "schema_version": 1,
        "event": event,
        "run_id": run_id,
        "story_id": story_id,
        "headline": headline,
        "caption": caption,
        "hashtags": hashtags,
        "sources": sources,
        "review_url": review_url,
        "video_preview_url": video_preview_url,
        "thumbnail_url": thumbnail_url,
        "estimated_cost_usd": round(estimated_cost_usd, 4),
        "veo_model": veo_model,
        "veo_resolution": veo_resolution,
        "gemini_models_used": gemini_models_used,
        "transcript_min_match_ratio": round(transcript_min_match_ratio, 3),
        "transcript_mismatch_count": transcript_mismatch_count,
        "error_message": error_message,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
    }
    return payload


def send_webhook_with_retry(
    webhook_url: str,
    payload: Dict[str, Any],
    hmac_secret: Optional[str] = None,
    max_retries: int = 3,
    timeout_sec: float = 10.0,
) -> bool:
    """Dispatches webhook with exponential backoff on 5xx/timeout. Never throws."""
    body_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "WeAware-Video-Pipeline/1.0",
    }
    if hmac_secret:
        signature = calculate_hmac_signature(body_bytes, hmac_secret)
        headers["x-weaware-signature"] = signature

    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(
                webhook_url,
                data=body_bytes,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                if 200 <= resp.status < 300:
                    logger.info(f"Make.com webhook dispatched successfully: HTTP {resp.status} (attempt {attempt + 1})")
                    return True
                else:
                    logger.warning(f"Make.com webhook returned unexpected HTTP {resp.status} on attempt {attempt + 1}")
        except urllib.error.HTTPError as e:
            if 500 <= e.code < 600:
                logger.warning(f"Webhook server error HTTP {e.code} on attempt {attempt + 1}")
            else:
                logger.error(f"Webhook client error HTTP {e.code} (will not retry)")
                return False
        except Exception as e:
            logger.warning(f"Webhook connection/timeout error on attempt {attempt + 1}: {e}")

        if attempt < max_retries - 1:
            backoff = 2 ** attempt
            time.sleep(backoff)

    logger.error(f"Make.com webhook failed after {max_retries} attempts. Notification marked failed.")
    return False


def send_review_notifications(
    run_id: str,
    story_id: str,
    headline: str,
    video_url: str,
    thumbnail_url: str,
    caption: str,
    hashtags: List[str],
    sources: List[str],
    estimated_cost: float,
    gemini_models_used: Dict[str, str],
    veo_model: Optional[str] = None,
    veo_resolution: Optional[str] = None,
    transcript_min_match_ratio: float = 1.0,
    transcript_mismatch_count: int = 0,
    api_base_url: Optional[str] = None,
    event: str = "ready_for_review",
    error_message: Optional[str] = None,
) -> Dict[str, bool]:
    """
    Sends notification to Cloud Pub/Sub and Make.com Custom Webhook.
    Never raises an exception or fails the video run.
    """
    api_url = api_base_url or settings.video_api_url
    review_token = generate_review_token(run_id, "review", expires_in_seconds=86400)
    review_url = f"{api_url}/videos/review?token={review_token}"

    payload = build_webhook_payload(
        event=event,
        run_id=run_id,
        story_id=story_id,
        headline=headline,
        caption=caption,
        hashtags=hashtags,
        sources=sources,
        review_url=review_url,
        video_preview_url=video_url,
        thumbnail_url=thumbnail_url,
        estimated_cost_usd=estimated_cost,
        veo_model=veo_model or settings.active_veo_model,
        veo_resolution=veo_resolution or settings.veo_resolution,
        gemini_models_used=gemini_models_used,
        transcript_min_match_ratio=transcript_min_match_ratio,
        transcript_mismatch_count=transcript_mismatch_count,
        error_message=error_message,
    )

    results = {"pubsub": False, "webhook": False}

    # 1. Cloud Pub/Sub Notification
    try:
        from google.cloud import pubsub_v1
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(settings.project_id, settings.pubsub_topic_name)
        data = json.dumps(payload).encode("utf-8")
        future = publisher.publish(topic_path, data)
        msg_id = future.result(timeout=10)
        logger.info(f"Published review notification to Pub/Sub: {msg_id}")
        results["pubsub"] = True
    except Exception as e:
        logger.warning(f"Could not publish to Pub/Sub: {e}")

    # 2. Make.com Custom Webhook Notification
    webhook_url = get_secret_value(settings.webhook_secret_name)
    hmac_secret = get_secret_value(settings.hmac_secret_name)

    if webhook_url and webhook_url.startswith("http"):
        results["webhook"] = send_webhook_with_retry(
            webhook_url=webhook_url,
            payload=payload,
            hmac_secret=hmac_secret,
            max_retries=3,
            timeout_sec=10.0,
        )
    else:
        logger.info("Make.com webhook secret is not configured or empty; skipping webhook delivery.")

    return results


def send_test_webhook():
    """CLI helper to post a sample event: 'test' payload to Make.com for structure determination."""
    sample_payload = build_webhook_payload(
        event="test",
        run_id="00000000-0000-0000-0000-000000000001",
        story_id="test-story-make-sample",
        headline="Astronomers Discover Asteroid Containing Trillions in Rare Minerals",
        caption="When the asteroid mining rush begins, will space lawyers take a 30% cut? ☄️🚀 #SpaceMining #LateNight #Satire",
        hashtags=["#SpaceMining", "#LateNight", "#Satire", "#WeAware"],
        sources=["Reuters", "Associated Press", "BBC News"],
        review_url="https://weaware-video-api-xyz.run.app/videos/review?token=sample-hmac-token-12345",
        video_preview_url="https://storage.googleapis.com/weaware-video-assets-xyz/episodes/test/final_episode.mp4",
        thumbnail_url="https://storage.googleapis.com/weaware-video-assets-xyz/episodes/test/thumbnail.jpg",
        estimated_cost_usd=3.2450,
        veo_model="veo-3.1-fast-generate-001",
        veo_resolution="720p",
        gemini_models_used={
            "scripter": "gemini-2.5-pro",
            "picker": "gemini-2.5-flash",
            "editor": "gemini-2.5-flash",
            "transcriber": "gemini-2.5-flash",
        },
        transcript_min_match_ratio=0.985,
        transcript_mismatch_count=0,
    )

    webhook_url = get_secret_value(settings.webhook_secret_name)
    hmac_secret = get_secret_value(settings.hmac_secret_name)

    if not webhook_url or not webhook_url.startswith("http"):
        print("ERROR: video-webhook-url secret does not contain a valid URL.")
        print("Please configure the secret first:")
        print("   echo -n '<make webhook url>' | gcloud secrets versions add video-webhook-url --data-file=-")
        sys.exit(1)

    print("Sending test event to configured Make.com webhook...")
    success = send_webhook_with_retry(
        webhook_url=webhook_url,
        payload=sample_payload,
        hmac_secret=hmac_secret,
        max_retries=3,
        timeout_sec=10.0,
    )
    if success:
        print("SUCCESS: Test payload delivered to Make.com! You can now inspect or redetermine data structure in Make.")
    else:
        print("FAILED: Could not deliver test payload to Make.com webhook. Check the URL and Make scenario status.")
        sys.exit(1)


if __name__ == "__main__":
    if "--send-test" in sys.argv:
        send_test_webhook()
    else:
        print("Usage: python -m video.pipeline.notifier --send-test")
