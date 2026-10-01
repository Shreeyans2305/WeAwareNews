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

### Official Model Retirement Calendar & Review Milestones

Sources:
- Official Lifecycle Documentation: [Cloud Model Versions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions)
- Official Vertex AI Pricing: [Vertex AI Pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing)

| Model ID | Endpoint Location | Status | Retirement / Cutoff Date | Switch / Review Date | Official Documentation Text Read | Source URL |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `gemini-2.5-flash` | `us-central1` | GA | **2026-10-20** | **2026-10-19** (Switch Date) | *"Discontinuation date: October 20, 2026"* | [Model Versions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions) |
| `gemini-2.5-pro` | `us-central1` | GA | **2026-10-20** | **2026-10-19** (Switch Date) | *"Discontinuation date: October 20, 2026"* | [Model Versions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions) |
| `gemini-3.8-flash` | `global` | GA | None announced *(conservative: 2028-01-01)* | **2027-01-01** (Promo Cutoff) | *"Promotional pricing available until December 31, 2026"* | [Vertex Pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing) |
| `gemini-3.5-flash` | `global` | GA | **2027-05-19 or later** | **2027-05-18** (Switch Date) | *"Discontinuation date: May 19, 2027 or later"* | [Model Versions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions) |
| `gemini-3.1-pro-preview` | `global` | Preview | **2027-05-28 or later** | Excluded | *"Discontinuation date: May 28, 2027 or later"* (Preview model; excluded while `ALLOW_PREVIEW_MODELS=false`) | [Model Versions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions) |
| `veo-3.1-fast-generate-001` | `us-central1` | GA | **2026-11-17 or later** | **2026-11-03** (Veo Review Date) | *"Discontinuation date: November 17, 2026 or later"* | [Model Versions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions) |
| `veo-3.1-generate-001` | `us-central1` | GA | **2026-11-17 or later** | **2026-11-03** (Veo Review Date) | *"Discontinuation date: November 17, 2026 or later"* | [Model Versions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions) |
| `gemini-2.5-flash-image` | `us-central1` | GA | **2027-03-15** | **2027-03-01** (Review Date) | *"Discontinuation date: March 15, 2027"* | [Model Versions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/model-versions) |

> [!IMPORTANT]
> **Veo Baseline Policy**: Baseline video generation is strictly locked to `veo-3.1-fast-generate-001` at 720p. The pipeline issues a lifecycle warning starting on the **Veo Review Date (2026-11-03)**; upgrading or switching Veo models requires explicit human review and approval.
> **Pro Role GA Policy**: On and after **2026-10-19**, no GA Pro models remain; the pipeline automatically falls back to the best available GA Flash model (`gemini-3.8-flash`), running the editor safety audit with stricter claim-by-claim verification and UI review flagging.

### Quotas to Request in Google Cloud Console
Under **IAM & Admin -> Quotas & System Limits** for `us-central1`:
- **Vertex AI Video Generation Requests per Minute**: Request at least `5 RPM` (allows parallel 4-clip generation).
- **Vertex AI Video Generation Seconds per Minute**: Request at least `60 seconds/min`.

---

## 4. Cost Caps & Spend Limits

### Tunables in `video/config/settings.py`
- `VEO_MODEL_TIER`: `fast` (default) or `standard`
- `VEO_RESOLUTION`: `720p` (frozen production baseline)
- `MAX_COST_USD_PER_RUN`: `$15.00`
- `MAX_RUNS_PER_DAY`: `4`
- `MAX_VEO_SECONDS_PER_DAY`: `250`

### Cost Breakdown per 32-Second Episode (4 clips × 8s @ 720p)

| Scenario | Fast Tier (`veo-3.1-fast-generate-001` @ $0.10/s) | Standard Tier (`veo-3.1-generate-001` @ $0.20/s) |
| :--- | :--- | :--- |
| **Base Run (32 seconds, 0 retries)** | **$3.20** | **$6.40** |
| **1 Safety Retry (40 seconds total)** | **$4.00** | **$8.00** |
| **Worst-Case (4 clips × 3 attempts = 96s)** | **$9.60** | **$19.20** *(capped at $15.00)* |

*Note: The pipeline checks remaining budget before every clip and aborts (`cost_cap_aborted`) if `MAX_COST_USD_PER_RUN` ($15.00) would be exceeded.*

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

## 7. Exact Deployment Order

Follow this sequence strictly when deploying:

1. **Cloud SQL Backup**:
   ```bash
   gcloud sql backups create --instance=weaware-pg --project=project-9ba21d45-1dfd-4108-b69 --description="Pre-video-runs migration"
   ```
2. **Database Migration**:
   Run via Cloud SQL Proxy: `video/migrations/001_create_video_runs.sql`.
3. **Build & Push Containers**:
   ```bash
   gcloud builds submit --config=video/cloudbuild.yaml .
   ```
4. **Terraform Apply**:
   ```bash
   cd video/terraform
   terraform apply -var="image_tag=<BUILD_ID>"
   ```
   *Creates GCS bucket, SAs, IAM, Pub/Sub, Cloud Run service & job, Workflows, secret versions, and paused Scheduler job.*
5. **Populate Real Make.com Webhook Secret**:
   Terraform initializes `video-webhook-url` with a placeholder. Update it with your live Make webhook URL:
   ```bash
   echo -n "<make webhook url>" | gcloud secrets versions add video-webhook-url --data-file=-
   ```
   *(Terraform includes `lifecycle { ignore_changes = [secret_data] }` to guarantee your live URL is never overwritten on subsequent terraform apply runs).*
6. **Send Test Webhook to Verify Make Scenario**:
   ```bash
   PYTHONPATH=. python -m video.pipeline.notifier --send-test
   ```
7. **Run Master Asset Bootstrap**:
   ```bash
   python video/bootstrap_assets.py --confirm
   ```
8. **Enable Scheduler Job** (unpause in Cloud Console or via gcloud).

### Rollback Steps
- **Cloud Run Service / Job**: `gcloud run services delete weaware-video-api --region=us-central1`, `gcloud run jobs delete weaware-video-job --region=us-central1`.
- **Cloud SQL**: The migration is purely additive. If rollback is desired:
  `DROP TABLE video_runs CASCADE;`
- **Terraform**: `cd video/terraform && terraform destroy`.

---

## 8. Make.com Scenarios Specification

Two independent Make.com scenarios handle the pipeline:

### Scenario A: Editor Review Notification (Push via Webhook)
A dedicated review scenario triggered as soon as a video episode is assembled:

```
[Module 1: Webhooks > Custom Webhook]
  - Path: Listens for POST from pipeline notifier
  - Security: Validates optional `x-weaware-signature` HMAC header
          |
          v
[Module 2: Flow Control > Router]
  - Branch 1: `event` = "ready_for_review"
  - Branch 2: `event` = "run_failed" OR "cost_cap_aborted"
  - Branch 3: `event` = "test" (for structure determination / testing)
          |
          +---> [Branch 1: Send Notification]
          |       - Notification Module (Email, Slack, Discord, or Telegram)
          |       - Content: Headline, Caption, Sources, Cost ($usd)
          |       - Media: Includes {{video_preview_url}} and {{thumbnail_url}}
          |       - Action Link: {{review_url}} (Single-use, 24h HMAC-secured review page)
          |
          +---> [Branch 2: Send Alert]
                  - Alert Module: Error message & run_id
```

> **Security Note on Review Link**: The review link contains a time-limited (24-hour expiration) HMAC-SHA256 signature and is single-use: once approved or rejected, the token is consumed in the database. Even if logged in Make.com execution history, the token cannot be reused after actioning.

---

### Scenario B: Instagram Reels Publication (Pull Poller)
Matches the existing scheduled WeAware news story publishing flow:

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
