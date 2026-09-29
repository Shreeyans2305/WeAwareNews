# Architecture & Implementation Decisions

## Phase 0: Vertex AI Verification & Smoke Test
- **Veo Model Selection**: 
  - Standard tier: `veo-3.1-generate-001`
  - Fast tier: `veo-3.1-fast-generate-001`
  - Default configured to `fast` (`VEO_MODEL_TIER=fast`) for development and testing economy (~$0.15/sec vs ~$0.40/sec).
- **Gemini Model Selection**:
  - Scripting & Story Selection: `gemini-2.5-flash` (fast, deterministic structured JSON, low latency).
  - Fact-Checking / Editorial Review: `gemini-2.5-pro` (higher reasoning depth for claim-to-source grounding).
- **Image Model Selection**:
  - `gemini-2.5-flash-image` (and `gemini-3.1-flash-image`) superseded legacy `imagen-3.0` models on Vertex AI. Image generation is invoked via `generate_content` with `response_modalities=["IMAGE"]`.
- **Vertical 9:16 Image Conditioning**:
  - Confirmed via live smoke test: Veo 3.1 natively supports `aspect_ratio="9:16"` conditioned on a first-frame starting plate (`image=...`), while `reference_images` is limited to 16:9 in the API. First-frame conditioning is therefore the primary mechanism for character and set consistency.
- **Native Audio**:
  - Enabled via `generate_audio=True` in `GenerateVideosConfig`. Produces broadcast dialogue and ambient room sound.

## Phase 1: Database & API
- **API Architecture (Choice A vs B)**:
  - Selected **Option A: Dedicated Cloud Run Service `weaware-video-api`**.
  - *Justification*:
    1. **Zero-risk to existing production API**: `weaware-api` remains completely untouched, avoiding any risk of deployment failure or downtime for the existing Make.com news automation.
    2. **Modern Runtime**: `weaware-video-api` runs on Python 3.12 while existing `weaware-api` runs Python 3.9.
    3. **Connection Pooling on `db-f1-micro`**: `weaware-video-api` uses an explicit connection pool capped at 1-2 connections with short timeouts, eliminating the risk of Cloud SQL connection exhaustion.
    4. **Isolated IAM & Secrets**: Runs under `weaware-video-sa` with scoped permissions rather than broadening the existing API service account.
- **`story_id` vs URL Deduplication**:
  - `recluster.py` wipes `stories` and generates random UUIDs for all clusters on every run.
  - Therefore, `video_runs` does NOT have a foreign key to `stories(story_id)`.
  - Deduplication is enforced via `source_urls TEXT[]` with a PostgreSQL GIN index (`source_urls && ARRAY[...]`), preventing the same news event from being turned into video multiple times across reclustering cycles within `VIDEO_DEDUPE_DAYS` (default 14 days).
  - Dropped `shared` claim mode in favor of URL overlap deduplication: since story_ids mutate, checking URL overlap against both `video_runs` and posted stories provides a durable cross-pipeline deduplication guarantee.
- **Atomic Claiming & Sweeper**:
  - Enforced via PostgreSQL partial unique index on `story_id` for active statuses (`claimed`, `scripting`, `generating_video`, `post_processing`, `ready_for_review`, `approved`, `publishing`, `published`).
  - Stale claims (`expires_at < NOW()`) are automatically flipped to `failed` by an integrated sweeper before any new claim is evaluated.
- **Review Security**:
  - Review links use HMAC-SHA256 tokens (`token_payload = f"{run_id}:{action}:{expiry_timestamp}"`).
  - Verified with constant-time `hmac.compare_digest`.
  - Single-use enforced by checking that `video_runs.status == 'ready_for_review'` upon commit and recording `review_decision_at`.
