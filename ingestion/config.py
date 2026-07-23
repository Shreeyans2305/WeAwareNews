import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


def load_dotenv(path: Path | None = None) -> None:
    env_path = path or (Path.cwd() / ".env")
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def _csv_env(name: str, default: List[str]) -> List[str]:
    raw = os.getenv(name)
    if not raw:
        return default
    return [part.strip() for part in raw.split(",") if part.strip()]


@dataclass(frozen=True)
class PollingConfig:
    intervals_by_tier_seconds: Dict[str, int]


@dataclass(frozen=True)
class Settings:
    registry_path: Path
    sqlite_path: Path
    polling: PollingConfig
    request_timeout_seconds: int
    max_items_per_source: int
    bluesky_curated_accounts: List[str]
    bluesky_keywords: List[str]


def load_settings() -> Settings:
    load_dotenv()

    primary_interval = int(os.getenv("WEAWARE_POLL_INTERVAL_PRIMARY", "300"))
    secondary_interval = int(os.getenv("WEAWARE_POLL_INTERVAL_SECONDARY", "900"))
    timeout = int(os.getenv("WEAWARE_HTTP_TIMEOUT_SECONDS", "15"))
    max_items = int(os.getenv("WEAWARE_MAX_ITEMS_PER_SOURCE", "50"))

    return Settings(
        registry_path=Path(__file__).resolve().parent / "sources" / "registry.json",
        sqlite_path=Path(__file__).resolve().parent / "store" / "items.db",
        polling=PollingConfig(
            intervals_by_tier_seconds={
                "primary": primary_interval,
                "secondary": secondary_interval,
            }
        ),
        request_timeout_seconds=timeout,
        max_items_per_source=max_items,
        bluesky_curated_accounts=_csv_env(
            "BLUESKY_CURATED_ACCOUNTS",
            [
                "apnews.com",
                "npr.org",
                "bbc.com",
                "reuters.com",
            ],
        ),
        bluesky_keywords=_csv_env(
            "BLUESKY_KEYWORDS",
            ["breaking news", "world news", "geopolitics"],
        ),
    )
