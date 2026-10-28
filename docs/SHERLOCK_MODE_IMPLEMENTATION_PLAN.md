# Sherlock Mode — implementation plan

Date: 28 October 2026. Status: proposal; no infrastructure, paid calls, billing, or delivery enabled.

## Product decision

Sherlock Mode is a paid-subscriber research desk staffed by **Journalist Jeff**, an explicitly identified AI research assistant. A subscriber submits a question about a topic, happening, or event and receives a private, source-linked research brief in their WeAware account. Target delivery: within 24 hours during the pilot, with a visible estimate rather than a guaranteed deadline.

Promise broad, evidence-led research across accessible sources, never “all information” or guaranteed completeness. Jeff must distinguish established facts, attributed claims, conflicting accounts, and unanswered questions. The service researches public information; it does not conduct interviews or access private records.

**Recommended first version:** website delivery, invite-only testers, manually granted time-limited entitlements, one research depth, and limited credits. Build the paid-access boundary from day one; add actual recurring checkout before opening to paying customers. Email is an optional “your report is ready” link after the website flow works.

Website-first avoids new mail setup and delivery debugging. It is a lower-complexity pilot choice, not a measured guarantee of lower provider charges. Waiting until tomorrow does not itself reduce research costs: bounded work, caching, and batching do. Run the job promptly when capacity permits and show it when ready; never keep a process alive waiting for a day.

## Existing foundation and gaps

Repository inspection found React/Vite, Firebase Authentication, FastAPI, PostgreSQL/Cloud SQL, Vertex AI editorial generation, Cloud Run infrastructure, authenticated audio-task patterns, and optional Resend newsletter delivery. No paid-subscription integration was found in the inspected application paths.

Reuse authentication, database access, source normalization/extraction where suitable, and evidence-review concepts. Create a separate private research workflow: existing article generation publishes into a public feed and must not accidentally expose subscriber prompts or reports. Existing feeds are useful context but cannot cover arbitrary user questions; external web discovery is a new capability.

The newsletter guide records a server-side verified-email gap. Enforce verified email on Sherlock requests and optional report notifications independently of frontend checks. Model defaults also differ between editorial documentation and code; verify available model IDs and deployed configuration before implementation.

## Subscriber experience

1. Open Sherlock Mode. Signed-out readers see sign-in; non-entitled accounts see the paid feature description; entitled users see remaining credits.
2. Enter a question, optional geography and date range, and optional public reference URLs. Show examples and a short privacy notice. Limit question length and reference count.
3. Confirm the interpreted scope and one-credit cost. Avoid an extra model call for this screen: use validated form fields. Broad questions receive a narrower suggested scope before queueing.
4. Receive a request page with status, submission time, estimated completion, and cancellation while queued.
5. Find completed briefs in “My investigations.” Refresh status only while a request is active; there is no need for live token streaming.
6. Read a 800–1,500-word brief, sources, research cutoff, limitations, and feedback controls. Provide a concise partial report when evidence is insufficient.

Report sections: direct answer; key findings with claim-level citations; background/timeline when relevant; competing explanations; what remains unknown; annotated source list; research timestamp and AI disclosure. Cite publication dates and event dates separately. Identify primary material and syndicated copies.

Exclude chat, unlimited follow-ups, attachments, audio, PDF export, public sharing, continuous monitoring, and custom research depths from the first release. A fresh follow-up is a new credited request.

## Execution architecture

React → authenticated FastAPI → PostgreSQL request queue → scheduled Cloud Run Job → search/fetch/evidence/review pipeline → private report → optional notification.

Use one scheduled worker job for the pilot, initially every hour, with one worker and a small maximum batch. This avoids introducing an additional queue service immediately. A job claims queued rows with `FOR UPDATE SKIP LOCKED`, commits a lease, then releases the database connection before network/model work. Persist each stage so interruption resumes from checkpoints. Never perform the investigation inside the submission HTTP request or rely on an in-process background task surviving a Cloud Run restart.

Use a dedicated restricted service account, limited database connections, configured job timeout, bounded job retries, per-request deadline, and feature/spend kill switches. Keep dispatch frequency and processing capacity compatible with the 24-hour target. Later, switch to per-request task dispatch if demand requires it; do not operate two independent dispatch mechanisms without shared leases and idempotency.

## Jeff's research workflow

1. **Scope and triage:** validate question/date/geography, detect requests needing clarification, and establish a question outline. Reject prohibited private-data investigations or unsafe requests before spending a credit.
2. **Discover:** search WeAware coverage and a configurable external search adapter. Select the external provider after a small relevance/cost benchmark; support one provider initially. Start with at most six searches, including primary-source and contradictory-evidence searches.
3. **Retrieve:** inspect at most 15 candidate URLs and retain approximately 6–10 useful sources where available. Prefer official records, original reporting, research, and subject expertise. Deduplicate syndicated coverage. Never pad source counts when relevant evidence is scarce.
4. **Extract evidence:** store bounded text excerpts, dates, provenance, and structured claims. Search snippets are leads; do not present them as verification of inaccessible full-text claims. Mark unavailable/paywalled sources and use accessible alternatives without bypassing restrictions.
5. **Build evidence map:** link each important claim to supporting and conflicting passages. Count independent origins rather than domains alone. Single authoritative primary-source facts may be reported with clear attribution; disputed allegations need stronger corroboration.
6. **Draft:** generate the brief only from collected evidence, preserving uncertainty and avoiding unsupported accusations. A thin evidence base produces a limited result, not invented completeness.
7. **Review:** check citation existence, citation-to-claim support, dates, contradictions, and unsupported assertions. Use deterministic checks plus a separate review pass; this is still automated review, not independent human verification. Allow one bounded repair pass.
8. **Deliver:** persist a versioned result, mark complete atomically, and optionally queue a notification. Delivery retries never rerun research.

Initial pilot reports pass an administrator review before delivery. Track review effort separately from infrastructure spend. Later permit automatic delivery only after the quality benchmark passes; sensitive allegations and flagged failures stay in review. Private reports never become public articles automatically.

## Data and API contracts

Use explicit, versioned migrations and indexes. Suggested tables:

| Table | Purpose |
| --- | --- |
| `subscriber_entitlements` | Firebase UID, entitlement source, status, validity period, billing identifiers |
| `research_requests` | Owner UID, validated scope, status/stage, timestamps, due time, cancellation, lease, attempts, error code, budget and usage |
| `research_sources` | Request ID, canonical URL, origin, title, dates, fetch status, content hash, bounded evidence and provenance |
| `research_reports` | Request ID, version, structured report, citation mapping, cutoff, review state and decision |
| `research_credit_ledger` | Unique request-linked reservations, consumption, release/refund, billing period |
| `research_usage_ledger` | Reserved and actual model/search/fetch usage, provider IDs, stage, retry and ambiguous-call allowances |
| `research_notifications` | Request/channel, delivery state, attempts, stable idempotency key |
| `billing_events` | Deduplicated provider event IDs and processing state, added with billing |

Statuses: `queued → researching → verifying → awaiting_review → completed`; terminal alternatives `cancelled`, `failed`, `insufficient_evidence`. Keep processing stage separate from overall status. Store partial evidence so an approved limited report can be delivered for `insufficient_evidence`.

Proposed user endpoints:

- `GET /api/v1/sherlock/entitlement` — eligibility, remaining credits, reset date.
- `POST /api/v1/sherlock/requests` — validate entitlement, reserve credit and enqueue atomically; require client idempotency key; return 202 and request ID.
- `GET /api/v1/sherlock/requests` — own paginated history.
- `GET /api/v1/sherlock/requests/{id}` — own status and approved result.
- `POST /api/v1/sherlock/requests/{id}/cancel` — queued requests only; release reservation atomically.
- `POST /api/v1/sherlock/requests/{id}/feedback` — usefulness and issue categories.

Every read, mutation, and citation/evidence lookup enforces ownership in the database query. Return 404 for another user's request. Administrator review uses separate authorization and audit records. Clients cannot choose UID, entitlement, cost ceiling, review state, or notification recipient.

## Paid access and credits

Pilot defaults: three requests per tester per month, one active request per account, no rollover, no automatic top-ups. These are proposed experiment settings, not an announced commercial plan.

Check current entitlement and reserve credit in the same database transaction as request creation. Duplicate submissions return the existing request without another debit. Consume the credit after approved delivery. Release it for queued cancellation, technical failure, or a report with insufficient evidence; make refunds idempotent. An accepted request may finish after subscription expiry, and users retain access to their delivered reports. New requests require current entitlement.

For actual paid launch, select a recurring-payment provider compatible with the business entity and target market. Implement hosted checkout, customer self-service, signed and replay-safe webhooks, event deduplication, reconciliation, and explicit policies for renewal, failed payment, refunds, and cancellation at period end. Never grant access based on the checkout return URL. Time-limited administrator grants remain an audited pilot tool.

## Cost controls and experiment

Keep delivery and research budgets separate. The repository's historical Gemini test log is not current Sherlock pricing or a reliable per-report estimate.

Proposed initial test envelope: **20 investigations with a $10 tracked variable-spend ceiling**, maximum **$0.50 reserved per investigation**, including retries. These are control targets, not estimates or guaranteed achievable prices. Before enabling paid calls, confirm provider rates and whether a useful report fits the envelope; lower scope or revise the experiment if needed. Existing cloud infrastructure, build costs, billing fees, taxes, and human review are outside this tracked ceiling and must be measured separately.

Controls:

- Reserve a conservative upper bound before each paid operation; reject it if request or experiment funds are insufficient. Reconcile against usage afterward.
- Bound searches, fetched pages, page size, model input/output, review/repair calls, retry count, runtime, and worker concurrency. Enforce every limit in code.
- Retain conservative reserves for timed-out calls whose provider usage is unknown. Retry only after considering duplicate charges; a database retry must not blindly repeat a model call.
- Cache public-source extraction by canonical URL/content hash and freshness. Do not share private prompts, reports, or personalized evidence across users. Skip full-report caching initially.
- Stop when new retrieval produces no material evidence. Use a configurable economical model for extraction/drafting and evaluate quality before changing models.
- Record per-report search, model, compute, retry, and review costs. Provider billing alerts supplement application limits; they do not enforce an invoice-wide cap.

Website delivery has no additional email-provider charge. Optional Resend notifications reuse the existing provider abstraction, but remain distinct transactional research notifications with separate preferences; newsletter consent does not imply Sherlock email consent. Use a verified token email, escape content, include only a generic completion link, and require sign-in to read. Email failure must not affect report availability or credits.

## Security, privacy, and reliability

Treat retrieved pages as untrusted data: ignore embedded instructions, give the model no credentials, and allow only bounded research tools. URL retrieval must block private/link-local/metadata addresses, restrict protocols and ports, revalidate redirects and DNS destinations, and enforce content/time limits. Do not allow arbitrary file reads or authenticated browsing.

Keep investigations private and exclude prompt/report bodies from routine logs. Render structured reports safely; sanitize any Markdown/HTML and validate citation URLs. Define deletion and retention before beta: proposed 30-day raw-evidence retention, reports retained until user deletion or account policy expiry, with backup-retention limits disclosed. Keep only the minimum billing/audit records required separately.

Leases need expiry, heartbeat, and fencing/version checks so stale workers cannot overwrite a resumed request. Use bounded exponential backoff for transient failures and checkpointed retries. Keep database transactions short. A recovery sweep handles abandoned leases and overdue requests; show delays honestly. Expose queue age, completion rate, stage failures, citation failures, spend, and review backlog to administrators.

## Build sequence and acceptance gates

1. **Foundation and mocked flow (1–2 engineering days):** schema, Firebase/entitlement checks, atomic credits, request/history/report UI, fake worker and fixtures. Gate: duplicate submit costs one credit; another user's report is inaccessible; all failure/cancellation paths settle credits once.
2. **Bounded research worker (2–4 days):** search adapter benchmark, safe fetcher, evidence map, drafting/review, checkpoints and usage ledger. Gate: complete a small fixture-backed investigation; restart/retry does not duplicate output or violate budgets; malicious pages cannot redirect the agent or reach internal URLs.
3. **Invite-only quality pilot (1–2 days plus review time):** administrator grants/review, feature flags, operational dashboard and 20-question evaluation set. Include breaking news, historical events, broad questions, disputed claims, scarce evidence, inaccessible pages and duplicate coverage. Gate: every delivered report has traceable citations; no unsupported material claims in the reviewed sample; failures refund correctly; observed costs fit the agreed envelope.
4. **Paid beta (2–4 days, dependent on payment onboarding):** recurring billing, webhook reconciliation, subscription lifecycle tests, policy copy and optional notifications. Gate: successful/failed renewal, duplicate/out-of-order events, cancellation and expiry all produce correct access; no double charges/credits; alerting and rollback rehearsed.

Estimated effort: approximately 6–12 engineering days, plus external account setup and pilot evaluation. This is a planning range, not a delivery commitment. Public launch should follow observed reliability against the 24-hour target, explicit subscription pricing, and a support/refund policy.

Suggested code locations: `backend/research/` for the worker and pipeline; `backend/api/sherlock.py` for user endpoints; versioned database migrations in the repository's chosen migration structure; `WEAWARE/src/components/SherlockPage.jsx` and `ResearchReport.jsx`; API client additions in `WEAWARE/src/lib/api.js`. Extract reusable evidence/mail utilities rather than coupling private research to public publishing.

## Launch decision

Proceed first with private website reports and manual pilot entitlements. Measure usefulness, citation quality, turnaround, variable cost, and administrator review time. Choose subscription pricing and monthly allowance from those measurements. Add completion emails when they improve return visits; add richer research depths only after the basic investigation consistently earns its cost.

Operational references checked for this proposal:

- Existing application: `README.md`, `HANDOFF.md`, `backend/NEWSLETTERS.md`, `backend/editorial/README.md`, `backend/api/main.py`, `backend/editorial/pipeline.py`, `cloudbuild.yaml`, `WEAWARE_TEST_COSTS.md`.
- Cloud Run job execution: https://docs.cloud.google.com/run/docs/execute/jobs
- Cloud Run task timeout configuration: https://docs.cloud.google.com/run/docs/configuring/task-timeout
- Resend current pricing (verify chosen plan before enabling notifications): https://resend.com/pricing
