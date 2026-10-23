# News collection

`python -m ingestion.run_stage1` is the first step in the Cloud Build pipeline. It reads
`sources/registry.json`, polls RSS/Atom feeds, optionally calls the keyed Currents,
World News, GNews, and Webz APIs, and reads curated/search Bluesky posts. Items are
normalized, deduplicated by source and URL, clustered into stories, saved to the
configured ingestion store, and queued for text extraction when summaries are short.
The later build steps recluster, sync to PostgreSQL, and generate reviewed articles.

The registry now contains 62 feeds from 43 source IDs. The latest expansion added
19 working feeds from ABC News, PBS NewsHour, Africanews, NASA, the European Central
Bank, USGS, IAEA, Science News, Voice of America, and The Straits Times. Feed URLs
come from those publishers' own RSS directories. Each new URL was checked for a
successful XML response with entries before inclusion. The old AP endpoint had no
working DNS, The Economist endpoint returned 403, and the Google News Reuters query
returned no entries; those entries were removed. A single check is not a promise
that any publisher will keep a feed active.

## Polling controls

| Variable | Default | Meaning |
| --- | ---: | --- |
| `WEAWARE_HTTP_TIMEOUT_SECONDS` | 15 | Socket timeout for each RSS request |
| `WEAWARE_RSS_WORKERS` | 8 | Maximum concurrent RSS requests |
| `WEAWARE_MAX_ITEMS_PER_SOURCE` | 50 | Maximum entries examined per feed per run |
| `WEAWARE_MAX_ITEM_AGE_DAYS` | 7 | Skip dated RSS items older than this; `0` disables the cutoff |
| `WEAWARE_POLL_INTERVAL_PRIMARY` | 300 | Minimum seconds between successful polls of a primary feed |
| `WEAWARE_POLL_INTERVAL_SECONDARY` | 900 | Minimum seconds between successful polls of a secondary feed |

The Cloud Scheduler currently starts the entire build every two days, so the tier
intervals are lower bounds rather than the effective collection cadence. Failed
feeds are logged and retried next run. The adapter limits response bodies to 2 MB
and carries feed image URLs into the stored item. Existing images are preserved if
a later feed response has no image.

RSS access is free, but publishers retain their content rights. Keep links and
attribution to the original articles, and review a publisher's terms before
republishing article text or images. A larger list also increases Jina extraction
requests and downstream editorial work; the extraction stage is separately capped
by `WEAWARE_EXTRACT_MAX` (default 50 per run).
