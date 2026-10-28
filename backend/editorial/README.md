# Article publishing and editorial services

The daily ingestion build runs `python -m editorial.pipeline` after syncing clustered coverage to PostgreSQL. The article pipeline selects stories with independent corroboration and usable source text, then uses Vertex AI for evidence extraction, cross-source review, drafting, and a final editorial review. Only approved drafts are published to `editorial_articles`; failed or rejected drafts remain unpublished for review or retry. Source URL fingerprints help avoid publishing a duplicate after reclustering.

The pipeline uses Application Default Credentials and the existing Cloud SQL connection. Its service account needs Vertex AI model invocation access and access to the existing `db-password` Secret Manager secret. Configure `WEAWARE_GEMINI_MODEL` (default `gemini-2.5-flash`), `WEAWARE_ARTICLE_BATCH_SIZE` (default `20`), and optionally `WEAWARE_ARTICLE_MIN_SOURCES` / `WEAWARE_ARTICLE_MIN_TEXT_SOURCES` on the Cloud Build trigger.

## Public article API

- `GET /api/v1/articles?topic=AI&q=climate&limit=24&offset=0`
- `GET /api/v1/articles/{article_id}`
- `GET /api/v1/topics`

These endpoints expose published articles and source notes without the automation API key. Set `VITE_API_BASE_URL` at frontend build time if the API is not same-origin. Set `WEAWARE_ALLOWED_ORIGINS` on the API service to the website origin (comma-separated for previews). The Vite development server proxies `/api` to `http://localhost:8080` by default.

## Related services

- User authentication and account access: Firebase ID tokens verified by the API; see [`../../WEAWARE/AUTH_SETUP.md`](../../WEAWARE/AUTH_SETUP.md).
- Topic-based email subscriptions: [`../NEWSLETTERS.md`](../NEWSLETTERS.md).
- Article narration, podcast drafts, editorial approval, and RSS: [`../audio/README.md`](../audio/README.md).

Article drafting and review use AI and can miss factual errors. Publication review is not a guarantee of completeness or truth; the website keeps links to original reporting available to readers.
