"""
WeAware News API
Exposes corroborated story clusters for external consumption (e.g. Make.com automation).

Authentication: x-api-key header (value stored in Secret Manager as 'api-key').
Database: Cloud SQL Postgres via Cloud SQL Python Connector + pg8000 (no SQLAlchemy needed).
"""
import os
import json
import re
import base64
import hashlib
import hmac
import html
import logging
import urllib.request
import urllib.error
from contextlib import contextmanager
from datetime import timedelta
from typing import List, Optional, Literal
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
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS newsletter_preferences (
                    firebase_uid TEXT PRIMARY KEY,
                    email TEXT NOT NULL,
                    topics TEXT[] NOT NULL DEFAULT '{}',
                    cadence TEXT NOT NULL CHECK (cadence IN ('daily', 'weekly')),
                    consented_at TIMESTAMPTZ NOT NULL,
                    unsubscribed_at TIMESTAMPTZ,
                    next_delivery_at TIMESTAMPTZ NOT NULL,
                    last_sent_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_newsletter_due ON newsletter_preferences(next_delivery_at) WHERE unsubscribed_at IS NULL")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS newsletter_deliveries (
                    delivery_id BIGSERIAL PRIMARY KEY,
                    firebase_uid TEXT NOT NULL REFERENCES newsletter_preferences(firebase_uid) ON DELETE CASCADE,
                    window_start TIMESTAMPTZ NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('sending', 'sent', 'failed')),
                    article_ids TEXT[] NOT NULL DEFAULT '{}',
                    attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    sent_at TIMESTAMPTZ,
                    error_code TEXT,
                    UNIQUE(firebase_uid, window_start)
                )
            """)
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


class NewsletterPreferenceInput(BaseModel):
    topics: List[str]
    cadence: Literal["daily", "weekly"]
    consent: bool


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


def _newsletter_user(claims: dict) -> tuple[str, str]:
    uid = claims.get("uid") or claims.get("sub")
    email = claims.get("email")
    if not uid or not email:
        raise HTTPException(status_code=403, detail="A verified Firebase email is required")
    if not claims.get("email_verified"):
        raise HTTPException(status_code=403, detail="Verify your email address before subscribing")
    return str(uid), str(email).strip().lower()


def _newsletter_unsubscribe_secret() -> Optional[str]:
    return os.getenv("NEWSLETTER_UNSUBSCRIBE_SECRET")


def _newsletter_unsubscribe_token(uid: str) -> str:
    secret = _newsletter_unsubscribe_secret()
    if not secret:
        raise RuntimeError("NEWSLETTER_UNSUBSCRIBE_SECRET is not configured")
    encoded_uid = base64.urlsafe_b64encode(uid.encode()).decode().rstrip("=")
    signature = hmac.new(secret.encode(), encoded_uid.encode(), hashlib.sha256).hexdigest()
    return f"{encoded_uid}.{signature}"


def _decode_unsubscribe_token(token: str) -> str:
    secret = _newsletter_unsubscribe_secret()
    if not secret or "." not in token:
        raise HTTPException(status_code=400, detail="Invalid unsubscribe link")
    encoded_uid, signature = token.rsplit(".", 1)
    expected = hmac.new(secret.encode(), encoded_uid.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=400, detail="Invalid unsubscribe link")
    try:
        return base64.urlsafe_b64decode(encoded_uid + "=" * (-len(encoded_uid) % 4)).decode()
    except Exception as error:
        raise HTTPException(status_code=400, detail="Invalid unsubscribe link") from error


@app.get("/api/v1/newsletters/preferences")
def get_newsletter_preferences(claims: dict = Depends(verify_firebase_user), db=Depends(get_db)):
    uid, email = _newsletter_user(claims)
    cursor = db.cursor()
    cursor.execute("""
        SELECT email, topics, cadence, consented_at, unsubscribed_at, next_delivery_at
        FROM newsletter_preferences WHERE firebase_uid=%s
    """, (uid,))
    row = cursor.fetchone()
    cursor.close()
    if not row:
        return {"subscribed": False, "email": email, "topics": [], "cadence": "weekly", "consentedAt": None}
    return {
        "subscribed": row[4] is None,
        "email": email,
        "topics": list(row[1] or []),
        "cadence": row[2],
        "consentedAt": row[3].isoformat() if row[3] else None,
        "nextDeliveryAt": row[5].isoformat() if row[5] else None,
    }


@app.put("/api/v1/newsletters/preferences")
def save_newsletter_preferences(
    preference: NewsletterPreferenceInput,
    claims: dict = Depends(verify_firebase_user),
    db=Depends(get_db),
):
    uid, email = _newsletter_user(claims)
    if not preference.consent:
        raise HTTPException(status_code=400, detail="Explicit newsletter consent is required")
    topics = sorted({topic.strip() for topic in preference.topics if topic and topic.strip()})
    if not topics or len(topics) > 20 or any(len(topic) > 80 for topic in topics):
        raise HTTPException(status_code=400, detail="Choose between 1 and 20 valid topics")
    cursor = db.cursor()
    cursor.execute("SELECT DISTINCT topic FROM editorial_articles WHERE status='published' AND topic IS NOT NULL")
    available = {row[0].lower(): row[0] for row in cursor.fetchall()}
    normalized = []
    for topic in topics:
        if topic.lower() not in available:
            cursor.close()
            raise HTTPException(status_code=400, detail=f"Unknown newsletter topic: {topic}")
        normalized.append(available[topic.lower()])
    interval = timedelta(days=1 if preference.cadence == "daily" else 7)
    cursor.execute("""
        INSERT INTO newsletter_preferences
            (firebase_uid, email, topics, cadence, consented_at, unsubscribed_at, next_delivery_at, updated_at)
        VALUES (%s, %s, %s, %s, NOW(), NULL, NOW() + %s, NOW())
        ON CONFLICT (firebase_uid) DO UPDATE SET
            email=EXCLUDED.email, topics=EXCLUDED.topics, cadence=EXCLUDED.cadence,
            consented_at=NOW(), unsubscribed_at=NULL, next_delivery_at=NOW() + %s,
            updated_at=NOW()
        RETURNING email, topics, cadence, consented_at, next_delivery_at
    """, (uid, email, normalized, preference.cadence, interval, interval))
    row = cursor.fetchone()
    db.commit()
    cursor.close()
    return {"subscribed": True, "email": row[0], "topics": list(row[1]), "cadence": row[2],
            "consentedAt": row[3].isoformat(), "nextDeliveryAt": row[4].isoformat()}


@app.get("/api/v1/newsletters/unsubscribe")
@app.post("/api/v1/newsletters/unsubscribe")
def unsubscribe_newsletter(token: str = Query(..., min_length=20, max_length=512), db=Depends(get_db)):
    uid = _decode_unsubscribe_token(token)
    cursor = db.cursor()
    cursor.execute("UPDATE newsletter_preferences SET unsubscribed_at=COALESCE(unsubscribed_at, NOW()), updated_at=NOW() WHERE firebase_uid=%s", (uid,))
    db.commit()
    cursor.close()
    return Response(
        content="<!doctype html><html><title>WeAware</title><body style='font:16px Arial,sans-serif;max-width:40rem;margin:4rem auto;padding:1rem'><h1>You are unsubscribed</h1><p>No further WeAware newsletter emails will be sent to this account.</p></body></html>",
        media_type="text/html",
    )


@app.post("/api/v1/newsletters/preferences/unsubscribe")
def unsubscribe_from_account(claims: dict = Depends(verify_firebase_user), db=Depends(get_db)):
    uid, _ = _newsletter_user(claims)
    cursor = db.cursor()
    cursor.execute("UPDATE newsletter_preferences SET unsubscribed_at=COALESCE(unsubscribed_at, NOW()), updated_at=NOW() WHERE firebase_uid=%s", (uid,))
    db.commit()
    cursor.close()
    return {"status": "unsubscribed"}


def _send_resend_email(to_email: str, subject: str, html_body: str, text_body: str, unsubscribe_url: str, idempotency_key: str) -> None:
    api_key = os.getenv("RESEND_API_KEY")
    sender = os.getenv("NEWSLETTER_FROM_EMAIL")
    if not api_key or not sender:
        raise RuntimeError("Newsletter delivery is disabled: configure RESEND_API_KEY and NEWSLETTER_FROM_EMAIL")
    payload = json.dumps({
        "from": sender,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
        "text": text_body,
        "headers": {"List-Unsubscribe": f"<{unsubscribe_url}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"},
    }).encode()
    request = urllib.request.Request(
        "https://api.resend.com/emails", data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Idempotency-Key": idempotency_key}, method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status >= 300:
                raise RuntimeError(f"Resend returned HTTP {response.status}")
    except urllib.error.HTTPError as error:
        # Never include response bodies, which can contain recipient/provider data, in logs or DB.
        raise RuntimeError(f"Resend returned HTTP {error.code}") from error


def _newsletter_article_link(article: dict) -> Optional[str]:
    for source in article.get("sources") or []:
        if not isinstance(source, dict):
            continue
        candidate = source.get("url")
        if candidate and urlparse(str(candidate)).scheme in ("http", "https"):
            return str(candidate)
    return None


def _dispatch_newsletters(db, limit: int = 100) -> dict:
    required_config = ("RESEND_API_KEY", "NEWSLETTER_FROM_EMAIL", "NEWSLETTER_UNSUBSCRIBE_SECRET", "NEWSLETTER_API_ORIGIN")
    if any(not os.getenv(key) for key in required_config):
        return {"status": "disabled", "sent": 0, "failed": 0, "reason": "mail_provider_or_unsubscribe_not_configured"}
    api_origin = os.getenv("NEWSLETTER_API_ORIGIN", "").rstrip("/")
    cursor = db.cursor()
    cursor.execute("""
        SELECT firebase_uid, email, topics, cadence, next_delivery_at, last_sent_at
        FROM newsletter_preferences
        WHERE unsubscribed_at IS NULL AND next_delivery_at <= NOW()
        ORDER BY next_delivery_at
        FOR UPDATE SKIP LOCKED
        LIMIT %s
    """, (limit,))
    subscribers = cursor.fetchall()
    sent = failed = 0
    for uid, email, topics, cadence, due_at, last_sent_at in subscribers:
        # Exact scheduled due timestamp is the idempotency key. Locking the preference
        # row serializes concurrent dispatchers; the unique constraint is a second guard.
        cursor.execute("""
            INSERT INTO newsletter_deliveries(firebase_uid, window_start, status)
            VALUES (%s, %s, 'sending')
            ON CONFLICT (firebase_uid, window_start) DO UPDATE SET
                status='sending', attempted_at=NOW(), error_code=NULL
            WHERE newsletter_deliveries.status <> 'sent'
            RETURNING delivery_id
        """, (uid, due_at))
        claim = cursor.fetchone()
        if not claim:
            continue
        delivery_id = claim[0]
        cursor.execute(f"""
            SELECT {_ARTICLE_FIELDS} FROM editorial_articles
            WHERE status='published' AND LOWER(topic)=ANY(%s)
              AND published_at > COALESCE(%s, NOW() - (%s * INTERVAL '1 day'))
            ORDER BY published_at DESC NULLS LAST LIMIT 8
        """, ([topic.lower() for topic in (topics or [])], last_sent_at, 1 if cadence == "daily" else 7))
        articles = [_article_dict(row) for row in cursor.fetchall()]
        if not articles:
            cursor.execute("UPDATE newsletter_deliveries SET status='sent', sent_at=NOW(), article_ids='{}' WHERE delivery_id=%s", (delivery_id,))
            cursor.execute("""
                UPDATE newsletter_preferences SET next_delivery_at=NOW() + %s, last_sent_at=NOW(), updated_at=NOW()
                WHERE firebase_uid=%s
            """, (timedelta(days=1 if cadence == "daily" else 7), uid))
            continue
        try:
            unsubscribe_url = f"{api_origin}/api/v1/newsletters/unsubscribe?token={_newsletter_unsubscribe_token(uid)}"
            title = "Your WeAware briefing"
            rows_html_parts = []
            rows_text_parts = []
            for article in articles:
                headline = html.escape(article["title"])
                source_url = _newsletter_article_link(article)
                headline_html = (
                    f'<a href="{html.escape(source_url, quote=True)}" style="color:#171717;font-size:19px;font-weight:bold">{headline}</a>'
                    if source_url else f"<strong>{headline}</strong>"
                )
                rows_html_parts.append(
                    f'<li style="margin:0 0 22px">{headline_html}'
                    f'<p style="color:#555;line-height:1.55">{html.escape(article["summary"])}</p>'
                    f'<small>{html.escape(article["topic"])} · {article["consensus"]}% consensus · {article["readMins"]} min</small></li>'
                )
                rows_text_parts.append("\n".join((article["title"], article["summary"], source_url or "")))
            rows_html = "".join(rows_html_parts)
            html_body = f'<div style="max-width:640px;margin:auto;font:16px/1.5 Arial,sans-serif"><h1>WeAware</h1><p>Your {html.escape(cadence)} briefing, based on the topics you chose.</p><ol>{rows_html}</ol><hr><p style="font-size:12px;color:#666">You chose to receive these emails. <a href="{html.escape(unsubscribe_url, quote=True)}">Unsubscribe</a></p></div>'
            text_body = "WeAware briefing\n\n" + "\n\n".join(rows_text_parts) + f"\n\nUnsubscribe: {unsubscribe_url}"
            retry_key = hashlib.sha256(f"{uid}:{due_at.isoformat()}".encode()).hexdigest()
            _send_resend_email(email, title, html_body, text_body, unsubscribe_url, f"weaware-newsletter-{retry_key}")
            cursor.execute("UPDATE newsletter_deliveries SET status='sent', sent_at=NOW(), article_ids=%s WHERE delivery_id=%s", ([a["id"] for a in articles], delivery_id))
            cursor.execute("""
                UPDATE newsletter_preferences SET next_delivery_at=NOW() + %s, last_sent_at=NOW(), updated_at=NOW()
                WHERE firebase_uid=%s
            """, (timedelta(days=1 if cadence == "daily" else 7), uid))
            sent += 1
        except Exception as error:
            logger.warning("Newsletter delivery failed (%s)", type(error).__name__)
            cursor.execute("UPDATE newsletter_deliveries SET status='failed', error_code=%s WHERE delivery_id=%s", (type(error).__name__[:80], delivery_id))
            failed += 1
    db.commit()
    cursor.close()
    return {"status": "ok", "sent": sent, "failed": failed}


@app.post("/api/v1/newsletters/dispatch")
def dispatch_newsletters(x_newsletter_dispatch_token: Optional[str] = Header(None), db=Depends(get_db)):
    configured_token = os.getenv("NEWSLETTER_DISPATCH_TOKEN")
    if not configured_token or not x_newsletter_dispatch_token or not hmac.compare_digest(configured_token, x_newsletter_dispatch_token):
        raise HTTPException(status_code=401, detail="Invalid scheduler credential")
    return _dispatch_newsletters(db)
