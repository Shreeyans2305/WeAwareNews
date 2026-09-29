-- Migration: 001_create_video_runs.sql
-- Description: Creates the video_runs table and indexes for WeAware Late Night video pipeline
-- Idempotent & Transactional

BEGIN;

SET LOCAL lock_timeout = '5s';

CREATE TABLE IF NOT EXISTS video_runs (
    run_id UUID PRIMARY KEY,
    story_id TEXT NOT NULL,
    status TEXT NOT NULL,
    -- Allowed statuses:
    -- 'claimed', 'scripting', 'generating_video', 'post_processing',
    -- 'ready_for_review', 'approved', 'publishing', 'published',
    -- 'rejected', 'failed'
    
    claim_mode TEXT NOT NULL DEFAULT 'separate',
    claimed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    heartbeat_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Story data snapshots (survives reclustering)
    headline_snapshot TEXT NOT NULL,
    sources_snapshot JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_urls TEXT[] NOT NULL DEFAULT '{}',
    story_text_snapshot TEXT NOT NULL,
    
    -- Review HMAC token verification
    review_token_hash TEXT,
    review_decision_at TIMESTAMPTZ,
    
    -- Artifacts & Publication
    video_gcs_uri TEXT,
    thumbnail_gcs_uri TEXT,
    caption TEXT,
    hashtags TEXT[] DEFAULT '{}',
    script_data JSONB,
    claims_data JSONB,
    run_metadata JSONB,
    idempotency_key TEXT,
    
    -- Cost tracking & errors
    estimated_cost_usd NUMERIC(6, 4) DEFAULT 0.0000,
    veo_seconds_used INTEGER DEFAULT 0,
    error_message TEXT,
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- GIN index for source URL overlap deduplication
CREATE INDEX IF NOT EXISTS idx_video_runs_source_urls 
ON video_runs USING GIN(source_urls);

-- Partial unique index to enforce single active run per story_id
CREATE UNIQUE INDEX IF NOT EXISTS idx_video_runs_active_story
ON video_runs(story_id)
WHERE status IN ('claimed', 'scripting', 'generating_video', 'post_processing', 'ready_for_review', 'approved', 'publishing', 'published');

-- Query indices for scheduler/sweeper & status polling
CREATE INDEX IF NOT EXISTS idx_video_runs_status 
ON video_runs(status);

CREATE INDEX IF NOT EXISTS idx_video_runs_expires_at 
ON video_runs(expires_at) 
WHERE status IN ('claimed', 'scripting', 'generating_video', 'post_processing', 'publishing');

CREATE INDEX IF NOT EXISTS idx_video_runs_created_at 
ON video_runs(created_at);

COMMIT;
