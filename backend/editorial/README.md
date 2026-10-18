# Article publishing pipeline

The ingestion Cloud Build now runs `python -m editorial.pipeline` after its Postgres sync. The job selects corroborated clusters with source text, then runs four independent Gemini stages through Vertex AI: evidence extraction, cross-source review, article drafting, and final editorial review. Only approved drafts are published to `editorial_articles`; failures remain recorded for a later retry. Source URL fingerprints prevent a reclustered copy of already published coverage from being published again.

The pipeline uses Application Default Credentials and the existing Cloud SQL proxy. Its service account needs Vertex AI model invocation access and access to the existing `db-password` Secret Manager secret. Configure `WEAWARE_GEMINI_MODEL` (default `gemini-2.5-flash`), `WEAWARE_ARTICLE_BATCH_SIZE` (default `20`), and optionally `WEAWARE_ARTICLE_MIN_SOURCES` / `WEAWARE_ARTICLE_MIN_TEXT_SOURCES` in the Cloud Build trigger.

The read-only public website API is:

- `GET /api/v1/articles?topic=AI&q=climate&limit=24&offset=0`
- `GET /api/v1/articles/{article_id}`
- `GET /api/v1/topics`

Set `VITE_API_BASE_URL` at frontend build time to the Cloud Run API origin. Set `WEAWARE_ALLOWED_ORIGINS` on the API service to the deployed WEAWARE origin (comma-separated for previews). The Vite development server proxies `/api` to `http://localhost:8080` by default. These public reads do not use the automation API key.

The website newsletter subscriptions and podcast/audio playback still use their existing demo flows; article lists shown in those views now come from the public article API.
