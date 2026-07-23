from ingestion.adapters.bluesky_adapter import BlueskyAdapter
from ingestion.adapters.newsapi_adapter import NewsAPIAdapter
from ingestion.adapters.rss_adapter import RSSAdapter
from ingestion.config import load_settings
from ingestion.normalize import dedup_intra_source, normalize_items
from ingestion.store.sqlite_store import SQLiteIngestionStore


def run() -> None:
    settings = load_settings()
    store = SQLiteIngestionStore(settings.sqlite_path)
    store.initialize()

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

    rss_raw_items, rss_poll_updates, rss_errors = rss_adapter.fetch(last_poll_state)
    api_raw_items, api_errors = news_api_adapter.fetch()
    bluesky_raw_items, bluesky_errors = bluesky_adapter.fetch()

    normalized = normalize_items(rss_raw_items + api_raw_items + bluesky_raw_items)
    deduped = dedup_intra_source(normalized)

    inserted_or_updated = store.upsert_items(deduped)
    store.upsert_poll_state(rss_poll_updates)

    print(
        "Stage 1 ingestion completed: "
        f"rss={len(rss_raw_items)} api={len(api_raw_items)} bluesky={len(bluesky_raw_items)} "
        f"normalized={len(normalized)} deduped={len(deduped)} persisted={inserted_or_updated}"
    )

    for error in rss_errors + api_errors + bluesky_errors:
        print(f"[ingestion-warning] {error}")


if __name__ == "__main__":
    run()
