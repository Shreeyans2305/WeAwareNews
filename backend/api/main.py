"""
WeAware News API
Exposes corroborated story clusters for external consumption (e.g. Make.com automation).

Authentication: x-api-key header (value stored in Secret Manager as 'api-key').
Database: Cloud SQL Postgres via Cloud SQL Python Connector + pg8000 (no SQLAlchemy needed).
"""
import os
import json
import re
import logging
from contextlib import contextmanager
from typing import List, Optional
from urllib.parse import urlparse

from fastapi import FastAPI, Depends, HTTPException, Header, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.cloud import secretmanager
from google.cloud.sql.connector import Connector, IPTypes
import firebase_admin
from firebase_admin import auth as firebase_auth

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="WeAware News API")
_default_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
_allowed_origins = [origin.strip() for origin in os.getenv("WEAWARE_ALLOWED_ORIGINS", "").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(dict.fromkeys(_default_origins + _allowed_origins)),
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


# ---------------------------------------------------------------------------
# Image filtering — inline reimplementation to avoid import path issues
# in the Cloud Run container (api/ is the working directory, not backend/)
# ---------------------------------------------------------------------------

# Bluesky avatars, logos, favicons, placeholders, tracking pixels
_BAD_IMAGE_SUBSTRINGS = (
    "avatar_thumbnail", "avatar/plain", "/img/avatar",
    "/favicon", "/brand/", "/branding/", "placeholder",
    "no-image", "noimage", "default-image", "default_image",
    "fallback-image", "fallback_image", "generic-image",
    "site-logo", "site_logo", "header-logo", "header_logo",
    "nav-logo", "nav_logo", "company-logo", "company_logo",
    "/pixel", "/beacon", "/track", "1x1",
    "/profile_images/", "/profile_banners/", "/default_profile",
)

_BAD_IMAGE_REGEXES = [
    re.compile(r"/[^/]*\blogo\b[^/]*\.(jpe?g|png|gif|svg|webp)", re.IGNORECASE),
    re.compile(r"/[^/]*\bicon\b[^/]*\.(jpe?g|png|gif|svg|webp|ico)", re.IGNORECASE),
]

_ALLOWLIST_DOMAINS = {
    "ichef.bbci.co.uk", "images.indianexpress.com", "static.toiimg.com",
    "i.cbc.ca", "npr.brightspotcdn.com", "media.zenfs.com",
    "dims.apnews.com", "s.yimg.com", "c.files.bbci.co.uk", "image.cnbcfm.com",
}

_LOGO_PRONE_DOMAINS = {"cdn.bsky.app"}


def _is_valid_editorial_image(url: Optional[str]) -> bool:
    """Check if an image URL is a real editorial photo (not a logo/avatar)."""
    if not url or not url.strip():
        return False
    url_lower = url.lower()
    try:
        from urllib.parse import urlparse
        hostname = urlparse(url).hostname or ""
    except Exception:
        return False
    if hostname in _ALLOWLIST_DOMAINS:
        return True
    if hostname in _LOGO_PRONE_DOMAINS:
        return False
    for pattern in _BAD_IMAGE_SUBSTRINGS:
        if pattern in url_lower:
            return False
    for regex in _BAD_IMAGE_REGEXES:
        if regex.search(url):
            return False
    return True




# ---------------------------------------------------------------------------
# Secrets — loaded once at startup, cached in module-level variables
# ---------------------------------------------------------------------------

_secret_client: Optional[secretmanager.SecretManagerServiceClient] = None
_api_key: Optional[str] = None
_db_pass: Optional[str] = None
_connector: Optional[Connector] = None


def _get_secret(secret_id: str) -> str:
    global _secret_client
    if _secret_client is None:
        _secret_client = secretmanager.SecretManagerServiceClient()
    project_id = os.environ["GOOGLE_CLOUD_PROJECT"]
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
    response = _secret_client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


@app.on_event("startup")
def _load_secrets() -> None:
    global _api_key, _db_pass, _connector
    logger.info("Loading secrets from Secret Manager…")
    _api_key = os.getenv("API_KEY") or _get_secret("api-key")
    _db_pass = os.getenv("DB_PASS") or _get_secret("db-password")
    _connector = Connector()
    # Safe, additive schema setup for the public article read API.
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS editorial_articles (
                    article_id TEXT PRIMARY KEY,
                    story_id TEXT NOT NULL,
                    source_fingerprint TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'processing',
                    topic TEXT, title TEXT, summary TEXT,
                    body JSONB NOT NULL DEFAULT '[]'::jsonb,
                    image_url TEXT,
                    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
                    flagged_claims JSONB NOT NULL DEFAULT '[]'::jsonb,
                    consensus INTEGER NOT NULL DEFAULT 0,
                    read_mins INTEGER NOT NULL DEFAULT 1,
                    agent_trace JSONB NOT NULL DEFAULT '{}'::jsonb,
                    estimated_cost_usd NUMERIC(12, 8) NOT NULL DEFAULT 0,
                    failure_reason TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    published_at TIMESTAMPTZ
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_editorial_articles_publication ON editorial_articles(status, published_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_editorial_articles_topic ON editorial_articles(topic, published_at DESC)")
        finally:
            cursor.close()
        conn.commit()
    finally:
        conn.close()
    logger.info("Secrets loaded. Connector initialised.")


@app.on_event("shutdown")
def _shutdown() -> None:
    if _connector:
        _connector.close()


# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------

def get_db():
    instance_connection_name = os.environ["INSTANCE_CONNECTION_NAME"]
    db_user = os.getenv("DB_USER", "weaware_user")
    db_name = os.getenv("DB_NAME", "weaware")

    conn = _connector.connect(
        instance_connection_name,
        "pg8000",
        user=db_user,
        password=_db_pass,
        db=db_name,
        ip_type=IPTypes.PUBLIC,
    )
    try:
        yield conn
    finally:
        conn.close()


def get_db_connection():
    """Open a short-lived Cloud SQL connection for startup schema setup."""
    instance_connection_name = os.environ["INSTANCE_CONNECTION_NAME"]
    return _connector.connect(
        instance_connection_name,
        "pg8000",
        user=os.getenv("DB_USER", "weaware_user"),
        password=_db_pass,
        db=os.getenv("DB_NAME", "weaware"),
        ip_type=IPTypes.PUBLIC,
    )


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def verify_api_key(x_api_key: str = Header(None)):
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API Key")
    if x_api_key != _api_key:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return True


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Article(BaseModel):
    source_name: str
    title: Optional[str] = None
    url: str
    snippet: Optional[str] = None
    region: str


class StoryResponse(BaseModel):
    story_id: str
    source_count: int
    articles: List[Article]
    image_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/stories/next", response_model=StoryResponse)
def get_next_story(db=Depends(get_db), auth=Depends(verify_api_key)):
    """
    Return the most recent unposted corroborated story (source_count >= MIN_SOURCES)
    that has at least one editorial-quality image.
    Returns 204 No Content if no eligible stories remain.
    """
    min_sources = int(os.getenv("WEAWARE_MIN_SOURCES", "2"))
    # Try up to this many candidates before giving up — guards against stories
    # whose DB image_urls all fail Python-level editorial re-validation
    # (e.g. Bluesky avatar thumbnails that slipped through the SQL filter).
    MAX_CANDIDATES = int(os.getenv("WEAWARE_MAX_CANDIDATES", "20"))

    cursor = db.cursor()

    # Fetch the top-N candidates ordered by recency.
    # The EXISTS subquery pre-filters on a strengthened image-quality check:
    # it excludes Bluesky avatar_thumbnail URLs (the #1 source of false positives)
    # and pure cdn.bsky.app avatar paths so we don't waste time on stories whose
    # only "images" are profile pictures.
    cursor.execute(
        """
        SELECT s.story_id, s.source_count
        FROM stories s
        WHERE s.source_count >= %s
          AND s.posted = false
          AND EXISTS (
            SELECT 1 FROM items i
            WHERE i.story_id = s.story_id
              AND i.image_url IS NOT NULL
              AND i.image_url != ''
              AND i.image_url NOT LIKE '%%avatar_thumbnail%%'
              AND i.image_url NOT LIKE '%%avatar/plain%%'
              AND i.image_url NOT LIKE '%%/img/avatar%%'
              AND i.image_url NOT LIKE '%%.bsky.app/img/avatar%%'
          )
        ORDER BY s.recency DESC
        LIMIT %s
        """,
        (min_sources, MAX_CANDIDATES),
    )
    candidate_rows = cursor.fetchall()

    if not candidate_rows:
        cursor.close()
        return Response(status_code=204)

    # Walk candidates in recency order; stop at the first one that produces
    # a valid editorial image after Python-level re-validation.
    for cand_row in candidate_rows:
        story_id = cand_row[0]
        source_count = cand_row[1]

        cursor.execute(
            """
            SELECT source_name, title, url, raw_text, region, image_url, source_type
            FROM items
            WHERE story_id = %s
            ORDER BY published_at DESC NULLS LAST
            """,
            (story_id,),
        )
        articles_rows = cursor.fetchall()

        articles = []
        cdn_images: List[str] = []
        rss_images: List[str] = []
        other_images: List[str] = []

        for r in articles_rows:
            # columns: source_name, title, url, raw_text, region, image_url, source_type
            img = r[5]
            source_type = r[6] if len(r) > 6 else "unknown"

            if img and _is_valid_editorial_image(img):
                try:
                    hostname = urlparse(img).hostname or ""
                except Exception:
                    hostname = ""

                if hostname in _ALLOWLIST_DOMAINS:
                    cdn_images.append(img)
                elif source_type in ("rss", "news_api_currents", "news_api_world_news",
                                     "news_api_gnews", "news_api_webz"):
                    rss_images.append(img)
                else:
                    other_images.append(img)

            articles.append(Article(
                source_name=r[0],
                title=r[1],
                url=r[2],
                snippet=r[3],
                region=r[4],
            ))

        # Pick the best available image
        if cdn_images:
            image_url = cdn_images[0]
        elif rss_images:
            image_url = rss_images[0]
        elif other_images:
            image_url = other_images[0]
        else:
            # This story's images all failed Python-level re-validation.
            # Log it and try the next candidate.
            logger.warning(
                "Story %s: all image_urls failed editorial validation — skipping",
                story_id,
            )
            continue

        cursor.close()
        return StoryResponse(
            story_id=story_id,
            source_count=source_count,
            articles=articles,
            image_url=image_url,
        )

    # All candidates exhausted without finding a usable image.
    cursor.close()
    return Response(status_code=204)


@app.get("/debug/stats")
def debug_stats(db=Depends(get_db), auth=Depends(verify_api_key)):
    """Temporary debug endpoint — returns DB stats to diagnose /stories/next returning 204."""
    cursor = db.cursor()
    stats = {}

    cursor.execute("SELECT COUNT(*) FROM stories")
    stats["total_stories"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM stories WHERE posted = false")
    stats["unposted_stories"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM stories WHERE source_count >= 2")
    stats["corroborated_stories"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM stories WHERE source_count >= 2 AND posted = false")
    stats["corroborated_unposted"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM items WHERE image_url IS NOT NULL AND image_url != ''")
    stats["items_with_image"] = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM items WHERE image_url IS NULL OR image_url = ''")
    stats["items_without_image"] = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(DISTINCT s.story_id)
        FROM stories s
        WHERE s.source_count >= 2 AND s.posted = false
          AND EXISTS (SELECT 1 FROM items i WHERE i.story_id = s.story_id AND i.image_url IS NOT NULL AND i.image_url != '')
    """)
    stats["eligible_for_next"] = cursor.fetchone()[0]

    cursor.execute("SELECT MAX(fetched_at) FROM items")
    stats["newest_item_fetched_at"] = str(cursor.fetchone()[0])

    cursor.execute("""
        SELECT source_type, COUNT(*) as n FROM items GROUP BY source_type ORDER BY n DESC
    """)
    stats["source_type_distribution"] = {row[0]: row[1] for row in cursor.fetchall()}

    cursor.execute("""
        SELECT s.story_id, s.source_count, s.recency,
               SUM(CASE WHEN i.image_url IS NOT NULL AND i.image_url != '' THEN 1 ELSE 0 END) as imgs
        FROM stories s
        LEFT JOIN items i ON i.story_id = s.story_id
        WHERE s.source_count >= 2 AND s.posted = false
        GROUP BY s.story_id, s.source_count, s.recency
        ORDER BY s.recency DESC LIMIT 5
    """)
    stats["top5_unposted_corroborated"] = [
        {"story_id": r[0], "source_count": r[1], "recency": str(r[2]), "items_with_image": r[3]}
        for r in cursor.fetchall()
    ]

    # Show the exact story the SQL in /stories/next would select
    cursor.execute(
        """
        SELECT s.story_id, s.source_count
        FROM stories s
        WHERE s.source_count >= 2
          AND s.posted = false
          AND EXISTS (
            SELECT 1 FROM items i
            WHERE i.story_id = s.story_id
              AND i.image_url IS NOT NULL
              AND i.image_url != ''
          )
        ORDER BY s.recency DESC
        LIMIT 1
        """,
    )
    sql_row = cursor.fetchone()
    if sql_row:
        sel_story_id = sql_row[0]
        stats["sql_selected_story"] = sel_story_id
        cursor.execute(
            "SELECT source_name, source_type, image_url FROM items WHERE story_id = %s AND image_url IS NOT NULL AND image_url != ''",
            (sel_story_id,),
        )
        stats["sql_selected_story_images"] = [
            {"source_name": r[0], "source_type": r[1], "image_url": r[2]}
            for r in cursor.fetchall()
        ]
    else:
        stats["sql_selected_story"] = None

    # Show 20 sample image_urls from eligible stories
    cursor.execute("""
        SELECT DISTINCT i.image_url, i.source_type
        FROM items i
        JOIN stories s ON s.story_id = i.story_id
        WHERE s.source_count >= 2 AND s.posted = false
          AND i.image_url IS NOT NULL AND i.image_url != ''
        LIMIT 20
    """)
    stats["sample_images_from_eligible"] = [
        {"image_url": r[0], "source_type": r[1]} for r in cursor.fetchall()
    ]

    cursor.close()
    return stats



@app.post("/stories/{story_id}/mark-posted")
def mark_posted(story_id: str, db=Depends(get_db), auth=Depends(verify_api_key)):
    """Mark a story as posted so it won't be returned by /stories/next again."""
    cursor = db.cursor()
    cursor.execute(
        "UPDATE stories SET posted = true WHERE story_id = %s",
        (story_id,),
    )
    rowcount = cursor.rowcount
    db.commit()
    cursor.close()

    if rowcount == 0:
        raise HTTPException(status_code=404, detail="Story not found")

    return {"status": "ok", "story_id": story_id}


# ---------------------------------------------------------------------------
# Public website article API
# ---------------------------------------------------------------------------

def _article_dict(row) -> dict:
    def json_value(value, fallback):
        if value is None:
            return fallback
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (TypeError, ValueError):
                return fallback
        return value

    body = json_value(row[4], [])
    if isinstance(body, list):
        body = [_clean_article_text(paragraph) for paragraph in body if isinstance(paragraph, str)]

    return {
        "id": row[0], "topic": row[1] or "Other", "title": _clean_article_text(row[2] or ""),
        "summary": _clean_article_text(row[3] or ""), "body": body, "image": row[5],
        "sources": json_value(row[6], []), "flaggedClaims": json_value(row[7], []),
        "consensus": row[8] or 0, "readMins": row[9] or 1,
        "publishedAt": row[10].isoformat() if row[10] else None,
    }


_INTERNAL_SOURCE_REFS = re.compile(r"\[(?:[0-9a-f]{40,64}(?:\s*,\s*)?)+\]", re.IGNORECASE)


def _clean_article_text(value: str) -> str:
    """Hide internal source hashes if an older or external draft includes them inline."""
    value = _INTERNAL_SOURCE_REFS.sub("", value)
    value = re.sub(r"\s+([,.;:!?])", r"\1", value)
    return re.sub(r"[ \t]{2,}", " ", value).strip()


_ARTICLE_FIELDS = "article_id, topic, title, summary, body, image_url, sources, flagged_claims, consensus, read_mins, published_at"


@app.get("/api/v1/articles")
def list_articles(
    topic: Optional[str] = Query(None, max_length=80),
    q: Optional[str] = Query(None, max_length=200),
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10000),
    db=Depends(get_db),
):
    """Return published articles for the WEAWARE feed, with topic/search filters."""
    cursor = db.cursor()
    clauses = ["status = 'published'"]
    params = []
    if topic and topic.lower() != "all":
        clauses.append("LOWER(topic) = LOWER(%s)")
        params.append(topic)
    if q and q.strip():
        clauses.append("(title ILIKE %s OR summary ILIKE %s OR EXISTS (SELECT 1 FROM jsonb_array_elements_text(body) p WHERE p ILIKE %s))")
        search = f"%{q.strip()}%"
        params.extend([search, search, search])
    where = " AND ".join(clauses)
    cursor.execute(f"SELECT COUNT(*) FROM editorial_articles WHERE {where}", tuple(params))
    total = cursor.fetchone()[0]
    cursor.execute(
        f"SELECT {_ARTICLE_FIELDS} FROM editorial_articles WHERE {where} ORDER BY published_at DESC NULLS LAST, article_id LIMIT %s OFFSET %s",
        tuple(params + [limit, offset]),
    )
    articles = [_article_dict(row) for row in cursor.fetchall()]
    cursor.close()
    return {"articles": articles, "total": total, "limit": limit, "offset": offset}


@app.get("/api/v1/articles/{article_id}")
def get_article(article_id: str, db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute(
        f"SELECT {_ARTICLE_FIELDS} FROM editorial_articles WHERE article_id=%s AND status='published'",
        (article_id,),
    )
    row = cursor.fetchone()
    cursor.close()
    if not row:
        raise HTTPException(status_code=404, detail="Article not found")
    return _article_dict(row)


@app.get("/api/v1/topics")
def list_article_topics(db=Depends(get_db)):
    cursor = db.cursor()
    cursor.execute("SELECT DISTINCT topic FROM editorial_articles WHERE status='published' AND topic IS NOT NULL ORDER BY topic")
    topics = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return {"topics": topics}


def verify_firebase_user(authorization: Optional[str] = Header(None)):
    """Verify a Firebase ID token; callers never supply trusted profile fields."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="A Firebase bearer token is required")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="A Firebase bearer token is required")

    project_id = os.getenv("FIREBASE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project_id:
        raise HTTPException(status_code=503, detail="Firebase authentication is not configured on this API")

    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(options={"projectId": project_id})

    try:
        return firebase_auth.verify_id_token(token, check_revoked=False)
    except Exception as error:
        logger.info("Firebase ID token rejected: %s", type(error).__name__)
        raise HTTPException(status_code=401, detail="The Firebase sign-in token is invalid or expired") from error


@app.get("/api/v1/auth/me")
def current_user(claims: dict = Depends(verify_firebase_user)):
    """Return a minimal profile derived only from a verified Firebase token."""
    firebase_claims = claims.get("firebase") or {}
    return {
        "uid": claims.get("uid") or claims.get("sub"),
        "email": claims.get("email"),
        "emailVerified": bool(claims.get("email_verified")),
        "displayName": claims.get("name"),
        "photoUrl": claims.get("picture"),
        "provider": firebase_claims.get("sign_in_provider"),
    }
