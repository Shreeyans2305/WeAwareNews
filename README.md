# WeAware

WeAware is a multi-source news reading product. It groups coverage around stories, links back to original reporting, and makes agreement, differences, and uncertainty easier to inspect. Summaries and automated signals are reading aids; they do not establish truth or replace editorial judgment.

## Product

- **News feed:** Browse published articles by topic, search, and open source notes and original reporting links.
- **The Crosscheck:** Choose topics and daily or weekly email delivery after signing in and verifying an email address. Subscribers can manage preferences or unsubscribe.
- **Audio and podcasts:** Request cached narration for published articles and play reviewed podcast episodes. Podcast episodes are exposed through a public RSS feed after editorial approval and audio generation.
- **Accounts:** Firebase Authentication supports email/password and Google sign-in. Guests can preview three stories and browse a limited feed; sign-in unlocks the larger feed and account features.
- **Video:** A separate pipeline produces neutral, source-grounded vertical news videos. Generated episodes require human review before approval; publishing is a separate integration.

## Repository map

| Path | Purpose |
| --- | --- |
| [`WEAWARE/`](WEAWARE/README.md) | React + Vite website |
| [`mobile/`](mobile/README.md) | Flutter Android and native SwiftUI iOS applications |
| [`backend/ingestion/`](backend/ingestion/README.md) | Feed polling, normalization, clustering, and extraction |
| [`backend/editorial/`](backend/editorial/README.md) | Article drafting and editorial review pipeline |
| [`backend/audio/`](backend/audio/README.md) | Article audio, podcast workflow, and audio infrastructure |
| [`backend/NEWSLETTERS.md`](backend/NEWSLETTERS.md) | Newsletter preferences and delivery operations |
| [`video/`](video/README.md) | Neutral vertical video workflow and review API |
| [`DECISIONS.md`](DECISIONS.md) | Architecture decisions and known limitations |
| [`HANDOFF.md`](HANDOFF.md) | Current system map and operational handoff |

## Local website development

```sh
cd WEAWARE
npm install
npm run dev
```

The Vite server proxies `/api` to `http://localhost:8080` unless configured otherwise. Create `WEAWARE/.env.local` from `.env.example` to configure the API origin and Firebase web-app identifiers. See [`WEAWARE/AUTH_SETUP.md`](WEAWARE/AUTH_SETUP.md) for Firebase and deployment configuration.

Create a production bundle with:

```sh
cd WEAWARE
npm run build
```

## API and data flow

The FastAPI service in `backend/api/` serves published articles and topics, verifies Firebase ID tokens for user-specific endpoints, and provides newsletter, article-audio, podcast, and editorial routes. PostgreSQL stores editorial and account metadata; generated audio is stored in Cloud Storage. News collection, reviewed article publishing, newsletter delivery, audio generation, and vertical video use separate jobs or queues. See each service README before running or deploying an operational workflow.

## Editorial and AI disclosure

WeAware uses AI to help cluster coverage, draft and summarize articles, and synthesize audio or video. Article publication uses an editorial review gate; podcast scripts require editor approval before audio generation. Video episodes have a separate human review and approval flow. Automated review can miss errors; open the linked reporting for important claims. Generated audio and video should be identified as AI-generated in their playback or publication context.

Do not commit credentials, Firebase service-account keys, API tokens, or production database connection strings. Store deployment secrets in Secret Manager and follow the service-specific operational docs.
