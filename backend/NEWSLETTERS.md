# WeAware account newsletters

The newsletter settings screen is available to signed-in accounts. A valid Firebase ID token is required for preference reads and updates; the API uses the verified Firebase UID and verified email claim, never a browser-supplied UID or recipient address. Users must choose at least one currently published topic and explicitly consent. They can change cadence/topics or unsubscribe in their account. Every email also carries an unsubscribe link and `List-Unsubscribe` headers.

## Delivery behavior

- Preferences and delivery records are stored in Cloud SQL in `newsletter_preferences` and `newsletter_deliveries`; the API creates these tables additively at startup.
- The dispatcher includes up to eight published articles matching the selected topics since the previous successful delivery. First delivery looks back one day for daily subscribers and seven days for weekly subscribers. Empty periods do not generate an email, and the next interval is scheduled.
- Dispatch locks due preference rows with `FOR UPDATE SKIP LOCKED`, and a unique `(firebase_uid, window_start)` record prevents concurrent duplicate work. Failed records can be retried. A stable Resend idempotency key protects retries if the mail provider accepted a message but the API process failed before recording success. Resend retains these keys for 24 hours; retry within that window to preserve provider-side deduplication.
- Email API credentials are intentionally optional. Dispatch returns `status: disabled` without contacting Resend until all required mail and unsubscribe configuration is present.

## Resend and production setup

1. Create a Resend account, add the sending domain, and publish/verify the DNS records Resend provides. Use a sender such as `WeAware Briefing <briefing@news.example>` on that verified domain. The Resend onboarding `resend.dev` sender is for testing and is not a production sender.
2. Create a restricted Resend API key. Store it in Google Secret Manager as `resend-api-key`; never put it in `WEAWARE/.env.local`, source control, frontend config, or logs.
3. Create high-entropy independent secrets for `newsletter-unsubscribe-secret` (HMAC unsubscribe links) and `newsletter-dispatch-token` (Cloud Scheduler authentication). Store both in Secret Manager.
4. Configure the Cloud Run API with Secret Manager environment mappings for `RESEND_API_KEY`, `NEWSLETTER_UNSUBSCRIBE_SECRET`, and `NEWSLETTER_DISPATCH_TOKEN`. Configure ordinary environment variables `NEWSLETTER_FROM_EMAIL` to the verified sender and `NEWSLETTER_API_ORIGIN` to the HTTPS origin that serves this API (no trailing slash). The unsubscribe URL must be publicly reachable. Keep the existing Cloud SQL and Firebase API settings.
5. Create a Cloud Scheduler job to call `POST https://<api-origin>/api/v1/newsletters/dispatch` hourly. Add the `X-Newsletter-Dispatch-Token` header with the dispatch token, and restrict job administration to trusted operators. For example, after loading the token from Secret Manager into a protected deployment shell variable:

   ```sh
   gcloud scheduler jobs create http weaware-newsletter-dispatch \
     --location=<scheduler-region> \
     --schedule="0 * * * *" \
     --time-zone="Etc/UTC" \
     --uri="https://<api-origin>/api/v1/newsletters/dispatch" \
     --http-method=POST \
     --headers="X-Newsletter-Dispatch-Token=${NEWSLETTER_DISPATCH_TOKEN}"
   ```

   If the job already exists, use `gcloud scheduler jobs update http` with the same options and `--update-headers="X-Newsletter-Dispatch-Token=${NEWSLETTER_DISPATCH_TOKEN}"`. Do not paste actual tokens into command history or shared logs.

Without the Resend key, verified sender, unsubscribe secret, API origin, or dispatch token, the dispatcher does not send. Configure and deploy these values before expecting emails. User preference collection works separately once the API version with newsletter endpoints is deployed.

## API

- `GET /api/v1/newsletters/preferences` — Firebase bearer token; return the signed-in user's own preferences.
- `PUT /api/v1/newsletters/preferences` — Firebase bearer token; accepts `{ "topics": ["World"], "cadence": "daily|weekly", "consent": true }`.
- `POST /api/v1/newsletters/preferences/unsubscribe` — Firebase bearer token; unsubscribe the signed-in account.
- `GET|POST /api/v1/newsletters/unsubscribe?token=...` — signed HMAC unsubscribe link for an email recipient; no account session is required.
- `POST /api/v1/newsletters/dispatch` — scheduler only; requires `X-Newsletter-Dispatch-Token`.

Resend setup instructions: [Resend domains](https://resend.com/docs/dashboard/domains/introduction) and [idempotency keys](https://resend.com/docs/dashboard/emails/idempotency-keys).
