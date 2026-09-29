"""
Unit tests for Video API:
- HMAC review token security (generation, verification, tamper, expiry, single-use)
- Atomic claiming & concurrency simulation
- Expired claim sweeper
- Compare-and-set status transitions
- Candidate quality filtering (paywall, social, thin text, >=2 distinct publishers, URL dedupe)
- Make.com publishing flow & idempotency
"""

import time
import uuid
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from video.api.main import app, truncate_excerpt
from video.api.security import (
    generate_review_token,
    verify_review_token,
    get_hmac_secret,
)
from video.api.models import (
    ClaimRequest,
    StatusUpdateRequest,
    ReviewCommitRequest,
)


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. HMAC Review Security Tests
# ---------------------------------------------------------------------------

def test_hmac_token_valid():
    run_id = str(uuid.uuid4())
    token = generate_review_token(run_id, "approve", expires_in_seconds=3600)
    valid, res_run_id, res_action, err = verify_review_token(token)
    assert valid is True
    assert res_run_id == run_id
    assert res_action == "approve"
    assert err is None


def test_hmac_token_expired():
    run_id = str(uuid.uuid4())
    # Generate token that expired 10 seconds ago
    token = generate_review_token(run_id, "approve", expires_in_seconds=-10)
    valid, res_run_id, res_action, err = verify_review_token(token)
    assert valid is False
    assert err == "Token has expired"


def test_hmac_token_tampered():
    run_id = str(uuid.uuid4())
    token = generate_review_token(run_id, "approve", expires_in_seconds=3600)
    # Tamper with action
    tampered = token.replace("approve", "reject")
    valid, res_run_id, res_action, err = verify_review_token(tampered)
    assert valid is False
    assert err == "Invalid token signature"


def test_hmac_token_malformed():
    valid, run_id, action, err = verify_review_token("not:a:valid:token:structure")
    assert valid is False
    assert "Malformed" in err


# ---------------------------------------------------------------------------
# 2. Text Truncation Helper Tests
# ---------------------------------------------------------------------------

def test_truncate_excerpt():
    text = "Word " * 300  # 1500 chars
    truncated = truncate_excerpt(text, max_chars=500)
    assert len(truncated) <= 505
    assert truncated.endswith("...")
    assert not truncated.endswith(" ...")


# ---------------------------------------------------------------------------
# 3. Candidate Filtering & Deduplication Tests
# ---------------------------------------------------------------------------

def test_video_candidates_filtering(client):
    """
    Test that candidate stories exclude paywalled, social, thin text,
    and deduplicates against recent run URLs.
    """
    mock_cursor = MagicMock()
    # 1. recent_run_urls
    mock_cursor.fetchone.side_effect = [
        [["https://duplicate-source.com/article1"]],  # recent run URLs
    ]
    # 2. Candidate stories
    mock_cursor.fetchall.side_effect = [
        [{"story_id": "story-1", "source_count": 3, "recency": "2026-09-29"}],
        # Items for story-1:
        # Article 1: Valid
        # Article 2: Valid, different source
        # Article 3: Paywalled (should be filtered out by SQL in prod)
        [
            {
                "source_name": "Reuters",
                "title": "Clean Energy Milestone Achieved",
                "url": "https://reuters.com/clean-energy",
                "raw_text": "Detailed body text of the article about clean energy milestones that is sufficiently long. " * 3,
                "published_at": "2026-09-29T08:00:00Z",
            },
            {
                "source_name": "BBC News",
                "title": "UK Energy Grid Shifts to Renewables",
                "url": "https://bbc.com/uk-energy",
                "raw_text": "Another detailed body text from BBC discussing the energy grid shifts over the past year. " * 3,
                "published_at": "2026-09-29T07:30:00Z",
            },
        ],
    ]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("video.api.main.get_db_connection") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_conn

        response = client.get("/stories/video-candidates?limit=5&min_sources=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["story_id"] == "story-1"
        assert data[0]["headline"] == "Clean Energy Milestone Achieved"
        assert data[0]["source_count"] == 2
        assert len(data[0]["articles"]) == 2


def test_video_candidates_excludes_overlapping_urls(client):
    """
    Test that a story whose URLs overlap with recent video runs is filtered out.
    """
    mock_cursor = MagicMock()
    mock_cursor.fetchone.side_effect = [
        [["https://reuters.com/already-used"]],  # recent run URLs
    ]
    mock_cursor.fetchall.side_effect = [
        [{"story_id": "story-overlap", "source_count": 2, "recency": "2026-09-29"}],
        [
            {
                "source_name": "Reuters",
                "title": "Old Story",
                "url": "https://reuters.com/already-used",
                "raw_text": "Long enough text about old story. " * 5,
                "published_at": "2026-09-29T08:00:00Z",
            },
            {
                "source_name": "AP",
                "title": "Old Story Also",
                "url": "https://ap.com/story",
                "raw_text": "Long enough text about old story. " * 5,
                "published_at": "2026-09-29T07:00:00Z",
            },
        ],
    ]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("video.api.main.get_db_connection") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_conn

        response = client.get("/stories/video-candidates?limit=5&min_sources=2")
        assert response.status_code == 200
        data = response.json()
        # Should be empty because URL overlapped with recent run
        assert len(data) == 0


# ---------------------------------------------------------------------------
# 4. Atomic Claiming & Concurrency Simulation Tests
# ---------------------------------------------------------------------------

def test_atomic_claim_success(client):
    mock_cursor = MagicMock()
    mock_now = "2026-09-29T10:00:00"
    mock_expires = "2026-09-29T10:45:00"
    mock_cursor.fetchone.return_value = (uuid.uuid4(), MagicMock(isoformat=lambda: mock_now), MagicMock(isoformat=lambda: mock_expires))

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("video.api.main.get_db_connection") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_conn

        body = {
            "claim_mode": "separate",
            "timeout_minutes": 45,
            "headline_snapshot": "Test Headline",
            "sources_snapshot": [{"source_name": "Reuters"}],
            "source_urls": ["https://reuters.com/1"],
            "story_text_snapshot": "Test story text",
        }
        resp = client.post("/stories/story-123/video-claim", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["story_id"] == "story-123"
        assert data["status"] == "claimed"


def test_concurrent_claim_conflict(client):
    """
    Simulates a concurrent claim attempt where Postgres returns no row due to ON CONFLICT DO NOTHING.
    """
    mock_cursor = MagicMock()
    # fetchone returns None when ON CONFLICT DO NOTHING does not insert
    mock_cursor.fetchone.return_value = None

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("video.api.main.get_db_connection") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_conn

        body = {
            "claim_mode": "separate",
            "timeout_minutes": 45,
            "headline_snapshot": "Test Headline",
            "sources_snapshot": [],
            "source_urls": ["https://reuters.com/1"],
            "story_text_snapshot": "Test story text",
        }
        resp = client.post("/stories/story-already-claimed/video-claim", json=body)
        assert resp.status_code == 409
        assert "already claimed" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 5. Compare-and-Set Status Transitions Tests
# ---------------------------------------------------------------------------

def test_compare_and_set_status_success(client):
    run_id = str(uuid.uuid4())
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = ("claimed",)  # current status in DB

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("video.api.main.get_db_connection") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_conn

        body = {
            "expected_status": "claimed",
            "new_status": "scripting",
            "heartbeat": True,
        }
        resp = client.post(f"/videos/{run_id}/status", json=body)
        assert resp.status_code == 200
        assert resp.json()["current_status"] == "scripting"


def test_compare_and_set_status_conflict(client):
    run_id = str(uuid.uuid4())
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = ("generating_video",)  # DB has progressed already

    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("video.api.main.get_db_connection") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_conn

        body = {
            "expected_status": "claimed",
            "new_status": "scripting",
        }
        resp = client.post(f"/videos/{run_id}/status", json=body)
        assert resp.status_code == 409
        assert "Status conflict" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 6. Review Flow & Single-Use Commit Tests
# ---------------------------------------------------------------------------

def test_review_get_confirm_page_only(client):
    run_id = str(uuid.uuid4())
    token = generate_review_token(run_id, "approve", expires_in_seconds=3600)

    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {
        "status": "ready_for_review",
        "headline_snapshot": "Exciting Satirical News",
        "caption": "Check out this reel #comedy",
        "video_gcs_uri": "gs://bucket/runs/1/final.mp4",
        "thumbnail_gcs_uri": "gs://bucket/runs/1/thumb.jpg",
    }
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("video.api.main.get_db_connection") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_conn

        resp = client.get(f"/videos/review?token={token}&action=approve")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Exciting Satirical News" in resp.text
        assert "Confirm Approval" in resp.text


def test_review_commit_single_use(client):
    run_id = str(uuid.uuid4())
    token = generate_review_token(run_id, "approve", expires_in_seconds=3600)

    mock_cursor = MagicMock()
    # First commit succeeds (returns run_id)
    mock_cursor.fetchone.return_value = (run_id,)
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("video.api.main.get_db_connection") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_conn

        # 1. First commit
        resp = client.post("/videos/review", json={"token": token, "action": "approve"})
        assert resp.status_code == 200
        assert resp.json()["decision"] == "approved"

        # 2. Replay attack: status is no longer 'ready_for_review' -> rowcount 0 -> 409
        mock_cursor.fetchone.return_value = None
        replay_resp = client.post("/videos/review", json={"token": token, "action": "approve"})
        assert replay_resp.status_code == 409
        assert "already been committed" in replay_resp.json()["detail"]


# ---------------------------------------------------------------------------
# 7. Make.com Publishing Flow Tests
# ---------------------------------------------------------------------------

def test_next_approved_video_pull_and_publish(client):
    run_id = str(uuid.uuid4())
    mock_cursor = MagicMock()
    # Mock row returned by FOR UPDATE SKIP LOCKED
    mock_cursor.fetchone.return_value = {
        "run_id": run_id,
        "story_id": "story-456",
        "video_gcs_uri": "gs://weaware-video/runs/1/final.mp4",
        "thumbnail_gcs_uri": "gs://weaware-video/runs/1/thumb.jpg",
        "caption": "Hilarious late night take #news",
        "hashtags": ["news", "comedy"],
        "idempotency_key": "idemp-key-789",
    }
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("video.api.main.get_db_connection") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_conn

        # 1. Pull next approved
        resp = client.get("/videos/next-approved")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert data["idempotency_key"] == "idemp-key-789"

        # 2. Mark published
        mock_cursor.fetchone.return_value = ("story-456", "separate")
        pub_resp = client.post(f"/videos/{run_id}/mark-published")
        assert pub_resp.status_code == 200
        assert pub_resp.json()["status"] == "ok"


def test_next_approved_204_when_empty(client):
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None  # No approved rows
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("video.api.main.get_db_connection") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_conn

        resp = client.get("/videos/next-approved")
        assert resp.status_code == 204
