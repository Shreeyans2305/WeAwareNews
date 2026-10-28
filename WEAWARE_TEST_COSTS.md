# WeAware API test cost log

> Historical usage record. The dates, model rates, backfill counts, and limits below describe the October 2026 test runs only; they are not current pricing or production limits. See the service documentation and current provider pricing before estimating a new run.

- **Testing date:** 2026-10-18
- **Earlier test limit:** $7.00 total for the original placeholder-feed backfill (superseded the earlier $5 limit)
- **Model:** Vertex AI Gemini 2.5 Flash
- **Status:** The original 14-article placeholder-feed backfill is complete. A later user-authorized expansion toward 10 new articles was stopped after a database connection failure; no further Gemini calls were made.

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

## October 18 follow-up backfill

The user authorized 10 additional articles under an approximately $8 cumulative Gemini cap. Ten editor-approved articles are now published, bringing the API total from 13 to 23. After a transient database connection failure, generation resumed with a fresh database connection at each transaction boundary, one Gemini HTTP attempt per request, and a committed $0.25 reserve before every model call. All reserves were released after successful responses; $0.75 remains allocated for ambiguous calls from the interrupted attempts.

| Measure | Value |
| --- | ---: |
| New published articles | 10 |
| Total published articles after this backfill | 23 |
| Published story estimates | $0.734080 |
| Editor-rejected candidates | 2 ($0.112925 total) |
| Health-check calls | $0.000108 |
| New conservative allowances for ambiguous calls | $0.750000 |
| Existing tracked spend before this backfill | $1.897293 |
| Current tracked DB spend, including new allowances | $3.494407 |
| Earlier allowance for interrupted attempts | $0.750000 |
| Accounted cumulative estimate | **$4.244407** |
| Remaining under the $8.00 Gemini cap | **about $3.76** |

Published stories: “Canadian Poet Anne Carson Wins Nobel Prize in Literature” ($0.085782); “Iconic Costume Designer Bob Mackie Dies at 87” ($0.092309); “Supreme Court Allows White House Ballroom Construction to Proceed Amid Legal Challenges” ($0.075883); “French Constitutional Council Blocks Social Media Ban for Under-15s” ($0.073976); “SpaceX Rocket Stage Impacts Moon After Drifting in Space” ($0.087708); “Federal Agents Search Home of US Representative Ilhan Omar Amid Undisclosed Investigation” ($0.070196); “Deadly Attack on King Khalid International Airport in Riyadh Kills 12, Injures Hundreds” ($0.053074); “Mid-Air Incident on Flydubai Flight Leads to Emergency Landing in Saudi Arabia” ($0.073978); “New York Prosecutors Reopen Cornell University Gang-Rape Investigation” ($0.049377); and “Italian Prime Minister Meloni Proposes New Education Policies for Schools” ($0.071797).

Two drafts were rejected by the editorial gate for insufficient independent corroboration. One connection failure left ambiguous request usage; the $0.75 allowance covers the earlier failed attempt and the response whose usage was lost when the database connection closed. The public article API returned HTTP 200 with all 23 published articles. No invoice-level GCP billing data was available; these figures estimate Gemini use only.
