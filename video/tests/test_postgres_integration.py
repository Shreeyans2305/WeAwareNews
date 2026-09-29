"""
Integration tests executing against a real PostgreSQL 15 database:
- Atomic concurrent claims (multi-threaded race condition)
- Expired claim sweeper & recovery
- Compare-and-set status transitions
- Publishing timeout auto-healing
- Real GIN index array overlap URL deduplication
- Heartbeat expiry aborting Veo calls
- Structural prompt template freeze test
"""

import os
import uuid
import time
import threading
from pathlib import Path
import psycopg2
import pytest
from fastapi.testclient import TestClient

from video.api.main import app
from video.pipeline.veo_client import VeoClient, ClaimCancelledError
from video.pipeline.scripter import assemble_veo_prompt, ClipScript
from video.bootstrap_assets import load_anchors_config

from backend.ingestion.store.postgres_store import _SCHEMA as PROD_PG_SCHEMA

TEST_DB_URL = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:testpass@127.0.0.1:5434/weaware_test")


@pytest.fixture(scope="session")
def setup_pg_database():
    """Ensure test tables exist in local PostgreSQL using production schema."""
    conn = psycopg2.connect(TEST_DB_URL)
    with conn.cursor() as cur:
        # Load official production schema from backend/ingestion/store/postgres_store.py
        cur.execute(PROD_PG_SCHEMA)
        
        # Migration DDL (with lock_timeout)
        migration_sql = Path("video/migrations/001_create_video_runs.sql").read_text()
        cur.execute(migration_sql)
    conn.commit()
    conn.close()


@pytest.fixture
def pg_client(setup_pg_database, monkeypatch):
    """TestClient wired directly to real local Postgres connection."""
    monkeypatch.setenv("DATABASE_URL", TEST_DB_URL)
    monkeypatch.setenv("API_KEY", "test-api-key-123")
    # Reset pool in video.api.db
    from video.api import db
    db._pool = None
    client = TestClient(app, headers={"x-api-key": "test-api-key-123"})
    return client


def test_real_pg_concurrent_claims(pg_client):
    """
    Test real concurrent claim requests from two threads hitting Postgres simultaneously.
    Proves partial unique index guarantees that only ONE thread claims (201) while the other receives 409.
    """
    story_id = f"race-story-{uuid.uuid4()}"
    results = []

    def make_claim():
        body = {
            "claim_mode": "separate",
            "timeout_minutes": 30,
            "headline_snapshot": "Breaking Tech News",
            "sources_snapshot": [{"source_name": "Reuters"}],
            "source_urls": [f"https://news.com/{story_id}"],
            "story_text_snapshot": "Sample story text",
        }
        resp = pg_client.post(f"/stories/{story_id}/video-claim", json=body)
        results.append(resp.status_code)

    t1 = threading.Thread(target=make_claim)
    t2 = threading.Thread(target=make_claim)

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Exactly one 201 Created and one 409 Conflict
    assert 201 in results
    assert 409 in results
    assert len(results) == 2


def test_real_pg_expired_claim_sweeper(pg_client):
    """
    Test that an expired claim is automatically marked 'failed' by the sweeper
    and frees the story to be claimed again.
    """
    story_id = f"sweeper-story-{uuid.uuid4()}"
    conn = psycopg2.connect(TEST_DB_URL)
    with conn.cursor() as cur:
        # Insert an expired run (expires_at 15 minutes in the past)
        cur.execute(
            """
            INSERT INTO video_runs (
                run_id, story_id, status, claim_mode, claimed_at,
                expires_at, heartbeat_at, headline_snapshot,
                sources_snapshot, source_urls, story_text_snapshot,
                created_at, updated_at
            )
            VALUES (
                %s, %s, 'claimed', 'separate', NOW() - INTERVAL '30 minutes',
                NOW() - INTERVAL '15 minutes', NOW(), 'Old Headline',
                '[]', ARRAY['https://example.com/1'], 'Old text',
                NOW() - INTERVAL '30 minutes', NOW() - INTERVAL '30 minutes'
            )
            """,
            (str(uuid.uuid4()), story_id),
        )
    conn.commit()
    conn.close()

    # New claim should trigger the sweeper, flip the old run to 'failed', and succeed (201)
    body = {
        "claim_mode": "separate",
        "timeout_minutes": 30,
        "headline_snapshot": "New Headline",
        "sources_snapshot": [],
        "source_urls": [f"https://news.com/{story_id}"],
        "story_text_snapshot": "New story text",
    }
    resp = pg_client.post(f"/stories/{story_id}/video-claim", json=body)
    assert resp.status_code == 201
    assert resp.json()["story_id"] == story_id

    # Verify in DB that old run status is now 'failed' with sweeper reason
    conn = psycopg2.connect(TEST_DB_URL)
    with conn.cursor() as cur:
        cur.execute("SELECT status, error_message FROM video_runs WHERE story_id = %s ORDER BY created_at ASC LIMIT 1", (story_id,))
        row = cur.fetchone()
        assert row[0] == "failed"
        assert "sweeper" in row[1].lower()
    conn.close()


def test_real_pg_compare_and_set(pg_client):
    """
    Test atomic compare-and-set status transitions against PostgreSQL.
    """
    story_id = f"cas-story-{uuid.uuid4()}"
    claim_resp = pg_client.post(
        f"/stories/{story_id}/video-claim",
        json={
            "claim_mode": "separate",
            "timeout_minutes": 30,
            "headline_snapshot": "CAS Headline",
            "sources_snapshot": [],
            "source_urls": [],
            "story_text_snapshot": "Text",
        },
    )
    assert claim_resp.status_code == 201
    run_id = claim_resp.json()["run_id"]

    # Valid CAS transition: 'claimed' -> 'scripting'
    resp = pg_client.post(f"/videos/{run_id}/status", json={"expected_status": "claimed", "new_status": "scripting"})
    assert resp.status_code == 200
    assert resp.json()["current_status"] == "scripting"

    # Invalid CAS: expecting 'claimed' but DB is now 'scripting' -> 409
    mismatch_resp = pg_client.post(f"/videos/{run_id}/status", json={"expected_status": "claimed", "new_status": "generating_video"})
    assert mismatch_resp.status_code == 409


def test_real_pg_publishing_timeout_auto_healing(pg_client):
    """
    Test that a video stuck in 'publishing' past publish_timeout is automatically
    reset to 'approved' by the sweeper in /videos/next-approved.
    """
    run_id = str(uuid.uuid4())
    conn = psycopg2.connect(TEST_DB_URL)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO video_runs (
                run_id, story_id, status, claim_mode, claimed_at,
                expires_at, heartbeat_at, headline_snapshot,
                sources_snapshot, source_urls, story_text_snapshot,
                video_gcs_uri, caption, hashtags, created_at, updated_at
            )
            VALUES (
                %s, 'stuck-story', 'publishing', 'separate', NOW() - INTERVAL '40 minutes',
                NOW() - INTERVAL '10 minutes', NOW(), 'Stuck Headline',
                '[]', '{}', 'Story Text',
                'gs://test-bucket/video.mp4', 'Caption', ARRAY['tag'],
                NOW() - INTERVAL '40 minutes', NOW() - INTERVAL '10 minutes'
            )
            """,
            (run_id,),
        )
    conn.commit()
    conn.close()

    # Calling /videos/next-approved sweeps the stuck run back to 'approved'
    # and then atomically claims it for publishing
    resp = pg_client.get("/videos/next-approved")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == run_id
    assert data["caption"] == "Caption"


def test_real_pg_url_overlap_dedupe(pg_client):
    """
    Test real PostgreSQL GIN index array overlap (&&) deduplication.
    """
    duplicate_url = f"https://globalnews.com/article-{uuid.uuid4()}"
    run_id = str(uuid.uuid4())

    conn = psycopg2.connect(TEST_DB_URL)
    with conn.cursor() as cur:
        # Insert a recent completed run with this source_url
        cur.execute(
            """
            INSERT INTO video_runs (
                run_id, story_id, status, claim_mode, claimed_at,
                expires_at, heartbeat_at, headline_snapshot,
                sources_snapshot, source_urls, story_text_snapshot,
                created_at, updated_at
            )
            VALUES (
                %s, 'prev-story', 'published', 'separate', NOW() - INTERVAL '2 days',
                NOW() + INTERVAL '1 day', NOW(), 'Recent Story',
                '[]', ARRAY[%s], 'Story Text',
                NOW() - INTERVAL '2 days', NOW() - INTERVAL '2 days'
            )
            """,
            (run_id, duplicate_url),
        )

        # Insert a new story in stories and items that uses that same URL
        new_story_id = f"new-story-{uuid.uuid4()}"
        cur.execute(
            "INSERT INTO stories (story_id, source_count, recency, created_at, posted) VALUES (%s, 2, '2026-09-29', NOW(), false)",
            (new_story_id,),
        )
        cur.execute(
            """
            INSERT INTO items (item_hash, source_id, source_name, source_type, region, url, title, raw_text, published_at, fetched_at, paywall, is_social, extraction_status, story_id)
            VALUES 
            (%s, 'src1', 'Publisher A', 'rss', 'us', %s, 'Article 1', %s, NOW(), NOW(), 0, 0, 'ok', %s),
            (%s, 'src2', 'Publisher B', 'rss', 'us', 'https://other.com/2', 'Article 2', %s, NOW(), NOW(), 0, 0, 'ok', %s)
            """,
            (
                str(uuid.uuid4()), duplicate_url, "Detailed body text of article 1 that is long enough. " * 5, new_story_id,
                str(uuid.uuid4()), "Detailed body text of article 2 that is long enough. " * 5, new_story_id,
            ),
        )
    conn.commit()
    conn.close()

    # Query candidates: the new story should be excluded because duplicate_url overlaps with the recent run
    resp = pg_client.get("/stories/video-candidates?dedupe_days=14")
    assert resp.status_code == 200
    candidates = resp.json()
    candidate_ids = [c["story_id"] for c in candidates]
    assert new_story_id not in candidate_ids


def test_heartbeat_expiry_stopping_veo_calls():
    """
    Test that VeoClient aborts immediately with ClaimCancelledError
    if the heartbeat callback signals that the claim was revoked or expired.
    """
    def revoked_claim_heartbeat():
        return False  # Claim is no longer active in DB

    client = VeoClient(run_id="test-run", heartbeat_callback=revoked_claim_heartbeat)
    with pytest.raises(ClaimCancelledError):
        client.check_budget_and_claim(upcoming_seconds=8)


def test_real_pg_candidates_full_filters(pg_client):
    """
    Test the candidate retrieval query against real PostgreSQL exercising ALL 5 filters:
    1. Paywall exclusion: paywall = 1
    2. Social exclusion: is_social = 1
    3. Thin text exclusion: length(trim(raw_text)) < 150
    4. Publisher count: must have >= 2 distinct publishers
    5. URL overlap: no overlap with recent video_runs within dedupe_days
    6. Valid candidate: passes all filters, correctly returns VideoCandidateResponse
    """
    conn = psycopg2.connect(TEST_DB_URL)
    with conn.cursor() as cur:
        # Clear existing test data
        cur.execute("DELETE FROM items;")
        cur.execute("DELETE FROM video_runs;")
        cur.execute("DELETE FROM stories;")

        # A recent video run with a specific URL
        recent_overlap_url = "https://bloomberg.com/news/overlapping-article"
        cur.execute(
            """
            INSERT INTO video_runs (
                run_id, story_id, status, claim_mode, claimed_at, expires_at,
                heartbeat_at, headline_snapshot, story_text_snapshot, source_urls,
                created_at, updated_at
            )
            VALUES (
                %s, 'old-story-1', 'published', 'separate', NOW() - INTERVAL '3 days',
                NOW() + INTERVAL '1 day', NOW(), 'Old Headline', 'Old text',
                ARRAY[%s], NOW() - INTERVAL '3 days', NOW() - INTERVAL '3 days'
            )
            """,
            (str(uuid.uuid4()), recent_overlap_url),
        )

        valid_text = (
            "This is a comprehensive, high-quality, long-form journalism report detailing the latest corporate "
            "antitrust rulings and international regulatory updates across all participating economies worldwide."
        )

        # Case 1: Paywall story (one free, one paywalled -> only 1 publisher survives)
        cur.execute("INSERT INTO stories VALUES ('story-paywall', 2, '2026-09-29T10:00:00Z', NOW(), NULL, FALSE)")
        cur.execute(
            """
            INSERT INTO items (item_hash, source_id, source_name, source_type, region, url, title, raw_text, published_at, fetched_at, paywall, is_social, extraction_status, story_id)
            VALUES 
            (%s, 's1', 'Publisher A', 'rss', 'us', 'https://pub-a.com/1', 'Article A', %s, NOW(), NOW(), 0, 0, 'ok', 'story-paywall'),
            (%s, 's2', 'Publisher B', 'rss', 'us', 'https://pub-b.com/2', 'Article B', %s, NOW(), NOW(), 1, 0, 'ok', 'story-paywall')
            """,
            (str(uuid.uuid4()), valid_text, str(uuid.uuid4()), valid_text),
        )

        # Case 2: Social story (one free, one social -> only 1 publisher survives)
        cur.execute("INSERT INTO stories VALUES ('story-social', 2, '2026-09-29T10:00:00Z', NOW(), NULL, FALSE)")
        cur.execute(
            """
            INSERT INTO items (item_hash, source_id, source_name, source_type, region, url, title, raw_text, published_at, fetched_at, paywall, is_social, extraction_status, story_id)
            VALUES 
            (%s, 's3', 'Publisher C', 'rss', 'us', 'https://pub-c.com/1', 'Article C', %s, NOW(), NOW(), 0, 0, 'ok', 'story-social'),
            (%s, 's4', 'Publisher D', 'social', 'us', 'https://pub-d.com/2', 'Article D', %s, NOW(), NOW(), 0, 1, 'ok', 'story-social')
            """,
            (str(uuid.uuid4()), valid_text, str(uuid.uuid4()), valid_text),
        )

        # Case 3: Thin text story (one valid, one thin < 150 chars -> only 1 publisher survives)
        cur.execute("INSERT INTO stories VALUES ('story-thin', 2, '2026-09-29T10:00:00Z', NOW(), NULL, FALSE)")
        cur.execute(
            """
            INSERT INTO items (item_hash, source_id, source_name, source_type, region, url, title, raw_text, published_at, fetched_at, paywall, is_social, extraction_status, story_id)
            VALUES 
            (%s, 's5', 'Publisher E', 'rss', 'us', 'https://pub-e.com/1', 'Article E', %s, NOW(), NOW(), 0, 0, 'ok', 'story-thin'),
            (%s, 's6', 'Publisher F', 'rss', 'us', 'https://pub-f.com/2', 'Article F', 'Too short text', NOW(), NOW(), 0, 0, 'ok', 'story-thin')
            """,
            (str(uuid.uuid4()), valid_text, str(uuid.uuid4())),
        )

        # Case 4: Single publisher story (both articles from same publisher -> only 1 publisher)
        cur.execute("INSERT INTO stories VALUES ('story-single-pub', 2, '2026-09-29T10:00:00Z', NOW(), NULL, FALSE)")
        cur.execute(
            """
            INSERT INTO items (item_hash, source_id, source_name, source_type, region, url, title, raw_text, published_at, fetched_at, paywall, is_social, extraction_status, story_id)
            VALUES 
            (%s, 's7', 'SamePublisher', 'rss', 'us', 'https://same.com/1', 'Article G', %s, NOW(), NOW(), 0, 0, 'ok', 'story-single-pub'),
            (%s, 's8', 'SamePublisher', 'rss', 'us', 'https://same.com/2', 'Article H', %s, NOW(), NOW(), 0, 0, 'ok', 'story-single-pub')
            """,
            (str(uuid.uuid4()), valid_text, str(uuid.uuid4()), valid_text),
        )

        # Case 5: Overlapping story (has 2 publishers, but one URL overlaps with recent run)
        cur.execute("INSERT INTO stories VALUES ('story-overlap', 2, '2026-09-29T10:00:00Z', NOW(), NULL, FALSE)")
        cur.execute(
            """
            INSERT INTO items (item_hash, source_id, source_name, source_type, region, url, title, raw_text, published_at, fetched_at, paywall, is_social, extraction_status, story_id)
            VALUES 
            (%s, 's9', 'Publisher I', 'rss', 'us', %s, 'Article I', %s, NOW(), NOW(), 0, 0, 'ok', 'story-overlap'),
            (%s, 's10', 'Publisher J', 'rss', 'us', 'https://pub-j.com/2', 'Article J', %s, NOW(), NOW(), 0, 0, 'ok', 'story-overlap')
            """,
            (str(uuid.uuid4()), recent_overlap_url, valid_text, str(uuid.uuid4()), valid_text),
        )

        # Case 6: Valid story (passes all filters: 2 distinct publishers, text >= 150, no paywall, no social, no overlap)
        cur.execute("INSERT INTO stories VALUES ('story-valid', 2, '2026-09-29T12:00:00Z', NOW(), NULL, FALSE)")
        cur.execute(
            """
            INSERT INTO items (item_hash, source_id, source_name, source_type, region, url, title, raw_text, published_at, fetched_at, paywall, is_social, extraction_status, story_id)
            VALUES 
            (%s, 's11', 'Reuters', 'rss', 'us', 'https://reuters.com/clean-article-1', 'Major Tech Breakthrough', %s, NOW(), NOW(), 0, 0, 'ok', 'story-valid'),
            (%s, 's12', 'Associated Press', 'rss', 'us', 'https://apnews.com/clean-article-2', 'Scientists Confirm Finding', %s, NOW(), NOW(), 0, 0, 'ok', 'story-valid')
            """,
            (str(uuid.uuid4()), valid_text, str(uuid.uuid4()), valid_text),
        )

    conn.commit()
    conn.close()

    # Query the actual FastAPI endpoint
    resp = pg_client.get("/stories/video-candidates?dedupe_days=14")
    assert resp.status_code == 200
    candidates = resp.json()

    candidate_ids = [c["story_id"] for c in candidates]
    
    # Assert all invalid cases are filtered out
    assert "story-paywall" not in candidate_ids, "Paywalled story was not filtered out"
    assert "story-social" not in candidate_ids, "Social story was not filtered out"
    assert "story-thin" not in candidate_ids, "Thin text story was not filtered out"
    assert "story-single-pub" not in candidate_ids, "Single publisher story was not filtered out"
    assert "story-overlap" not in candidate_ids, "URL overlap story was not filtered out"

    # Assert valid story is present and fully populated
    assert "story-valid" in candidate_ids, "Valid candidate story was incorrectly excluded"
    valid_c = next(c for c in candidates if c["story_id"] == "story-valid")
    assert valid_c["headline"] in ["Major Tech Breakthrough", "Scientists Confirm Finding"]
    assert valid_c["source_count"] == 2
    assert len(valid_c["articles"]) == 2
    assert len(valid_c["source_urls"]) == 2


def test_baseline_prompt_structural_freeze():
    """
    Test locking the baseline prompt structure: fails if assembled prompts
    drift structurally from the frozen smoke-test prompt template.
    """
    clip = ClipScript(
        clip_index=1,
        duration_seconds=8,
        speaker="marcus",
        dialogue="Welcome back to WeAware Late Night.",
        action="He raises an eyebrow with a wry smirk",
        camera="Medium close-up shot",
        claims=[],
    )
    config = load_anchors_config()
    prompt = assemble_veo_prompt(clip, config)

    # Required baseline structural anchors
    assert "Medium close-up shot" in prompt, "Missing camera shot framing"
    assert "Marcus Vance" in prompt, "Missing anchor name"
    assert "Late Night Satire Studio" in prompt or "studio" in prompt.lower(), "Missing set context"
    assert 'Dialogue: "Welcome back to WeAware Late Night."' in prompt or '"Welcome back to WeAware Late Night."' in prompt
    assert "vertical 9:16 framing" in prompt, "Missing vertical aspect ratio instruction"
    assert "no subtitles" in prompt, "Missing clean video rule"
    assert "no watermarks" in prompt, "Missing watermark exclusion rule"
    assert "no on-screen text" in prompt, "Missing on-screen text exclusion rule"
