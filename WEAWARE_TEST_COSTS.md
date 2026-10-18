# WeAware API test cost log

- **Testing date:** 2026-10-18
- **Current user-set test limit:** $7.00 total for testing (supersedes the earlier $5 limit)
- **Model:** Vertex AI Gemini 2.5 Flash
- **Status:** Completed the 14-article backfill. No further Gemini calls are planned.

## Gemini usage estimates

The estimates use the Vertex AI published rates of $0.15 per million input tokens, $0.60 per million non-thinking output tokens, and $3.50 per million thinking tokens. They are estimates from model usage metadata, not invoice totals.

| Run | Result | Input tokens | Output tokens | Thinking tokens | Estimated Gemini cost |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | Draft rejected by editor | 15,961 | 4,539 | 16,598 | $0.063211 |
| 2 | Draft rejected by editor | 7,158 | 2,674 | 6,747 | $0.026293 |
| 3 | Article passed and published | 32,175 | 8,615 | 29,444 | $0.113049 |
| **Total** | **3 runs; 1 article published** | **55,294** | **15,828** | **52,789** | **$0.202553** |

## Backfill usage

The local Gemini pipeline generated and reviewed candidates until the API returned 14 published articles, matching the 14 entries in the former placeholder feed. Only editor-approved stories were published. Failed drafts and interrupted attempts remained unpublished.

| Measure | Value |
| --- | ---: |
| Additional published articles | 13 |
| Total published articles in the API | 14 |
| Rejected or failed candidates | 20 |
| Tracked Gemini estimate for all runs | $1.897293 |
| Conservative allowance for three interrupted candidate attempts | $0.750000 |
| Accounted model usage including allowance | **$2.647293** |
| Remaining from the $7.00 model-test limit | **about $4.35** |

The pipeline now defaults to a $6.00 tracked-spend ceiling and reserves $0.25 before each model request. The remaining headroom covers the $0.75 allowance for interrupted requests and leaves a further margin below the $7 limit. No more model calls are being made for this backfill.

## Other Google Cloud charges

The API was redeployed to Cloud Run and served local preview requests. Cloud Run, Cloud SQL, and source-build charges are billed separately from Gemini token use. A current billing export was not available during this test, so those charges are **not included** in the model estimate above. Check the Google Cloud Billing report after its normal reporting delay for the invoice-level total. The software spend guard limits tracked Gemini usage; it cannot enforce an invoice-wide billing cap.
