"""Generate evidence-grounded articles from ingested story clusters using Vertex AI Gemini."""

import json
import logging
import os
import re
from typing import Any, Optional

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS editorial_articles (
    article_id TEXT PRIMARY KEY,
    story_id TEXT NOT NULL,
    source_fingerprint TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'processing',
    topic TEXT,
    title TEXT,
    summary TEXT,
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
);
CREATE INDEX IF NOT EXISTS idx_editorial_articles_publication
    ON editorial_articles(status, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_editorial_articles_topic
    ON editorial_articles(topic, published_at DESC);
"""

INTERNAL_SOURCE_REFS = re.compile(r"\[(?:[0-9a-f]{40,64}(?:\s*,\s*)?)+\]", re.IGNORECASE)


def _clean_article_text(value: str) -> str:
    value = INTERNAL_SOURCE_REFS.sub("", value)
    value = re.sub(r"\s+([,.;:!?])", r"\1", value)
    return re.sub(r"[ \t]{2,}", " ", value).strip()

AGENT_PROMPTS = {
    "evidence": """You are an evidence analyst for a neutral news desk. Use only the supplied source records. Extract verifiable claims, dates, numbers, named entities, and disagreements. Mark unsupported assertions as uncertain. Return JSON with keys: event, key_facts (array of {claim, source_ids, confidence}), disagreements (array of {claim, source_ids}), missing_context (array). Do not write the article.""",
    "crosscheck": """You are an independent cross-source reviewer. Compare the evidence packet with the original source records. Identify which facts are corroborated, source-specific, disputed, or unsupported. Never treat repetition from the same outlet as independent corroboration. Return JSON with keys: verified_facts (array of {claim, source_ids}), source_assessments (array of {source_id, stance, note}), flagged_claims (array of {claim, reason}), consensus (integer 0-100), concerns (array). Use stance values agree, context, dispute.""",
    "writer": """You are a careful, neutral news writer. Write a concise, readable article grounded only in the supplied verified evidence and source records. Attribute claims and preserve genuine disagreement. Do not add facts, invented quotes, invented outlets, or editorial conclusions. Never put source IDs, hashes, or bracketed source references in the title, summary, or body; name outlets in ordinary prose when attribution is needed because linked source records are displayed separately. Return JSON with keys: title, topic (one of World, Politics, Business, Markets, Technology, AI, Climate, Science, Health, Culture, Good News, Other), summary, body (array of 3-7 readable paragraphs), image_source_id (source id or null).""",
    "editor": """You are the final independent publication editor. Compare the proposed article against only the source records and verified evidence. Reject invented or unsupported facts, missing material attribution, misleading certainty, loaded language, and unresolved contradictions. Return JSON with keys: approved (boolean), issues (array of strings), flagged_claims (array of {claim, reason}), revised_summary (string or null). Do not rewrite unsupported claims into facts.""",
}


def _json_response(client: genai.Client, model: str, prompt: str, payload: Any, usage: dict) -> dict:
    response = client.models.generate_content(
        model=model,
        contents=f"{prompt}\n\nINPUT JSON:\n{json.dumps(payload, ensure_ascii=False)}",
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2,
        ),
    )
    metadata = getattr(response, "usage_metadata", None)
    if metadata:
        usage["input_tokens"] += int(getattr(metadata, "prompt_token_count", 0) or 0)
        usage["output_tokens"] += int(getattr(metadata, "candidates_token_count", 0) or 0)
        usage["thinking_tokens"] += int(getattr(metadata, "thoughts_token_count", 0) or 0)
    text = (response.text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError("Gemini agent returned a non-object JSON response")
    return result


def _load_candidate_ids(conn, limit: int) -> list[str]:
    excluded_story_ids = [value.strip() for value in os.getenv("WEAWARE_ARTICLE_EXCLUDE_STORY_IDS", "").split(",") if value.strip()]
    only_new = os.getenv("WEAWARE_ARTICLE_ONLY_NEW", "false").lower() == "true"
    existing_article_filter = (
        "AND NOT EXISTS (SELECT 1 FROM editorial_articles a WHERE a.story_id=s.story_id)"
        if only_new else
        "AND (NOT EXISTS (SELECT 1 FROM editorial_articles a WHERE a.story_id=s.story_id) "
        "OR EXISTS (SELECT 1 FROM editorial_articles a WHERE a.story_id=s.story_id "
        "AND (a.status='failed' OR (a.status='processing' AND a.updated_at < NOW() - INTERVAL '1 hour'))))"
    )
    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT s.story_id FROM stories s
               WHERE s.source_count >= %s
                 AND NOT (s.story_id = ANY(%s))
                 {existing_article_filter}
                 AND (SELECT COUNT(DISTINCT i.source_id) FROM items i
                      WHERE i.story_id=s.story_id
                        AND COALESCE(i.raw_text,'') <> ''
                        AND COALESCE(i.is_social,0)=0
                        AND LOWER(COALESCE(i.source_type,'')) NOT IN ('bluesky','social')) >= %s
               ORDER BY s.source_count DESC, s.recency DESC LIMIT %s""",
            (int(os.getenv("WEAWARE_ARTICLE_MIN_SOURCES", "2")), excluded_story_ids,
             int(os.getenv("WEAWARE_ARTICLE_MIN_TEXT_SOURCES", "2")), limit),
        )
        return [row[0] for row in cur.fetchall()]


def _tracked_spend(conn) -> float:
    with conn.cursor() as cur:
        cur.execute("SELECT COALESCE(SUM(estimated_cost_usd), 0) FROM editorial_articles")
        total = float(cur.fetchone()[0] or 0)
    # End the read transaction before waiting on the next remote Gemini call.
    conn.commit()
    return total


def _load_story(conn, story_id: str) -> tuple[dict, list[dict]]:
    with conn.cursor() as cur:
        cur.execute("SELECT source_count, recency FROM stories WHERE story_id=%s", (story_id,))
        story = cur.fetchone()
        if not story:
            raise ValueError("story cluster disappeared")
        cur.execute(
            """SELECT item_hash, source_name, title, url, raw_text, published_at, region, image_url
               FROM items WHERE story_id=%s AND COALESCE(raw_text,'') <> ''
                 AND COALESCE(is_social,0)=0
                 AND LOWER(COALESCE(source_type,'')) NOT IN ('bluesky','social')
               ORDER BY published_at DESC NULLS LAST LIMIT 8""", (story_id,)
        )
        cols = [d[0] for d in cur.description]
        sources = [dict(zip(cols, row)) for row in cur.fetchall()]
    import hashlib
    source_fingerprint = hashlib.sha256(
        "\n".join(sorted({source["url"] for source in sources})).encode("utf-8")
    ).hexdigest()
    return {"source_count": story[0], "recency": str(story[1]), "source_fingerprint": source_fingerprint}, sources


def _safe_image_url(sources: list[dict], selected_id: Optional[str]) -> Optional[str]:
    selected = next((s for s in sources if s["item_hash"] == selected_id), None)
    candidates = ([selected] if selected else []) + sources
    for source in candidates:
        url = source.get("image_url")
        if url and url.startswith("https://"):
            return url
    return None


def _save_processing(conn, story_id: str, source_fingerprint: str) -> Optional[str]:
    article_id = f"article-{source_fingerprint[:32]}"
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO editorial_articles(article_id,story_id,source_fingerprint,status,agent_trace)
               VALUES (%s,%s,%s,'processing','{}'::jsonb)
               ON CONFLICT(source_fingerprint) DO UPDATE SET story_id=EXCLUDED.story_id,
               status='processing', failure_reason=NULL, updated_at=NOW()
               WHERE editorial_articles.status <> 'published'
               RETURNING article_id""", (article_id, story_id, source_fingerprint),
        )
        row = cur.fetchone()
    conn.commit()
    return row[0] if row else None


def _save_failure(conn, story_id: str, reason: str, trace: dict, estimated_cost: float) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """UPDATE editorial_articles SET status='failed', failure_reason=%s, estimated_cost_usd=estimated_cost_usd + %s,
               agent_trace=%s::jsonb, updated_at=NOW() WHERE story_id=%s""",
            (reason[:2000], estimated_cost, json.dumps(trace), story_id),
        )
    conn.commit()


def process_story(conn, client: genai.Client, model: str, story_id: str, run_usage: dict) -> bool:
    trace: dict[str, Any] = {}
    usage = {"input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0}
    usage_recorded = False
    input_rate = float(os.getenv("WEAWARE_GEMINI_INPUT_USD_PER_MILLION", "1.50"))
    output_rate = float(os.getenv("WEAWARE_GEMINI_OUTPUT_USD_PER_MILLION", "7.50"))
    thinking_rate = float(os.getenv("WEAWARE_GEMINI_THINKING_USD_PER_MILLION", "7.50"))

    def estimated_cost() -> float:
        return (usage["input_tokens"] * input_rate + usage["output_tokens"] * output_rate + usage["thinking_tokens"] * thinking_rate) / 1_000_000

    budget_limit = float(os.getenv("WEAWARE_GEMINI_BUDGET_USD", "6.0"))
    # Reserve a conservative amount for one in-flight model call because provider
    # usage is only known after the response returns.
    call_reserve = float(os.getenv("WEAWARE_GEMINI_CALL_RESERVE_USD", "0.25"))

    def request_json(prompt: str, payload: Any) -> dict:
        if budget_limit > 0 and _tracked_spend(conn) + estimated_cost() + call_reserve > budget_limit:
            raise RuntimeError("Gemini spend guard reached before next model call")
        return _json_response(client, model, prompt, payload, usage)

    try:
        story, sources = _load_story(conn, story_id)
        article_id = _save_processing(conn, story_id, story["source_fingerprint"])
        if article_id is None:
            return True  # This evidence set has already been published.
        if len(sources) < int(os.getenv("WEAWARE_ARTICLE_MIN_TEXT_SOURCES", "2")):
            raise ValueError("not enough source text for independent review")
        source_records = [
            {**source, "raw_text": (source.get("raw_text") or "")[:8000]}
            for source in sources
        ]
        packet = {"story": story, "sources": source_records}
        trace["evidence"] = request_json(AGENT_PROMPTS["evidence"], packet)
        trace["crosscheck"] = request_json(
            AGENT_PROMPTS["crosscheck"],
            {"evidence": trace["evidence"], "sources": source_records},
        )
        draft = request_json(
            AGENT_PROMPTS["writer"],
            {"evidence": trace["evidence"], "crosscheck": trace["crosscheck"], "sources": source_records},
        )
        trace["editor"] = request_json(
            AGENT_PROMPTS["editor"],
            {"draft": draft, "evidence": trace["evidence"], "crosscheck": trace["crosscheck"], "sources": source_records},
        )
        run_usage["input_tokens"] += usage["input_tokens"]
        run_usage["output_tokens"] += usage["output_tokens"]
        run_usage["thinking_tokens"] += usage["thinking_tokens"]
        usage_recorded = True
        trace["cost_tracking"] = {**usage, "estimated_cost_usd": estimated_cost()}
        if not trace["editor"].get("approved"):
            raise ValueError("editor rejected draft: " + "; ".join(trace["editor"].get("issues", [])[:8]))
        title = str(draft.get("title") or "").strip()
        summary = _clean_article_text(str(trace["editor"].get("revised_summary") or draft.get("summary") or ""))
        body = [_clean_article_text(str(p)) for p in draft.get("body", []) if _clean_article_text(str(p))]
        if not title or not summary or len(body) < 2:
            raise ValueError("editor-approved draft is missing required article fields")
        source_assessments = {x.get("source_id"): x for x in trace["crosscheck"].get("source_assessments", [])}
        article_sources = []
        for source in sources:
            assessment = source_assessments.get(source["item_hash"], {})
            article_sources.append({
                "outlet": source["source_name"], "url": source["url"],
                "stance": assessment.get("stance", "context"),
                "note": assessment.get("note", "Source included in the cross-check."),
            })
        words = sum(len(p.split()) for p in body)
        consensus = max(0, min(100, int(trace["crosscheck"].get("consensus", 0))))
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE editorial_articles SET status='published', topic=%s, title=%s, summary=%s,
                   body=%s::jsonb, image_url=%s, sources=%s::jsonb, flagged_claims=%s::jsonb,
                   consensus=%s, read_mins=%s, agent_trace=%s::jsonb, estimated_cost_usd=estimated_cost_usd + %s, failure_reason=NULL,
                   updated_at=NOW(), published_at=NOW() WHERE article_id=%s""",
                (str(draft.get("topic") or "Other"), title, summary, json.dumps(body),
                 _safe_image_url(sources, draft.get("image_source_id")), json.dumps(article_sources),
                 json.dumps(trace["editor"].get("flagged_claims") or trace["crosscheck"].get("flagged_claims") or []),
                 consensus, max(1, (words + 219) // 220), json.dumps(trace), estimated_cost(), article_id),
            )
        conn.commit()
        logger.info("Published generated article %s", article_id)
        return True
    except Exception as exc:
        conn.rollback()
        if not usage_recorded:
            run_usage["input_tokens"] += usage["input_tokens"]
            run_usage["output_tokens"] += usage["output_tokens"]
            run_usage["thinking_tokens"] += usage["thinking_tokens"]
        trace["cost_tracking"] = {**usage, "estimated_cost_usd": estimated_cost()}
        logger.exception("Article generation failed for %s", story_id)
        _save_failure(conn, story_id, str(exc), trace, estimated_cost())
        return False


def run_pipeline(limit: int = 20) -> dict:
    """Process the newest eligible story clusters; uses Application Default Credentials."""
    from google.cloud import secretmanager
    import psycopg2

    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
    model = os.getenv("WEAWARE_GEMINI_MODEL", "gemini-3.8-flash")
    client = genai.Client(vertexai=True, project=project, location=location)
    password = os.getenv("DB_PASS")
    if not password:
        secret_client = secretmanager.SecretManagerServiceClient()
        secret_name = f"projects/{project}/secrets/db-password/versions/latest"
        password = secret_client.access_secret_version(request={"name": secret_name}).payload.data.decode("UTF-8")
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "5433")),
        dbname=os.getenv("DB_NAME", "weaware"),
        user=os.getenv("DB_USER", "weaware_user"),
        password=password,
        connect_timeout=10,
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=5,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(SCHEMA)
        conn.commit()
        story_ids = _load_candidate_ids(conn, limit)
        usage = {"input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0}
        published = sum(process_story(conn, client, model, story_id, usage) for story_id in story_ids)
        estimated_cost = (
            usage["input_tokens"] * float(os.getenv("WEAWARE_GEMINI_INPUT_USD_PER_MILLION", "1.50"))
            + usage["output_tokens"] * float(os.getenv("WEAWARE_GEMINI_OUTPUT_USD_PER_MILLION", "7.50"))
            + usage["thinking_tokens"] * float(os.getenv("WEAWARE_GEMINI_THINKING_USD_PER_MILLION", "7.50"))
        ) / 1_000_000
        return {"selected": len(story_ids), "published": published, "failed": len(story_ids) - published,
                **usage, "estimated_cost_usd": round(estimated_cost, 6)}
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_pipeline(int(os.getenv("WEAWARE_ARTICLE_BATCH_SIZE", "20")))
    print(json.dumps(result))
