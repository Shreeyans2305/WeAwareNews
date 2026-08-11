"""
WeAware News API
Exposes corroborated story clusters for external consumption (e.g. Make.com automation).

Authentication: x-api-key header (value stored in Secret Manager as 'api-key').
Database: Cloud SQL Postgres via Cloud SQL Python Connector + pg8000 (no SQLAlchemy needed).
"""
import os
import logging
from contextlib import contextmanager
from typing import List, Optional

from fastapi import FastAPI, Depends, HTTPException, Header, Response
from pydantic import BaseModel
from google.cloud import secretmanager
from google.cloud.sql.connector import Connector, IPTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="WeAware News API")

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
    Return the oldest unposted corroborated story (source_count >= MIN_SOURCES).
    Returns 204 No Content if no eligible stories remain.
    """
    min_sources = int(os.getenv("WEAWARE_MIN_SOURCES", "2"))

    cursor = db.cursor()
    cursor.execute(
        """
        SELECT s.story_id, s.source_count
        FROM stories s
        WHERE s.source_count >= %s AND s.posted = false
          AND EXISTS (SELECT 1 FROM items i WHERE i.story_id = s.story_id AND i.image_url IS NOT NULL)
        ORDER BY s.recency DESC
        LIMIT 1
        """,
        (min_sources,),
    )
    row = cursor.fetchone()
    if not row:
        cursor.close()
        return Response(status_code=204)

    story_id = row[0]
    source_count = row[1]

    cursor.execute(
        """
        SELECT source_name, title, url, raw_text, region, image_url
        FROM items
        WHERE story_id = %s
        """,
        (story_id,),
    )
    articles_rows = cursor.fetchall()
    cursor.close()

    articles = []
    image_url = None
    for r in articles_rows:
        # columns: source_name, title, url, raw_text, region, image_url
        if not image_url and r[5]:
            image_url = r[5]
        articles.append(Article(
            source_name=r[0],
            title=r[1],
            url=r[2],
            snippet=r[3],  # Return the full text instead of just 200 chars
            region=r[4],
        ))

    return StoryResponse(
        story_id=story_id,
        source_count=source_count,
        articles=articles,
        image_url=image_url,
    )


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
