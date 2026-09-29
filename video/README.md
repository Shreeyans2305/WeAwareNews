# WeAware Late Night - Automated Satirical Video Pipeline

An automated 9:16 vertical video production pipeline extending the WeAware News platform. It selects corroborated multi-source news stories, generates punchy late-night satire scripts with Gemini, generates broadcast video and dialogue with Vertex AI Veo 3.1, performs audio/video post-production via FFmpeg, and exposes approved videos to Make.com for Instagram Reels publication.

---

## 1. Architecture Overview

```
                                      +--------------------------+
                                      |  Cloud Scheduler (02:00) |
                                      +------------+-------------+
                                                   |
                                                   v
                                      +--------------------------+
                                      |     Cloud Workflows      |
                                      +------------+-------------+
                                                   |
                             +---------------------+---------------------+
                             | Guard: Ingestion check + Freshness check  |
                             +---------------------+---------------------+
                                                   |
                                                   v
                                      +--------------------------+
                                      | Cloud Run Job (Pipeline) |
                                      +------------+-------------+
                                                   |
       +-----------------------+-------------------+-----------------------+
       |                       |                   |                       |
       v                       v                   v                       v
1. Story Picker         2. Scripter & Editor  3. Veo Generation      4. FFmpeg Post
(Gemini 2.5 Flash)      (Strict Fact Ground)  (Veo 3.1 9:16 Audio)   (-14 LUFS, Subs, Lower3rd)
       |                       |                   |                       |
       +-----------------------+-------------------+-----------------------+
                                                   |
                                                   v
                                      +--------------------------+
                                      |   GCS Bucket & DB Runs   |
                                      +------------+-------------+
                                                   |
                                                   v
                                      +--------------------------+
                                      |   Human Approval Gate    |
                                      | (Pub/Sub + Webhook HMAC) |
                                      +------------+-------------+
                                                   |
                                                   v
                                      +--------------------------+
                                      | Make.com Instagram Flow  |
                                      | (/videos/next-approved)  |
                                      +--------------------------+
```

---

## 2. GCP APIs to Enable

Ensure the following APIs are activated on `project-9ba21d45-1dfd-4108-b69`:

```bash
gcloud services enable \
  aiplatform.googleapis.com \
  run.googleapis.com \
  workflows.googleapis.com \
  cloudscheduler.googleapis.com \
  pubsub.googleapis.com \
  secretmanager.googleapis.com \
  cloudbuild.googleapis.com \
  storage.googleapis.com
```

---

## 3. Vertex AI Model Selection & Quotas

### Verified Active Model IDs in `us-central1`

| Role | Active Model ID | Pricing / Unit |
| :--- | :--- | :--- |
| **Video Generation (Fast Tier)** | `veo-3.1-fast-generate-001` | ~$0.15 / second |
| **Video Generation (Standard Tier)** | `veo-3.1-generate-001` | ~$0.40 / second |
| **Story Picker & Scriptwriting** | `gemini-2.5-flash` | $0.10 / 1M in, $0.40 / 1M out |
| **Standards & Fact Editor** | `gemini-2.5-pro` | $1.25 / 1M in, $5.00 / 1M out |
| **Anchor/Set Asset Generator** | `gemini-2.5-flash-image` | Pay-per-image |

### Quotas to Request in Google Cloud Console
Under **IAM & Admin -> Quotas & System Limits** for `us-central1`:
- **Vertex AI Video Generation Requests per Minute**: Request at least `5 RPM` (allows parallel 4-clip generation).
- **Vertex AI Video Generation Seconds per Minute**: Request at least `60 seconds/min`.

---

## 4. Cost Caps & Worst-Case Spend

### Tunables in `video/config/settings.py`
- `VEO_MODEL_TIER`: `fast` (default) or `standard`
- `MAX_COST_USD_PER_RUN`: `$25.00`
- `MAX_RUNS_PER_DAY`: `4`
- `MAX_VEO_SECONDS_PER_DAY`: `250`

### Cost Breakdown per 32-Second Episode (4 clips × 8s)

| Scenario | Fast Tier (`veo-3.1-fast`) | Standard Tier (`veo-3.1`) |
| :--- | :--- | :--- |
| **Base Run (32 seconds, 0 retries)** | **$4.80** | **$12.80** |
| **1 Safety Retry (40 seconds total)** | **$6.00** | **$16.00** |
| **Worst-Case (4 clips × 3 attempts = 96s)** | **$14.40** | **$38.40** *(capped at $25.00)* |

*Note: The pipeline checks remaining budget before every clip and aborts if `MAX_COST_USD_PER_RUN` would be exceeded.*

---

## 5. Local Dry-Run Testing (Zero Spend)

Test story selection, strict Pydantic script generation, and editorial verification against real news data read-only without calling Veo or spending money:

```bash
# 1. Run local API server (or point to staging)
uvicorn video.api.main:app --port 8080 &

# 2. Execute local dry run
PYTHONPATH=. python video/pipeline/runner.py --dry-run
```

---

## 6. One-Off Asset Bootstrap

The anchor and studio set plates are generated once and stored in GCS. To prevent accidental spend, the script includes a safety lock requiring `--confirm`:

```bash
# Inspect plan and estimated cost ($0.15 for 5 plates)
python video/bootstrap_assets.py

# When approved, execute master generation
python video/bootstrap_assets.py --confirm
```

---

## 7. Exact Deployment Order (Awaiting Approval)

Follow this sequence strictly when deploying:

1. **Cloud SQL Backup**:
   ```bash
   gcloud sql backups create --instance=weaware-pg --project=project-9ba21d45-1dfd-4108-b69 --description="Pre-video-runs migration"
   ```
2. **Database Migration**:
   Connect via Cloud SQL Proxy and run `video/migrations/001_create_video_runs.sql`.
3. **Build & Push Containers**:
   ```bash
   # Build video container with FFmpeg
   gcloud builds submit --tag us-central1-docker.pkg.dev/project-9ba21d45-1dfd-4108-b69/weaware-repo/weaware-video-api:latest -f video/Dockerfile .
   gcloud builds submit --tag us-central1-docker.pkg.dev/project-9ba21d45-1dfd-4108-b69/weaware-repo/weaware-video-job:latest -f video/Dockerfile .
   ```
4. **Terraform Apply**:
   ```bash
   cd video/terraform
   terraform apply
   ```
   *Creates GCS bucket, SAs, IAM, Pub/Sub, Cloud Run service & job, Workflows, and paused Scheduler job.*
5. **Run Master Asset Bootstrap**:
   ```bash
   python video/bootstrap_assets.py --confirm
   ```
6. **Enable Scheduler Job** (unpause in Cloud Console or via gcloud).

### Rollback Steps
- **Cloud Run Service / Job**: `gcloud run services delete weaware-video-api --region=us-central1`, `gcloud run jobs delete weaware-video-job --region=us-central1`.
- **Cloud SQL**: The migration is purely additive. If rollback is desired:
  `DROP TABLE IF EXISTS video_runs CASCADE;`
- **Terraform**: `cd video/terraform && terraform destroy`.

---

## 8. Make.com Scenario Specification (Instagram Reels)

Match the existing Make.com pull pattern used for news stories:

```
[Schedule: Every 2 Hours]
          |
          v
[HTTP Module 1: Make a Request]
  - URL: https://weaware-video-api-...run.app/videos/next-approved
  - Method: GET
  - Headers:
      x-api-key: {{API_KEY}}
  - Handle 204: Ignore / Stop scenario
          |
          v
[Router / Filter]
  - Condition: 200 OK received with run_id
          |
          v
[Instagram for Business: Create a Reel]
  - Account: WeAware Main Account
  - Video URL: {{HTTP1.data.signed_video_url}}
  - Cover URL: {{HTTP1.data.signed_thumbnail_url}}
  - Caption: {{HTTP1.data.caption}} {{HTTP1.data.hashtags}}
          |
          v
[HTTP Module 2: Acknowledge Publication]
  - URL: https://weaware-video-api-...run.app/videos/{{HTTP1.data.run_id}}/mark-published
  - Method: POST
  - Headers:
      x-api-key: {{API_KEY}}
```

---

## 9. Go-Live Compliance Checklist

- [ ] **Meta Reels Content Constraints**:
  - Aspect Ratio: Exactly 9:16 (1080x1920).
  - Frame Rate: 30 fps.
  - Codec: H.264 video (`yuv420p`), AAC audio.
  - Video Length: 32 seconds (under Meta's 90-second Reel ceiling).
- [ ] **AI-Generated Labeling (Meta & EU AI Act Compliance)**:
  - Meta requires the "AI Info" label on photorealistic generative media.
  - SynthID watermark is embedded natively by Veo into the video stream.
  - Caption must retain the `satire_disclosure` line:
    *"AI-generated political satire grounded in verified multi-source news reporting."*
- [ ] **Copyright & Lower-Third Attribution**:
  - Strictly no copyrighted publisher agency photos (AP, Reuters, Getty).
  - Source attribution rendered as clean vector text in the lower-third.
