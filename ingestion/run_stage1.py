"""
WeAware Ingestion Pipeline — Stage 1

Execution order:
  1. Fetch   — pull raw items from RSS feeds, commercial news APIs, and Bluesky
  2. Normalise — coerce all items to the unified schema; compute item_hash
  3. Dedup   — drop URL-level duplicates within the same source
  4. Cluster  — group items that likely cover the same story
              (mode controlled by CLUSTERING_MODE env var: "jaccard" | "hybrid")
  5. Persist  — upsert stories, items, and poll state into items.db
  6. Flag     — insert items with short/failed extraction into the review queue

Run:
  python -m ingestion.run_stage1
"""

from ingestion.adapters.bluesky_adapter import BlueskyAdapter
from ingestion.adapters.newsapi_adapter import NewsAPIAdapter
from ingestion.adapters.rss_adapter import RSSAdapter
from ingestion.cluster import CLUSTERING_MODE, cluster_items
from ingestion.config import load_settings
from ingestion.extract import run_extraction
from ingestion.normalize import dedup_intra_source, normalize_items
from ingestion.store.sqlite_store import SQLiteIngestionStore
from ingestion.store.postgres_store import PostgresIngestionStore


def run() -> None:
    settings = load_settings()
    import os
    db_backend = os.getenv("WEAWARE_DB_BACKEND", "sqlite").lower()
    if db_backend == "postgres":
        connection_string = os.getenv("WEAWARE_POSTGRES_URL")
        store = PostgresIngestionStore(connection_string)
    else:
        store = SQLiteIngestionStore(settings.sqlite_path)
    store.initialize()

    # ------------------------------------------------------------------ #
    # 1. Fetch
    # ------------------------------------------------------------------ #
    last_poll_state = store.get_poll_state()

    rss_adapter = RSSAdapter(
        registry_path=settings.registry_path,
        request_timeout_seconds=settings.request_timeout_seconds,
        max_items_per_source=settings.max_items_per_source,
        tier_intervals_seconds=settings.polling.intervals_by_tier_seconds,
    )
    news_api_adapter = NewsAPIAdapter(
        request_timeout_seconds=settings.request_timeout_seconds,
        max_items_per_source=settings.max_items_per_source,
    )
    bluesky_adapter = BlueskyAdapter(
        request_timeout_seconds=settings.request_timeout_seconds,
        max_items_per_source=settings.max_items_per_source,
        curated_accounts=settings.bluesky_curated_accounts,
        keywords=settings.bluesky_keywords,
    )

    rss_raw, rss_poll_updates, rss_errors = rss_adapter.fetch(last_poll_state)
    api_raw, api_errors = news_api_adapter.fetch()
    bluesky_raw, bluesky_errors = bluesky_adapter.fetch()

    # ------------------------------------------------------------------ #
    # 2. Normalise
    # ------------------------------------------------------------------ #
    normalized = normalize_items(rss_raw + api_raw + bluesky_raw)

    # ------------------------------------------------------------------ #
    # 3. Dedup (intra-source, same URL)
    # ------------------------------------------------------------------ #
    deduped = dedup_intra_source(normalized)

    # ------------------------------------------------------------------ #
    # 4. Cluster (cross-source story grouping)
    # ------------------------------------------------------------------ #
    stories, item_to_story = cluster_items(deduped, mode=CLUSTERING_MODE)

    # Stamp story_id and corroboration flag onto each item
    for item in deduped:
        story_id = item_to_story.get(str(item["item_hash"]))
        item["story_id"] = story_id
        # An item is corroborated when its story has contributions from
        # more than one distinct source_id
        story = next((s for s in stories if s["story_id"] == story_id), None)
        item["has_cross_source_corroboration"] = bool(
            story and story["source_count"] > 1
        )

    # ------------------------------------------------------------------ #
    # 5. Persist
    # ------------------------------------------------------------------ #
    store.upsert_stories(stories)
    inserted_or_updated = store.upsert_items(deduped)
    store.upsert_poll_state(rss_poll_updates)

    # ------------------------------------------------------------------ #
    # 6. Flag for review
    # ------------------------------------------------------------------ #
    store.flag_for_review(deduped)

    # ------------------------------------------------------------------ #
    # 7. Extract full text via Jina AI (for short/failed items)
    # ------------------------------------------------------------------ #
    extract_summary = run_extraction(store, request_timeout=settings.request_timeout_seconds)

    # ------------------------------------------------------------------ #
    # Summary
    # ------------------------------------------------------------------ #
    multi_source_stories = sum(1 for s in stories if s["source_count"] > 1)
    corroborated = sum(1 for i in deduped if i.get("has_cross_source_corroboration"))

    print(
        "Stage 1 ingestion completed:\n"
        f"  fetched  : rss={len(rss_raw)}  api={len(api_raw)}  bluesky={len(bluesky_raw)}\n"
        f"  pipeline : normalized={len(normalized)}  deduped={len(deduped)}  persisted={inserted_or_updated}\n"
        f"  clusters : stories={len(stories)}  multi-source={multi_source_stories}  corroborated_items={corroborated}\n"
        f"  extract  : attempted={extract_summary.get('attempted', 0)}  "
        f"ok={extract_summary.get('ok', 0)}  "
        f"still_short={extract_summary.get('still_short', 0)}  "
        f"failed={extract_summary.get('failed', 0)}\n"
        f"  db       : {settings.sqlite_path}"
    )

    all_errors = rss_errors + api_errors + bluesky_errors
    if all_errors:
        print(f"\n  warnings ({len(all_errors)}):")
        for error in all_errors:
            print(f"    [warn] {error}")


if __name__ == "__main__":
    run()
