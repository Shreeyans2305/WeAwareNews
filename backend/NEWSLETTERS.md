# WeAware account newsletters

The newsletter settings screen is available to signed-in accounts. The website requires a verified email before it submits a subscription, and the API requires a valid Firebase ID token for preference reads and updates. The API scopes preferences to the Firebase UID and takes the recipient address from the token's email claim, never from a browser-supplied UID or recipient address. The API independently rejects tokens whose `email_verified` claim is false. Users must choose at least one currently published topic and explicitly consent. They can change cadence/topics or unsubscribe in their account. Every email also carries an unsubscribe link and `List-Unsubscribe` headers.

## Delivery behavior

- Preferences and delivery records are stored in Cloud SQL in `newsletter_preferences` and `newsletter_deliveries`; the API creates these tables additively at startup.
- The dispatcher includes up to eight published articles matching the selected topics since the previous successful delivery. First delivery looks back one day for daily subscribers and seven days for weekly subscribers. Empty periods do not generate an email, and the next interval is scheduled.
- Dispatch locks due preference rows with `FOR UPDATE SKIP LOCKED`, and a unique `(firebase_uid, window_start)` record prevents concurrent duplicate work. Failed records can be retried. A stable Message-ID aids tracing; SMTP retries after ambiguous failures can produce duplicates.
- Email API credentials are intentionally optional. Dispatch returns `status: disabled` without contacting Gmail until all required mail and unsubscribe configuration is present.

## Gmail production setup

The service sends through Gmail SMTP over verified TLS on port 465. No custom domain or Resend account is needed. The sending Gmail account can differ from the Google Cloud account.

- Set `NEWSLETTER_SMTP_USER` to the sender Gmail address and `NEWSLETTER_FROM_EMAIL` to its display sender.
- Store a Google app password belonging to that sender in Secret Manager as `newsletter-smtp-password`; map it to `NEWSLETTER_SMTP_PASSWORD`. Never use the regular Google password or place this value in frontend configuration.
- Map `newsletter-unsubscribe-secret` and `newsletter-dispatch-token` to `NEWSLETTER_UNSUBSCRIBE_SECRET` and `NEWSLETTER_DISPATCH_TOKEN`.
- Set `NEWSLETTER_API_ORIGIN` to the publicly reachable HTTPS API origin.
- The hourly Cloud Scheduler job `weaware-newsletter-dispatch` calls the dispatch endpoint with `X-Newsletter-Dispatch-Token`.

Gmail sending limits apply, so this configuration is intended for a small subscriber list. SMTP acceptance does not prove inbox placement. SMTP also has no provider idempotency guarantee: a stable Message-ID aids tracing but retries after a connection or commit failure can produce duplicates.

## API

- `GET /api/v1/newsletters/preferences` — Firebase bearer token; return the signed-in user's own preferences.
- `PUT /api/v1/newsletters/preferences` — Firebase bearer token; accepts `{ "topics": ["World"], "cadence": "daily|weekly", "consent": true }`.
- `POST /api/v1/newsletters/preferences/unsubscribe` — Firebase bearer token; unsubscribe the signed-in account.
- `GET|POST /api/v1/newsletters/unsubscribe?token=...` — signed HMAC unsubscribe link for an email recipient; no account session is required.
- `POST /api/v1/newsletters/dispatch` — scheduler only; requires `X-Newsletter-Dispatch-Token`.

Google app password setup: https://support.google.com/accounts/answer/185833.

## Delivery verification and multiple recipients

The preferences response includes `deliveryReady`, which checks the required provider, unsubscribe, origin, and scheduler-token settings. This confirms configuration presence, not domain verification, scheduler installation, or inbox delivery. The account page shows a warning when these settings are missing.

After subscribing, use **Send test email** (`POST /api/v1/newsletters/test`, Firebase bearer token). This sends a real delivery-check message to the verified account address. Provider acceptance is reported honestly; check the inbox and spam folder to verify receipt. Repeated clicks send additional tests; SMTP does not guarantee deduplication. The test does not advance the scheduled briefing or change its topics.

Multiple people are supported as independent subscribers: each person signs in, verifies their address, selects daily or weekly, and consents. The dispatcher sends a private message per subscriber, with their own topics and unsubscribe link. Dispatch processes at most 100 due subscribers per request; schedule additional runs for larger lists. For a team wanting one shared destination, a mailing-list address can be used as its verified account email; list membership is managed by that group's mail administrator. Arbitrary recipient lists are not accepted by the public subscription endpoint.

Local transport verification: `python3 -m unittest backend/tests/test_newsletter_delivery.py`. This mocks provider calls and does not prove production delivery.

## Crosscheck email design and placement investigation (2026-10-28)

Scheduled briefings use `api/newsletter.py` for an email-safe version of the website's newspaper design: paper background, Georgia serif masthead/headlines, double rule, lead image and opening paragraphs, consensus stamps, source attribution, and flagged claims. HTML and plain text share article content. It uses presentation tables, inline styles, no JavaScript, no remote fonts, and no tracking pixels. Browser previews were checked at 780px and 390px with no horizontal mobile overflow. Email-client appearance may vary.

A controlled check to the requested recipient found that a plain-text message with no links or attachments arrived in Inbox, while both the earlier digest and the redesigned Crosscheck arrived in Spam. The earlier newsletter passed SPF, DKIM, and DMARC. This demonstrates that authenticated transport works but does not isolate Gmail's classification cause. Content, linked domains, remote images, sender reputation, and recipient history remain possible factors; Gmail's API provides labels and headers, not the private spam score. Do not claim that styling or authentication alone fixes spam, or silently mark messages Not Spam during delivery tests. Keep attribution, consent, and unsubscribe features intact.

Marking a message Not Spam applies to the receiving mailbox; it does not establish inbox placement for other subscribers. Further production checks must use real opt-in recipients, with low sending volume and no repeated diagnostic blasts. Current inbox placement remains unresolved.

## Follow-up link/image comparisons (2026-10-28)

At the recipient's explicit request, one-off newspaper variants were compared in the same mailbox. Initial observations: no external URLs = Inbox; source links alone = Inbox; lead image alone = Inbox; unsubscribe URL alone = Inbox; complete HTML with and without List-Unsubscribe headers = Spam; all images without links = Inbox; all links without images = Inbox. These checks do not establish a single blocked domain. Subjects and delivery times differ, Gmail classification is adaptive, and results are observational.

The latest full illustrated edition (subject suffix `ab3361`) arrived with INBOX and CATEGORY_UPDATES labels, not SPAM. The preceding full edition (`5ff1a1`), initially observed in Spam, also had INBOX on the later read. This change prevents attributing improvement conclusively to template edits alone. No spam labels or filters were changed by the tests.

The production renderer now includes an image for every article with an available safe image URL. One NDTV image returned HTTP 403. `api/newsletter_images.json` replaces that exact URL with The Hindu's open-graph image from the same story's already-cited source coverage and includes a credit. All six preview images loaded in browser verification. The plain-text alternative retains source outlet names and stances instead of duplicating every long article URL; HTML retains clickable original source links. The unsubscribe URL remains in both alternatives. Newspaper layout is unchanged. Eight template/transport tests pass.

This confirms inbox placement for the final requested test, not guaranteed placement for future subscribers. Do not blacklist sources or remove unsubscribe based on these comparisons.

## Automatic subscriber delivery and subjects

All subscribed, verified website accounts use the shared illustrated `api/newsletter.py` renderer for scheduled delivery, filtered by their saved topics. Images are included for every article with an available safe image URL, with the documented credited replacement for the known blocked source image. No separate opt-in is needed for the illustrated design.

Subjects are generated by `newsletter_subject` in Asia/Kolkata time, with English ordinal dates and the saved frequency, for example `The Crosscheck 28th October 2026 | Daily Newsletter` or `The Crosscheck 28th October 2026 | Weekly Newsletter`. They do not contain edition or test suffixes. The account's Send test email action also renders the same newsletter using saved topics and cadence, without advancing the scheduled delivery.

The hourly scheduler selects due, subscribed accounts. The first newsletter becomes due one day (daily) or seven days (weekly) after saving the subscription, and the hourly job sends when due; there is no fixed 7am or Friday promise. Periods without newly published matching stories are skipped and the next interval is scheduled. A successful delivery advances the next due date by one or seven days. Failures remain due for retry. Website subscriptions require verified email and explicit consent; unsubscribed accounts are excluded.

Verification: `python3 -m unittest backend/tests/test_newsletter_schedule.py backend/tests/test_newsletter_template.py backend/tests/test_newsletter_delivery.py`. Tests cover ordinal dates, timezone rollover, daily/weekly dispatch, topic query parameters, the illustrated renderer, no-news periods, and mail transport.
