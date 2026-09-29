"""
Review Notifier: Dispatches review requests with single-use HMAC URLs
via Pub/Sub topic and Webhook (Discord / Slack / Google Chat).
"""

import json
import logging
import os
import urllib.request
from typing import Dict, Any, Optional

from video.config.settings import settings
from video.api.security import generate_review_token

logger = logging.getLogger("weaware-video.notifier")


def send_review_notifications(
    run_id: str,
    headline: str,
    video_url: str,
    caption: str,
    estimated_cost: float,
    api_base_url: Optional[str] = None,
) -> Dict[str, bool]:
    api_url = api_base_url or settings.video_api_url

    # Generate single-use review tokens
    approve_token = generate_review_token(run_id, "approve", expires_in_seconds=86400)
    reject_token = generate_review_token(run_id, "reject", expires_in_seconds=86400)

    approve_link = f"{api_url}/videos/review?token={approve_token}&action=approve"
    reject_link = f"{api_url}/videos/review?token={reject_token}&action=reject"

    payload = {
        "event": "video_ready_for_review",
        "run_id": run_id,
        "headline": headline,
        "caption": caption,
        "video_url": video_url,
        "estimated_cost_usd": estimated_cost,
        "review_links": {
            "approve": approve_link,
            "reject": reject_link,
        },
    }

    results = {"pubsub": False, "webhook": False}

    # 1. Pub/Sub notification
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

    # 2. Webhook notification (Discord / Slack / Chat)
    webhook_url = os.getenv("VIDEO_WEBHOOK_URL")
    if not webhook_url:
        try:
            from google.cloud import secretmanager
            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{settings.project_id}/secrets/{settings.webhook_secret_name}/versions/latest"
            response = client.access_secret_version(request={"name": name})
            webhook_url = response.payload.data.decode("UTF-8").strip()
        except Exception as e:
            logger.info(f"No webhook secret configured: {e}")

    if webhook_url:
        try:
            # Discord / Slack compatible message payload
            msg = {
                "content": f"🎬 **WeAware Late Night Review Ready!**\n"
                           f"**Headline:** {headline}\n"
                           f"**Estimated Cost:** ${estimated_cost:.2f}\n"
                           f"[Approve Video]({approve_link}) | [Reject Video]({reject_link})\n"
                           f"Preview: {video_url}"
            }
            req = urllib.request.Request(
                webhook_url,
                data=json.dumps(msg).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "WeAware-Video-Pipeline"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info(f"Webhook dispatched successfully: HTTP {resp.status}")
                results["webhook"] = True
        except Exception as e:
            logger.warning(f"Webhook dispatch failed: {e}")

    return results
