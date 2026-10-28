# Sherlock Mode / Journalist Jeff pilot

Website-only private research, manual tester access, mandatory editor approval. No subscription billing, checkout, or email integration. Implementation is local and disabled by default; this guide does not imply the feature has been deployed or quality-benchmarked with live research.

## What is implemented

- Firebase-authenticated request/history/detail/cancellation and private PDF-download endpoints under `/api/v1/sherlock`; verified email and database ownership are enforced server-side.
- Manual expiring tester allowances, three credits by default, one active investigation per account. Allowances last until the grant expiry; there is no automatic monthly reset. Granting again sets a new allowance, not an additive top-up.
- Atomic submission-key deduplication and credit reservation, terminal failure/cancellation refunds, consumption only after human approval. Existing reports remain readable after access expires. Revocation blocks new work; already accepted work may finish.
- Durable PostgreSQL queue and isolated one-request worker with a 30-minute fenced lease, 20-minute provider deadline, short transactions, persisted evidence/stage artifacts, and recovery of abandoned jobs. Expired jobs fail and refund rather than automatically repeating ambiguous paid calls.
- Six deliberately different searches; at most 18 candidate page fetches; at most ten retrieved sources; minimum six accessible sources, primary evidence, and three independent origins. Cross-origin redirects, PDFs, inaccessible/paywalled documents and robots-disallowed sources are skipped in this pilot.
- Evidence map with 8–18 findings and exact passage checks, a user-selected analysis length (Brief: 400–700 words; Standard: 800–1,500; Detailed: 1,500–2,400), paragraph-to-claim references, a second model verification pass, and mandatory human review. Length changes presentation, not research rigor or source requirements. Source independence and truth still require editorial judgment; neither word counts nor model agreement proves reliability.
- Search snippets are discovery leads, never verified evidence. Text matching proves a quotation exists, not that the source or interpretation is correct. The reviewer sees original retrieved text as well as draft and claims.

## Readable reports and PDF downloads

Each request accepts `reportLength: brief|standard|detailed` (default `standard`), persists it, and passes the exact word range to both drafting and verification. The validator rejects a draft outside that range. Sources, limits, and the short introductory answer are additional to the analysis word count. Users can describe the angle they need in the scope field; the word-range choice controls the main analysis. All choices retain the same minimum source/evidence standards, one credit, and $0.50 limit. Detailed writing gets a larger but bounded output-token allowance, reserved before the call. If it cannot fit the spending limit, it fails and refunds rather than silently increasing spend.

Every editor-approved report has a **Download PDF** button. `GET /api/v1/sherlock/requests/{id}/report.pdf` checks verified Firebase identity and ownership, returns 404 for another owner's report and 409 before approval. It renders the approved stored content on demand with ReportLab, without another model call, source fetch, public storage URL, or report rewrite. No extra research credit is used. PDF generation uses modest API compute; it is not an additional model/search fee. Downloads are attachments with `Cache-Control: private, no-store`.

PDFs use embedded DejaVu Sans fonts (license in `research/fonts`), selectable text, consistent A4 margins, page numbers, a short answer, descriptive section headings, uncertainty/limitation sections, and numbered body citations linking to a source notebook. Source titles link to original HTTPS pages. Raw evidence quotations stay inspectable on the website instead of bloating a short PDF. The pilot writes English analysis; this is not a multilingual PDF or translation feature.

Re-run `python -m research.cli migrate` **before deploying this update**. It now applies all numbered idempotent migrations, including `002_report_length.sql`. Existing requests get the Standard label without rewriting their delivered text. Rebuild API and worker images to install ReportLab and include fonts. No billing, email, live paid calls, or automatic deployment are enabled by this change.

## Spend policy

The schema enforces **at most $0.50 per investigation** and **$10 across the entire pilot**, shared across users, worker processes, retries and restarts. All amounts use decimal arithmetic and transactional locks. The cumulative pilot budget never resets automatically. Initial migration leaves it paused.

Before every Brave search and Vertex generation, commit a conservative reservation. Model reservations bound UTF-8 input bytes plus envelope headroom, maximum output and a separate thinking allowance. Settle only after usable usage metadata; input, output and thinking tokens are charged. Network/usage uncertainty retains the whole reservation. No automatic provider retries or model-controlled paid tools are enabled. A reservation cannot be reused. If reported usage exceeds a reservation, the database kill switch pauses the pilot for manual reconciliation.

These are **tracked variable provider-spend limits based on operator-verified rates**, not an invoice-wide cloud cap. Incorrect rates or provider billing changes cannot be detected by token accounting alone. Cloud Run, Cloud SQL, builds, network traffic, taxes and human review are separate. Verify both provider plans/rates and model availability before enabling calls. If a useful report cannot fit $0.50, let it stop and refund the credit; do not silently raise limits or weaken the quality gate.

Providers: Brave Web Search for bounded discovery, Vertex `gemini-2.5-flash` for planning/evidence/drafting/verification. Other models are deliberately rejected until their token/thinking bounds are evaluated. This pilot does not use an autonomous deep-research API with unbounded tool spending. Verify Brave's current plan/rights for AI research before enabling it.

## Setup and operation

From `backend/`, configure worker/admin database access via `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, plus `DB_PASS` or Secret Manager `db-password`. For Cloud Run, mount the Cloud SQL instance and use `/cloudsql/PROJECT:REGION:INSTANCE` as `DB_HOST`. Local tests use a disposable PostgreSQL instance. Never point test truncation at production.

1. Apply the additive schema explicitly:

   ```sh
   python -m research.cli migrate
   ```

2. Configure worker variables from `research/.env.example`. Store the Brave key in Secret Manager. Use a restricted service account with Vertex invocation, required secret access and Cloud SQL client access. Set verified positive conservative provider rates; blank/zero/nonfinite rates fail closed. Only set `SHERLOCK_RATES_VERIFIED=true` after checking the configured model and provider plan.
3. Add testers by their Firebase UID, obtained from Firebase Authentication. No browser-supplied entitlement flags or public grant endpoints exist:

   ```sh
   python -m research.cli grant --uid TESTER_FIREBASE_UID --credits 3 --days 30 --actor YOUR_OPERATOR_ID
   python -m research.cli revoke --uid TESTER_FIREBASE_UID --actor YOUR_OPERATOR_ID
   ```

4. Deploy the API with `SHERLOCK_ENABLED=true` after migration. The API image now includes the research package. It does not need the search key or model credentials. Existing article access is unchanged.
5. Build the separate worker with backend as the build context:

   ```sh
   docker build -f research/Dockerfile -t weaware-sherlock-worker .
   ```

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

31 tests cover evidence/depth gates, fabricated quotations, duplicate-source origins, provider preflight/reservation/usage, SSRF destinations, API authentication and ownership, unpublished-draft privacy, mandatory editor approval, cancellation/refunds, idempotent concurrent submission, concurrent global spending, both database adapters, ambiguous paid calls and expired-worker fencing. Additional checks cover chosen length persistence/idempotency, exact word bounds, writer output limits, authenticated approval-only PDF downloads, PDF text/pagination/citation links, currency/Greek glyphs and markup escaping. The sample PDF was rendered and inspected page by page. These tests use fixtures and mocked providers; **no live research quality or invoice cost has been validated yet**.

Before inviting real testers, run a small approved-budget benchmark covering a current event, historical question, disputed claim, narrow specialist topic, and deliberately thin evidence. Record report usefulness, primary-source relevance, claim accuracy, per-operation charges, total cost and review effort. The service must fail transparently if the budget or evidence is insufficient. Do not market exhaustive research or guaranteed accuracy.

Provider references consulted:

- [Brave Web Search documentation](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started)
- [Vertex generate-content reference](https://cloud.google.com/vertex-ai/generative-ai/docs/model-reference/inference)
- [Gemini thinking documentation](https://ai.google.dev/gemini-api/docs/thinking)
