# WeAware audio publishing

This adds cached article narration and reviewed, scripted podcast episodes. The API creates `audio_assets` and `podcast_episodes` on startup; audio bytes live in Cloud Storage, never in Postgres.

## Google Cloud resources

The Terraform in [`../terraform/audio`](../terraform/audio) provisions the two audio buckets, a Cloud Tasks queue, a task identity, required API enablement, and the bucket/queue IAM bindings. It expects the existing API service account and deployed API URL as inputs. Review the plan before applying it:

```sh
cd backend/terraform/audio
terraform init
terraform plan -var='project_id=weaware' \
  -var='api_service_account_email=YOUR_API_RUNTIME_SERVICE_ACCOUNT' \
  -var='api_service_url=https://YOUR_API.run.app'
```

The podcast bucket is public because RSS clients need stable, unauthenticated enclosure URLs. The article bucket blocks public access; the API returns short-lived signed links. If organization policy disallows public buckets, the RSS feed needs a custom media domain or another public media origin before podcast apps can play episodes.

After applying Terraform, set these environment variables on the existing API Cloud Run service using the Terraform outputs:

- `ARTICLE_AUDIO_BUCKET`
- `PODCAST_AUDIO_BUCKET`
- `PODCAST_AUDIO_PUBLIC_ORIGIN`
- `AUDIO_TASKS_LOCATION` (the queue region, normally `us-central1`)
- `AUDIO_TASKS_QUEUE`
- `AUDIO_TASKS_SERVICE_ACCOUNT`
- `AUDIO_TASKS_WORKER_URL` (the existing API service URL)
- `AUDIO_TASKS_AUDIENCE` (the same API URL unless a custom audience is configured)
- `AUDIO_TTS_VOICE` (defaults to `en-US-Neural2-D`)
- `AUDIO_TTS_MONTHLY_CHARACTER_LIMIT` (defaults to 1,000,000 characters)

The API runtime identity also needs the existing Cloud SQL and Secret Manager permissions. Terraform adds storage object access, Cloud Tasks enqueue permission, and signing permissions. The task route verifies the OIDC token and exact configured service account before it synthesizes anything. Do not expose service account credentials in the frontend.

Terraform creates the `podcast-editorial-api-key` Secret Manager secret and grants the API runtime account access. Add a strong secret version before using editorial endpoints. Those endpoints use a dedicated `X-Podcast-Editorial-Key`; they do not reuse the Make/API automation key.

Deploy the updated `backend` API image after setting the environment. Cloud SQL schema updates are additive and run during API startup. Terraform does not deploy application code or change the Cloud Run service revision.

## Editorial workflow

The daily Cloud Build pipeline now creates a **draft** script from the latest three published articles after article generation. It records source URLs and model usage cost. It uses the existing Vertex AI project/model settings and spend guard. Drafts never enter the public episode list or RSS feed automatically.

An editor reviews the draft and calls the internal API with `X-Podcast-Editorial-Key`:

- `GET /api/v1/podcasts/episodes/{episode_id}/draft` returns the script and source URLs for review.
- `POST /api/v1/podcasts/episodes/{episode_id}/approve` approves the script and queues synthesis.
- The episode appears in `GET /api/v1/podcasts/episodes` and `/podcasts/feed.xml` only after audio generation succeeds.
- If a generation fails, approve the same episode again to retry; its script remains unchanged.

Draft creation can also be performed with `POST /api/v1/podcasts/episodes` using that key. This is intended for trusted editorial automation, not browser calls.

## Runtime behavior and cost controls

- Article audio is generated when a listener requests it. Existing media is reused by a hash of narration text and voice. Source text edits create a new version.
- A Postgres advisory lock reserves monthly character capacity before queuing work. Failed and retried syntheses are conservatively counted in a dedicated monthly usage row, including retries that cross a month boundary.
- The limit is project-wide across article and podcast synthesis. Retried syntheses consume the character budget again. Set it to `0` only if an unlimited cap is intentional.
- Cloud Tasks retries transient worker failures. The content hash and deterministic task name make duplicate requests safe; a completed GCS object is reused if the database update failed after synthesis. Text is split below the synchronous Cloud TTS request limit and MP3 frames are joined into one cached file.
- Podcast audio URLs must remain stable for RSS clients. Article URLs are signed for seven days, so a listener can finish long-form audio without link expiry during playback.
- Generated audio is currently MP3 and estimated duration is based on script word count. The browser player uses the actual media duration when it loads.

## API behavior

- `POST /api/v1/articles/{id}/audio` requests generation and returns its status.
- `GET /api/v1/articles/{id}/audio` returns `not_requested`, `queued`, `running`, `ready`, or `failed` and a signed URL when ready.
- `GET /api/v1/podcasts/episodes` returns published, playable episodes and source URLs.
- `GET /podcasts/feed.xml` returns only published, playable episodes with public media enclosures and source notes.

Audio generation has a monthly character cap, but the API still accepts public requests for published article audio. For stricter abuse prevention, add authenticated listener quotas or pre-generate a bounded set of articles at publication before relaxing the default cap.
