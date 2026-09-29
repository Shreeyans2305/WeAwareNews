# Architecture & Implementation Decisions

## 1. Reclustering & `posted=true` Survival Investigation
**Finding:** The existing `posted=true` protection **DOES NOT survive reclustering**.

### Code Evidence
1. In [`backend/recluster.py`](file:///Users/shreeyansvichare/Code/WeAwareNews/backend/recluster.py#L74-L82):
   ```python
   with store._connect() as conn:
       conn.execute("DELETE FROM stories")
       conn.executemany(
           "INSERT INTO stories(story_id, source_count, recency, created_at, centroid) VALUES (?, ?, ?, ?, ?)",
           story_rows,
       )
   ```
   Every recluster run clears the local `stories` table and generates freshly minted random `uuid.uuid4()` strings for all story clusters ([`ingestion/cluster.py:L458, L552`](file:///Users/shreeyansvichare/Code/WeAwareNews/backend/ingestion/cluster.py#L458)).
2. In [`backend/sync_to_postgres.py`](file:///Users/shreeyansvichare/Code/WeAwareNews/backend/sync_to_postgres.py#L197-L204):
   ```python
   INSERT INTO stories(story_id, source_count, recency, created_at, centroid, posted)
   VALUES (%s, %s, %s, %s, %s, FALSE)
   ON CONFLICT(story_id) DO UPDATE SET
       source_count = EXCLUDED.source_count,
       recency      = EXCLUDED.recency,
       centroid     = COALESCE(EXCLUDED.centroid, stories.centroid)
   ```
   And on items:
   ```python
   UPDATE items SET story_id = EXCLUDED.story_id ...
   ```
### Analysis
- While `sync_to_postgres.py` does not downgrade `posted=true` on conflicting `story_id`s, reclustering assigns items to **new UUIDs**.
- These new `story_id`s do not conflict with the old ones; they insert as brand new rows with `posted = FALSE`.
- The old `story_id` remains as an orphaned ghost row with `posted = true`, while the news items themselves move to the new `story_id` and become eligible for re-posting by `/stories/next`.
- **Architectural Response for Video**:
  - We explicitly dropped the Foreign Key from `video_runs.story_id` to `stories(story_id)`.
  - We implemented URL-based deduplication (`source_urls TEXT[]` with a PostgreSQL GIN index). Even when `story_id`s are regenerated, any story sharing source URLs with a recent video run within `VIDEO_DEDUPE_DAYS` (default 14) is blocked from re-generation.

---

## 2. API Architecture Decision (Choice A vs B)
- **Selected**: **Option A: Dedicated Cloud Run Service `weaware-video-api`**.
- **Rationale**:
  1. **Zero-risk to existing production API**: `weaware-api` remains completely untouched, eliminating any deployment risk or downtime for Make.com's live Instagram posting.
  2. **Python 3.12 Runtime**: `weaware-video-api` runs on modern Python 3.12 with clean type hints, whereas existing `weaware-api` runs Python 3.9 in a lean container.
  3. **Connection Protection on `db-f1-micro`**: `weaware-video-api` enforces an isolated connection pool of 1-2 connections with strict timeouts, preventing database connection exhaustion.
  4. **Scoped IAM & Security**: `weaware-video-api` runs under `weaware-video-sa` with restricted permissions.

---

## 3. Vertex AI Model Selection & Constraints
- **Veo 3.1 Models**:
  - `veo-3.1-fast-generate-001` configured as the default tier (`VEO_MODEL_TIER=fast`) for fast turnaround and low cost (~$0.15/s).
  - `veo-3.1-generate-001` configured for the standard broadcast tier (~$0.40/s).
- **First-Frame Image Conditioning**:
  - Vertex AI Veo 3.1 officially rejects `aspect_ratio="9:16"` when passed multi-image `reference_images` (which are restricted to 16:9).
  - However, native 9:16 video generation **works seamlessly with first-frame image conditioning** (`image=...`), as proven in Phase 0 smoke test.
  - We use pre-generated 9:16 anchor keyframes (Marcus and Maya) to initiate each clip.
- **Image Generation Migration**:
  - Google Cloud deprecated `imagen-3.0` API endpoints in favor of multimodal generation via `gemini-2.5-flash-image` and `gemini-3.1-flash-image` with `response_modalities=["IMAGE"]`. The asset generator was built natively on this supported pattern.
- **Native Audio**:
  - Generated directly by Veo via `generate_audio=True` in `GenerateVideosConfig`.

---

## 4. Security & Human Review Flow
- **Single-Use HMAC Review Tokens**:
  - Review links use HMAC-SHA256 tokens (`{run_id}:{action}:{expiry}:{signature}`) verified via constant-time `hmac.compare_digest`.
  - `GET /videos/review` renders a preview confirmation page only (no state mutation on GET, protecting against email scanner bot clicks).
  - `POST /videos/review` commits the decision, updates `status = 'approved' | 'rejected'`, records `review_decision_at`, and prevents replay attacks.

---

## 5. Known Limitations & Next Steps
1. **Dialogue Verbatim Drift**: Veo occasionally paraphrases or drops words in spoken dialogue when action prompts are dense. Pacing budget (~2.5 words/sec) and concise prompts minimize drift. If dialogue fidelity requires exact phoneme timing, the architecture includes a post-production TTS mux fallback.
2. **Character & Desk Continuity**: First-frame conditioning ensures initial frame consistency; subtle lighting or attire shifts can occur across shot cuts. Hard cuts between distinct camera framings (Host medium -> Host wide -> Correspondent -> Host sign-off) mask continuity jumps naturally, mimicking real television editing.
3. **Future Extension**: Multi-platform publishing adapter (adding YouTube Shorts and TikTok endpoints alongside Make.com Instagram Reel polling).
