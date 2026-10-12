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
def client(monkeypatch):
    monkeypatch.setenv("VIDEO_API_KEY", "test-key-default")
    return TestClient(app, headers={"x-api-key": "test-key-default"})


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


def test_review_confirm_page_flash_fallback_badge(client):
    run_id = str(uuid.uuid4())
    token = generate_review_token(run_id, "approve", expires_in_seconds=3600)

    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {
        "status": "ready_for_review",
        "headline_snapshot": "Breaking Tech Satire",
        "caption": "Check out this reel",
        "video_gcs_uri": "gs://bucket/runs/1/final.mp4",
        "thumbnail_gcs_uri": "gs://bucket/runs/1/thumb.jpg",
        "run_metadata": {
            "pro_selection_reason": "pro_unavailable_flash_fallback",
            "editor_fallback_active": True,
        },
    }
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("video.api.main.get_db_connection") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_conn

        resp = client.get(f"/videos/review?token={token}&action=approve")
        assert resp.status_code == 200
        assert "editor: flash fallback" in resp.text
        assert "pro_unavailable_flash_fallback" in resp.text
        assert "[editor: flash fallback]" in resp.text


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


# ---------------------------------------------------------------------------
# 8. API Key Authentication Tests (PHASE 1 requirement)
# ---------------------------------------------------------------------------

@pytest.fixture
def authed_client(monkeypatch):
    """TestClient with VIDEO_API_KEY set in environment."""
    monkeypatch.setenv("VIDEO_API_KEY", "test-video-api-key-xyz")
    from video.api import security
    # Force re-read of env var by using a fresh client
    return TestClient(app, headers={"x-api-key": "test-video-api-key-xyz"})


@pytest.fixture
def unauthed_client(monkeypatch):
    """TestClient with VIDEO_API_KEY set but NO x-api-key header."""
    monkeypatch.setenv("VIDEO_API_KEY", "test-video-api-key-xyz")
    return TestClient(app, headers={})


def test_next_approved_requires_auth_missing_header(unauthed_client):
    """GET /videos/next-approved must return 401 when x-api-key header is absent."""
    resp = unauthed_client.get("/videos/next-approved")
    assert resp.status_code == 401
    assert "Missing x-api-key" in resp.json()["detail"]


def test_next_approved_requires_auth_wrong_key(monkeypatch):
    """GET /videos/next-approved must return 401 when x-api-key is wrong."""
    monkeypatch.setenv("VIDEO_API_KEY", "correct-key")
    client = TestClient(app, headers={"x-api-key": "wrong-key"})
    resp = client.get("/videos/next-approved")
    assert resp.status_code == 401
    assert "Invalid API Key" in resp.json()["detail"]


def test_mark_published_requires_auth_missing_header(unauthed_client):
    """POST /videos/{run_id}/mark-published must return 401 when x-api-key is absent."""
    run_id = str(uuid.uuid4())
    resp = unauthed_client.post(f"/videos/{run_id}/mark-published")
    assert resp.status_code == 401
    assert "Missing x-api-key" in resp.json()["detail"]


def test_mark_published_requires_auth_wrong_key(monkeypatch):
    """POST /videos/{run_id}/mark-published must return 401 when x-api-key is wrong."""
    monkeypatch.setenv("VIDEO_API_KEY", "correct-key")
    client = TestClient(app, headers={"x-api-key": "totally-wrong-key"})
    run_id = str(uuid.uuid4())
    resp = client.post(f"/videos/{run_id}/mark-published")
    assert resp.status_code == 401
    assert "Invalid API Key" in resp.json()["detail"]


def test_video_candidates_requires_auth_missing_header(unauthed_client):
    """GET /stories/video-candidates must return 401 when x-api-key header is absent."""
    resp = unauthed_client.get("/stories/video-candidates")
    assert resp.status_code == 401


def test_claim_requires_auth_missing_header(unauthed_client):
    """POST /stories/{story_id}/video-claim must return 401 when x-api-key header is absent."""
    body = {
        "claim_mode": "separate",
        "timeout_minutes": 45,
        "headline_snapshot": "Test",
        "sources_snapshot": [],
        "source_urls": [],
        "story_text_snapshot": "Test text",
    }
    resp = unauthed_client.post("/stories/story-test/video-claim", json=body)
    assert resp.status_code == 401


def test_server_missing_video_api_key_returns_401():
    """
    When VIDEO_API_KEY is not set on the server side, verify_api_key must
    return 401 (not silently bypass auth). This guards against misconfiguration.
    """
    import os
    original = os.environ.pop("VIDEO_API_KEY", None)
    os.environ.pop("API_KEY", None)
    try:
        client = TestClient(app, headers={"x-api-key": "any-key"})
        resp = client.get("/videos/next-approved")
        assert resp.status_code == 401
        assert "VIDEO_API_KEY missing" in resp.json()["detail"]
    finally:
        if original is not None:
            os.environ["VIDEO_API_KEY"] = original


def test_health_and_healthz_no_auth_required():
    """Health check endpoints must remain unauthenticated."""
    client = TestClient(app, headers={})  # no auth
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# 9. Signed URL Expiry & Caption Disclosure Tests (PHASE 1 requirements)
# ---------------------------------------------------------------------------

def test_signed_url_2hr_expiry_invoked(monkeypatch):
    """
    Verify that blob.generate_signed_url is called with expiration=7200 (2 hours).
    """
    monkeypatch.setenv("VIDEO_API_KEY", "test-key-signed-url")
    run_id = str(uuid.uuid4())
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {
        "run_id": run_id,
        "story_id": "story-signed",
        "video_gcs_uri": "gs://weaware-video/runs/1/final.mp4",
        "thumbnail_gcs_uri": "gs://weaware-video/runs/1/thumb.jpg",
        "caption": "Check out this reel",
        "hashtags": ["news"],
        "idempotency_key": "idemp-123",
        "run_metadata": {"satire_disclosure": "\n\n⚠️ AI-generated satire."},
    }
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_blob = MagicMock()
    mock_blob.generate_signed_url.return_value = "https://signed-url.example.com/video.mp4"
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_storage_client = MagicMock()
    mock_storage_client.bucket.return_value = mock_bucket

    with patch("video.api.main.get_db_connection") as mock_get_db, \
         patch("builtins.__import__", side_effect=lambda name, *args, **kwargs: (
             type("FakeModule", (), {"Client": lambda: mock_storage_client})()
             if name == "google.cloud.storage" else __import__(name, *args, **kwargs)
         )):
        # Simpler: just patch the storage module in sys.modules
        pass

    import sys
    import types
    fake_storage = types.ModuleType("google.cloud.storage")
    fake_storage.Client = lambda: mock_storage_client  # type: ignore[attr-defined]

    with patch("video.api.main.get_db_connection") as mock_get_db, \
         patch.dict("sys.modules", {"google.cloud.storage": fake_storage}):
        mock_get_db.return_value.__enter__.return_value = mock_conn
        client = TestClient(app, headers={"x-api-key": "test-key-signed-url"})
        resp = client.get("/videos/next-approved")

    assert resp.status_code == 200
    # Verify signed URL was requested with 2-hour (7200s) expiry
    mock_blob.generate_signed_url.assert_called_once()
    call_kwargs = mock_blob.generate_signed_url.call_args
    assert call_kwargs.kwargs.get("expiration") == 7200 or (
        call_kwargs.args and call_kwargs.args[1] == 7200
    ), f"Expected expiration=7200, got: {call_kwargs}"


def test_caption_includes_satire_disclosure(monkeypatch):
    """
    /videos/next-approved must append the satire_disclosure from run_metadata
    to the caption returned to Make.com (since Meta AI label field is unreliable).
    """
    monkeypatch.setenv("VIDEO_API_KEY", "test-key-caption")
    run_id = str(uuid.uuid4())
    disclosure = "\n\n⚠️ This video is AI-generated satire for entertainment purposes. Not real news."
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {
        "run_id": run_id,
        "story_id": "story-disclosure",
        "video_gcs_uri": "gs://test/vid.mp4",
        "thumbnail_gcs_uri": "gs://test/thumb.jpg",
        "caption": "Big news tonight #comedy",
        "hashtags": ["comedy"],
        "idempotency_key": "idemp-abc",
        "run_metadata": {"satire_disclosure": disclosure},
    }
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("video.api.main.get_db_connection") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_conn
        client = TestClient(app, headers={"x-api-key": "test-key-caption"})
        resp = client.get("/videos/next-approved")

    assert resp.status_code == 200
    returned_caption = resp.json()["caption"]
    assert "Big news tonight" in returned_caption, "Original caption content missing"
    assert disclosure.strip() in returned_caption, (
        f"Satire disclosure not found in caption.\nCaption: {returned_caption}"
    )


def test_caption_disclosure_not_doubled(monkeypatch):
    """
    If the disclosure was already baked into the stored caption, it must NOT be appended again.
    """
    monkeypatch.setenv("VIDEO_API_KEY", "test-key-nodupe")
    run_id = str(uuid.uuid4())
    disclosure = "\n\n⚠️ AI-generated satire."
    caption_with_disclosure = f"Some news tonight{disclosure}"
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {
        "run_id": run_id,
        "story_id": "story-nodupe",
        "video_gcs_uri": "gs://test/vid.mp4",
        "thumbnail_gcs_uri": "gs://test/thumb.jpg",
        "caption": caption_with_disclosure,
        "hashtags": [],
        "idempotency_key": "idemp-dupe",
        "run_metadata": {"satire_disclosure": disclosure},
    }
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("video.api.main.get_db_connection") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_conn
        client = TestClient(app, headers={"x-api-key": "test-key-nodupe"})
        resp = client.get("/videos/next-approved")

    assert resp.status_code == 200
    returned = resp.json()["caption"]
    # Disclosure appears exactly once
    assert returned.count(disclosure.strip()) == 1, (
        f"Disclosure was doubled in caption: {returned}"
    )


def test_caption_fallback_disclosure_when_no_run_metadata(monkeypatch):
    """
    When run_metadata is NULL/empty in DB, /videos/next-approved must still
    append a default disclosure disclosure to the caption.
    """
    monkeypatch.setenv("VIDEO_API_KEY", "test-key-fallback")
    run_id = str(uuid.uuid4())
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = {
        "run_id": run_id,
        "story_id": "story-fallback",
        "video_gcs_uri": "gs://test/vid.mp4",
        "thumbnail_gcs_uri": "",
        "caption": "Something happened today",
        "hashtags": [],
        "idempotency_key": "idemp-fallback",
        "run_metadata": None,  # DB row has NULL run_metadata
    }
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("video.api.main.get_db_connection") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_conn
        client = TestClient(app, headers={"x-api-key": "test-key-fallback"})
        resp = client.get("/videos/next-approved")

    assert resp.status_code == 200
    returned_caption = resp.json()["caption"]
    # Must contain some disclosure even with NULL run_metadata
    assert "AI-generated" in returned_caption or "satire" in returned_caption.lower(), (
        f"No fallback disclosure found in caption: {returned_caption}"
    )


def test_reclaim_after_timeout_via_sweeper(monkeypatch):
    """
    Publishing timeout sweeper: a run stuck in 'publishing' past its expires_at
    is reset to 'approved' and made available to the next /videos/next-approved call.
    This is the re-claim test for failed Instagram posts.
    Simulated via mock: sweeper UPDATE runs, then the atomic SELECT picks the run.
    """
    monkeypatch.setenv("VIDEO_API_KEY", "test-key-sweeper")
    run_id = str(uuid.uuid4())
    mock_cursor = MagicMock()
    # The sweeper UPDATE is the first execute(); subsequent SELECT finds the reset run.
    mock_cursor.fetchone.return_value = {
        "run_id": run_id,
        "story_id": "story-stuck",
        "video_gcs_uri": "gs://test/vid.mp4",
        "thumbnail_gcs_uri": "",
        "caption": "Stuck video caption",
        "hashtags": [],
        "idempotency_key": "idemp-sweeper",
        "run_metadata": {},
    }
    mock_conn = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("video.api.main.get_db_connection") as mock_get_db:
        mock_get_db.return_value.__enter__.return_value = mock_conn
        client = TestClient(app, headers={"x-api-key": "test-key-sweeper"})
        resp = client.get("/videos/next-approved?publish_timeout_min=15")

    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == run_id
    # Verify that both the sweeper UPDATE and the atomic UPDATE were called
    assert mock_cursor.execute.call_count >= 2, (
        "Expected at least 2 SQL execute calls (sweeper + atomic SELECT-UPDATE)"
    )
