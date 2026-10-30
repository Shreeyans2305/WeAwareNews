# Sherlock Mode / Journalist Jeff pilot

Website-only private research, manual tester access, mandatory editor approval. No subscription billing, checkout, or email integration. The manually provisioned pilot is deployed at https://weaware-3504c.web.app. Configuration defaults remain disabled for new installations. Delivery requires editor approval.

Readiness update, 29 October 2026: the API and worker are now deployed with report gates that reject uncited numeric claims, percentages without a source-backed comparison/baseline, and projections without explicit dated-assessment attribution. The independent-review prompt highlights these same checks. The focused quality suite passes 26 checks. No live investigation has exercised the new gates; production admission remains paused pending a bounded benchmark and human editorial review.

## What is implemented

- Firebase-authenticated request/history/detail/cancellation and private PDF-download endpoints under `/api/v1/sherlock`; verified email and database ownership are enforced server-side.
- Manual expiring tester allowances, three credits by default, one active investigation per account. Allowances last until the grant expiry; there is no automatic monthly reset. Granting again sets a new allowance, not an additive top-up.
- Atomic submission-key deduplication and credit reservation, terminal failure/cancellation refunds, consumption only after human approval. Existing reports remain readable after access expires. Revocation blocks new work; already accepted work may finish.
- Durable PostgreSQL queue and isolated one-request worker with a 30-minute fenced lease, 20-minute provider deadline, short transactions, persisted evidence/stage artifacts, and recovery of abandoned jobs. Expired jobs fail and refund rather than automatically repeating ambiguous paid calls.
- Six deliberately different searches; at most 18 candidate page fetches; at most ten retrieved sources; minimum six accessible sources, primary evidence, and three independent origins. Source redirects repeat robots checks for every destination/path, with a five-hop bound, pinned public DNS and verified TLS. Protego handles wildcard/longest-match robots rules, and publisher crawl delays/request rates are honored within the retrieval deadline. Robots-file redirects follow the public-HTTPS rules of RFC 9309. PDFs, inaccessible/paywalled documents and robots-disallowed sources are skipped.
- Evidence map with 8–18 findings, model selection of numbered original passages (quotation text copied by the application), and exact passage checks, a user-selected analysis length (Brief: 400–700 words; Standard: 800–1,500; Detailed: 1,500–2,400), paragraph-to-claim references, a second model verification pass, and mandatory human review. A deterministic report gate also requires every numeric token to occur in the cited original passages, requires percentages to state a comparison/baseline present in those passages, and requires projections to name the dated assessment in the prose. Length changes presentation, not research rigor or source requirements. Source independence and truth still require editorial judgment; neither word counts nor model agreement proves reliability.
- Search snippets are discovery leads, never verified evidence. Text matching proves a quotation exists, not that the source or interpretation is correct. The reviewer sees original retrieved text as well as draft and claims.

## Readable reports and PDF downloads

Each request accepts `reportLength: brief|standard|detailed` (default `standard`), persists it, and passes the exact word range to both drafting and verification. The validator rejects a draft outside that range. Sources, limits, and the short introductory answer are additional to the analysis word count. Users can describe the angle they need in the scope field; the word-range choice controls the main analysis. All choices retain the same minimum source/evidence standards, one credit, and $0.50 limit. Detailed writing gets a larger but bounded output-token allowance, reserved before the call. If it cannot fit the spending limit, it fails and refunds rather than silently increasing spend.

Every editor-approved report has a **Download PDF** button. `GET /api/v1/sherlock/requests/{id}/report.pdf` checks verified Firebase identity and ownership, returns 404 for another owner's report and 409 before approval. It renders the approved stored content on demand with ReportLab, without another model call, source fetch, public storage URL, or report rewrite. No extra research credit is used. PDF generation uses modest API compute; it is not an additional model/search fee. Downloads are attachments with `Cache-Control: private, no-store`.

PDFs use embedded DejaVu Sans fonts (license in `research/fonts`), selectable text, consistent A4 margins, page numbers, a short answer, descriptive section headings, uncertainty/limitation sections, and numbered body citations linking to a source notebook. Source titles link to original HTTPS pages. Raw evidence quotations stay inspectable on the website instead of bloating a short PDF. The pilot writes English analysis; this is not a multilingual PDF or translation feature.

Re-run `python -m research.cli migrate` **before deploying this update**. It now applies all numbered idempotent migrations, including `002_report_length.sql` and `003_manual_email_invites.sql`. Existing requests get the Standard label without rewriting their delivered text. Rebuild API and worker images to install ReportLab and include fonts. No Sherlock billing or email integration exists. Live calls require explicit worker and database enablement.

## Spend policy

The schema enforces **at most $0.50 per investigation** and **$10 across the entire pilot**, shared across users, worker processes, retries and restarts. All amounts use decimal arithmetic and transactional locks. The cumulative pilot budget never resets automatically. Initial migration leaves it paused.

Before every paid fixed-price Brave search and Vertex generation, commit a conservative reservation. Model reservations bound UTF-8 input bytes plus envelope headroom and maximum output, with additional conservative thinking headroom. Gemini 3.5 Flash-Lite uses LOW thinking; reasoning counts against the output token limit. Settle only after usable usage metadata; input, output and thinking tokens are charged. Network/usage uncertainty retains the whole reservation. No automatic provider retries are enabled. Generation stages have no model-controlled paid search tools. Current Google grounding charges per model-generated query, without a documented hard query bound, so Google discovery is rejected before any paid call. A reservation cannot be reused. If reported usage exceeds a reservation, the database kill switch pauses the pilot for manual reconciliation.

These are **tracked variable provider-spend limits based on operator-verified rates**, not an invoice-wide cloud cap. Incorrect rates or provider billing changes cannot be detected by token accounting alone. Cloud Run, Cloud SQL, builds, network traffic, taxes and human review are separate. Verify both provider plans/rates and model availability before enabling calls. If a useful report cannot fit $0.50, let it stop and refund the credit; do not silently raise limits or weaken the quality gate.

Providers: free Wikipedia bibliography discovery by default, optional fixed-price Brave Search, and Vertex `gemini-3.5-flash-lite` for planning/evidence/drafting/verification. Conservative configured rates are $0.005 per search, $0.30 per million input tokens and $2.50 per million output/thinking tokens, even when free allowances may apply. Gemini 2.5 Flash is retired and rejected by the provider preflight. Flash is also allowed with its separately enforced price floor ($1.50/$9.00 per million input/output tokens); its slower responses and higher costs require a separate benchmark before selecting it for the worker. Other models are rejected until their token/thinking bounds are evaluated. This pilot does not use an autonomous deep-research API with unbounded tool spending. Verify the search plan’s AI-use and storage rights before enabling it.

## Setup and operation

From `backend/`, configure worker/admin database access via `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, plus `DB_PASS` or Secret Manager `db-password`. For Cloud Run, mount the Cloud SQL instance and use `/cloudsql/PROJECT:REGION:INSTANCE` as `DB_HOST`. Local tests use a disposable PostgreSQL instance. Never point test truncation at production.

1. Apply the additive schema explicitly:

   ```sh
   python -m research.cli migrate
   ```

2. Configure worker variables from `research/.env.example`. The default `SHERLOCK_SEARCH_PROVIDER=wikipedia` needs no API key or additional account. It searches three Wikipedia articles per query and returns at most 100 original reference URLs per query, with no pagination or retries. One metered model selection step chooses exactly 18 known candidate URLs from a pool of at most 240, allowing for retrieval failures; insufficient or invented selections are rejected. Only independently fetched original text can become evidence. Search itself costs zero; model selection and generation still consume the tracked budget. Breaking news and topics absent from these bibliographies have limited coverage. An optional Brave key can be stored in Secret Manager as `sherlock-brave-api-key`. Google generation uses the existing Vertex project/service account. Google search grounding is disabled because its current query billing cannot be bounded by the existing adapter. Use a restricted service account with Vertex invocation, required secret access and Cloud SQL client access. Set verified positive conservative provider rates; blank/zero/nonfinite rates fail closed. Only set `SHERLOCK_RATES_VERIFIED=true` after checking the configured model and provider plan.
3. Add testers by their Firebase UID, obtained from Firebase Authentication, or invite a specific verified email before registration. Email invitations activate only when a server-verified Firebase identity matches that address; no email is sent and repeated sign-ins do not replenish credits. No browser-supplied entitlement flags or public grant endpoints exist:

   ```sh
   python -m research.cli grant-email --email tester@example.com --credits 3 --days 30 --actor YOUR_OPERATOR_ID
   python -m research.cli grant --uid TESTER_FIREBASE_UID --credits 3 --days 30 --actor YOUR_OPERATOR_ID
   python -m research.cli revoke --uid TESTER_FIREBASE_UID --actor YOUR_OPERATOR_ID
   ```

4. Deploy the API with `SHERLOCK_ENABLED=true` after migration. The API image now includes the research package. It does not need the search key or model credentials. Existing article access is unchanged.
5. Build the separate worker with backend as the build context:

   ```sh
   docker build -f research/Dockerfile -t weaware-sherlock-worker .
   ```

   Cloud Build can produce and push a tagged worker image from the backend context with `gcloud builds submit backend --config backend/research/cloudbuild.yaml --substitutions=_TAG=YOUR_TAG`.

   Configure the Cloud Run Job with one task, parallelism one, maximum retries zero, a 25-minute job timeout, the Cloud SQL mount and the worker environment/secrets. Use authenticated Cloud Scheduler job execution hourly; set maximum instances/executions conservatively. One execution handles one request. The database fences overlapping executions and spending even if a scheduler retries. Scheduler and infrastructure setup are not automatically installed by this feature.
6. Set worker `SHERLOCK_PAID_CALLS_ENABLED=true`, then enable the shared budget explicitly:

   ```sh
   python -m research.cli budget --enable --actor YOUR_OPERATOR_ID
   python -m research.cli run-once
   python -m research.cli budget
   ```

   No paid calls are made by grant, inspect, migration, review, or budget commands. `run-once` first validates provider configuration, claims a request, and then makes bounded paid calls if work exists. It also recovers expired jobs and removes raw artifacts older than 30 days. Run cleanup separately each day if the worker is disabled:

   ```sh
   python -m research.cli purge-evidence
   ```

## Human review before delivery

```sh
python -m research.cli review-list
python -m research.cli inspect REQUEST_ID
python -m research.cli review REQUEST_ID --decision approve --actor EDITOR_ID --note 'Checked primary records, independent origins, chronology and every material claim.'
# Or reject and refund:
python -m research.cli review REQUEST_ID --decision reject --actor EDITOR_ID --note 'Describe the concrete evidence or interpretation problem.'
```

Inspection prints private prompts, drafts and source text. Use a trusted operator terminal; do not paste the output into public logs. Open original sources, check the dates and question relevance, confirm primary-source status and syndication origins, inspect each material citation in context, and verify the conclusion/uncertainties. Automated approval alone is insufficient. Complete review promptly to support the 24-hour estimate; it is not a guaranteed SLA. Only approved reports become visible to their owner, and never in the public feed.

The website provides request history, processing status, credit balance and inspectable citations. It polls active work every 30 seconds while Sherlock is open. Editor controls are CLI-only in this pilot. Account deletion/report deletion requires an operator process for now. Raw stage artifacts are removed after 30 days by maintenance; report text, selected quotes, usage and audit records remain until separately removed under the account-retention policy. Backups follow database retention.

## Pause, failure and rollback

```sh
python -m research.cli budget --pause --actor YOUR_OPERATOR_ID
```

Pausing prevents new reservations and admissions; already in-flight provider calls can finish within existing reservations. Stop the scheduler/worker to stop future work, and set API `SHERLOCK_ENABLED=false` to disable new submission. Approved report reads/cancellation remain available. Do not drop tables or reset `committed` on rollback; that would discard privacy/audit records or reopen spent funds. Full reservations for uncertain calls require invoice reconciliation before manual correction.

Diagnose `error_code` and operations metadata by request ID. Routine worker logs contain only request IDs and error types, never provider payloads or source bodies. `budget` shows enabled status, cap and committed spend. `review-list` shows pending editor work. Monitor queue age, failed requests and review backlog; admission limits are intentionally small. A missing migration or unavailable database requires operator attention, not a fallback to unmetered work.

## Verification

```sh
# From repository root. Install backend/research/requirements-test.txt first.
SHERLOCK_TEST_DSN=postgresql://USER:PASSWORD@127.0.0.1:PORT/DISPOSABLE_DB \
  .venv/bin/python -m unittest discover -s backend/tests -p test_sherlock.py -v
npm --prefix WEAWARE run build
```

43 tests cover evidence/depth gates, fabricated quotations, duplicate-source origins, provider preflight/reservation/usage, SSRF destinations, API authentication and ownership, unpublished-draft privacy, mandatory editor approval, cancellation/refunds, idempotent concurrent submission, concurrent global spending, both database adapters, ambiguous paid calls and expired-worker fencing. Additional checks cover chosen length persistence/idempotency, exact word bounds, writer output limits, authenticated approval-only PDF downloads, PDF text/pagination/citation links, currency/Greek glyphs and markup escaping. The sample PDF was rendered and inspected page by page. These automated tests use fixtures and mocked providers. A deployed live investigation and its four-page PDF were also exercised; operator validation rejected factual framing missed by the model verifier. No live report has been approved, and provider invoices have not been reconciled.

Before inviting real testers, run a small approved-budget benchmark covering a current event, historical question, disputed claim, narrow specialist topic, and deliberately thin evidence. Record report usefulness, primary-source relevance, claim accuracy, per-operation charges, total cost and review effort. The service must fail transparently if the budget or evidence is insufficient. Do not market exhaustive research or guaranteed accuracy.

Provider references consulted:

- [Vertex pricing](https://cloud.google.com/vertex-ai/generative-ai/pricing)
- [Google Search grounding and required search suggestions](https://cloud.google.com/vertex-ai/generative-ai/docs/grounding/grounding-with-google-search)

- [Brave Web Search documentation](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started)
- [Vertex generate-content reference](https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/inference)
- [Gemini thinking documentation](https://ai.google.dev/gemini-api/docs/thinking)

## Deployment validation — 28 October 2026

Migrations 001–003 applied to the existing production database. Website and API deployed; a separate worker job exists. Manual access: theactiverecord@gmail.com has three credits for 30 days; weaware.news@gmail.com has an unredeemed verified-email invitation for the same allowance. No mail was sent.

The retired Gemini 2.5 Flash returned HTTP 404 during initial live tests. The deployed worker now uses Gemini 3.5 Flash-Lite and free Wikipedia bibliography discovery, requiring no new search account. A final ozone-recovery investigation fetched six sources, assembled twelve claims and 486 analysis words, and passed automated verification for $0.02280220 in tracked model usage. A four-page marked editor-preview PDF was generated and inspected.

Operator validation found missing historical attribution, potentially misleading ODGI metric wording, and incomplete supporting quotation windows. The draft was rejected and its credit refunded; no human approval or report release occurred. This is a real verification false positive and a launch blocker. Forty-three automated tests pass, but that does not establish live editorial reliability. See `output/sherlock/pilot-deployment-2026-10-28.md` for the precise test record and remaining work.

Final tracked cumulative commitment is $0.39956310, including $0.09393880 held for uncertain calls; no reservations were reset. Database admission is paused, worker paid calls are disabled, and the hourly scheduler is PAUSED. Both tester allowances remain provisioned, but new investigations cannot start until readiness work is completed. No new paid search subscription is required. Existing newsletter email is unrelated; Sherlock has no mail or billing code. Do not represent this deployment as a research-ready pilot.

### Private draft PDF for editorial review

`python -m research.cli preview-pdf REQUEST_ID --output /private/new-report.pdf` exports an awaiting-review report only in the privileged operator environment. Every page is marked **EDITOR COPY — NOT APPROVED**; it does not change database status or expose the draft through reader APIs. The ordinary website PDF endpoint still rejects every unapproved request. Use this preview to obtain actual human approval before release.
