# WeAware project handoff

This repository contains the WeAware news reading site, collection and editorial APIs, newsletter and audio services, and a separate human-reviewed vertical-video workflow. This document is a current system map, not a deployment authorization. Follow each service guide and the active task instructions before running paid jobs, applying infrastructure, enabling schedules, approving content, or publishing.

## Product and editorial principles

WeAware helps readers compare coverage of the same story and follow links to original reporting. A source count or agreement signal is descriptive; it is not a truth score. AI is used for organization, summarization, drafting, and media generation. Automated checks can miss errors, so important claims should be checked against the linked coverage.

Article publication and podcast episodes have editorial review steps. Vertical video scripts are designed for neutral, attributed reporting and receive an editorial check before generation. Completed video is held for human review; approval is separate from publishing.

## System map

- `WEAWARE/` — React/Vite app with home, feed, article reader, newsletters, podcasts/audio, authentication, and About views.
- `backend/ingestion/` — RSS/API/curated-source polling, normalization, deduplication, story clustering, and extraction.
- `backend/editorial/` — evidence extraction, cross-source review, article drafting, and publication review.
- `backend/api/` — FastAPI service for public articles and topics, authenticated accounts, newsletter preferences, audio, podcast, and internal editorial endpoints.
- `backend/audio/` and `backend/terraform/` — audio generation, podcast editorial workflow, RSS, and supporting Cloud resources.
- `video/` — separate story selection, script/editor gates, Veo generation, FFmpeg processing, and human review API.

## Current user-facing features

- Public article feed with topic and text filtering and linked source reporting.
- Guest preview of three stories; signed-in users can load the larger feed.
- Firebase email/password and Google sign-in; API verifies Firebase ID tokens for protected user actions.
- The Crosscheck newsletter preferences with verified email, explicit consent, topic selection, daily/weekly cadence, and unsubscribe.
- Cached AI narration for published articles and published podcast episodes with a public RSS feed.
- An About page explaining how WeAware compares coverage, the limits of agreement signals, and reading/listening options.

## Operational references

- Start here: [README.md](README.md)
- Website and local setup: [WEAWARE/README.md](WEAWARE/README.md)
- Firebase setup: [WEAWARE/AUTH_SETUP.md](WEAWARE/AUTH_SETUP.md)
- Collection: [backend/ingestion/README.md](backend/ingestion/README.md)
- Article publishing: [backend/editorial/README.md](backend/editorial/README.md)
- Newsletter delivery: [backend/NEWSLETTERS.md](backend/NEWSLETTERS.md)
- Audio and podcasts: [backend/audio/README.md](backend/audio/README.md)
- Video workflow: [video/README.md](video/README.md)
- Architecture decisions and limitations: [DECISIONS.md](DECISIONS.md)

Do not put production secrets in code, command output, documentation, or frontend environment variables. Keep external delivery, scheduling, paid generation, approval, and publishing behind their documented operational controls.
