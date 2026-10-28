"""Create a review-only daily podcast script from published WeAware articles."""

import json
import logging
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

HOST_ONE_NAME = os.getenv("WEAWARE_PODCAST_HOST_ONE_NAME", "Rhea").strip() or "Rhea"
HOST_TWO_NAME = os.getenv("WEAWARE_PODCAST_HOST_TWO_NAME", "Jay").strip() or "Jay"
HOST_ONE_LABEL = HOST_ONE_NAME.upper()
HOST_TWO_LABEL = HOST_TWO_NAME.upper()

SCRIPT_PROMPT = f"""You are the script editor for WeAware Daily Brief, a neutral news podcast
hosted by two presenters, {HOST_ONE_NAME} and {HOST_TWO_NAME}. Write a natural, spoken
conversation between them using only the supplied published articles. In the opening
welcome, have each presenter introduce themselves by first name once. Format every spoken
turn exactly as `{HOST_ONE_LABEL}: ...` or `{HOST_TWO_LABEL}: ...`, with one turn per
paragraph. Alternate speakers often
and let them respond to each other's points, ask brief clarifying questions, and hand off
between stories. Use warm, restrained human delivery: contractions, clear transitions,
short sentences, and occasional concise reactions to the reported facts. Do not invent
personal experiences, opinions, facts, quotes, people, or causal claims. Attribute
contested claims and preserve caveats; distinguish confirmed information from allegations
or projections. Include a short welcome, three concise story segments, each selected
article's consensus score, at least one flagged claim with its caveat when available, and
a source-aware closing. No stage directions, sound effects, markdown, or unspoken labels.
Use pronounceable numbers. Return JSON only with title, description, topic, and script.
Aim for 1,300-1,500 words. This is a DRAFT for editor review; do not imply it has been
independently updated beyond the included articles."""


def _connect():
    from google.cloud import secretmanager
    import psycopg2

    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    password = os.getenv("DB_PASS")
    if not password:
        client = secretmanager.SecretManagerServiceClient()
        password = client.access_secret_version(
            request={"name": f"projects/{project}/secrets/db-password/versions/latest"}
        ).payload.data.decode("utf-8")
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"), port=int(os.getenv("DB_PORT", "5433")),
        dbname=os.getenv("DB_NAME", "weaware"), user=os.getenv("DB_USER", "weaware_user"),
        password=password, connect_timeout=10,
    )


def create_daily_draft() -> dict:
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is required")
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    episode_id = f"daily-brief-{today:%Y%m%d}"
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM podcast_episodes WHERE episode_id=%s", (episode_id,))
            if cur.fetchone():
                return {"episode_id": episode_id, "status": "already_exists"}
            cur.execute("""SELECT article_id,title,topic,summary,body,sources,flagged_claims,consensus
                           FROM editorial_articles WHERE status='published'
                           ORDER BY published_at DESC NULLS LAST LIMIT 3""")
            rows = cur.fetchall()
        if not rows:
            return {"status": "no_published_articles"}

        with conn.cursor() as cur:
            cur.execute("""SELECT
                         (SELECT COALESCE(SUM(estimated_cost_usd),0) FROM editorial_articles) +
                         (SELECT COALESCE(SUM(estimated_cost_usd),0) FROM podcast_episodes)""")
            tracked_spend = float(cur.fetchone()[0] or 0)
        budget = float(os.getenv("WEAWARE_GEMINI_BUDGET_USD", "10"))
        if budget > 0 and tracked_spend + float(os.getenv("WEAWARE_GEMINI_CALL_RESERVE_USD", "0.25")) > budget:
            return {"episode_id": episode_id, "status": "spend_guard_reached"}

        articles = []
        source_urls = []
        for article_id, title, topic, summary, body, sources, flags, consensus in rows:
            def parse_json(value):
                if isinstance(value, str):
                    try:
                        return json.loads(value)
                    except ValueError:
                        return []
                return value or []

            body, sources, flags = parse_json(body), parse_json(sources), parse_json(flags)
            source_urls.extend(
                source["url"] for source in sources
                if isinstance(source, dict) and source.get("url", "").startswith("https://")
            )
            articles.append({
                "id": article_id, "title": title, "topic": topic, "summary": summary,
                "body": body, "sources": sources, "flagged_claims": flags,
                "consensus": consensus,
            })

        model = os.getenv("WEAWARE_PODCAST_MODEL", os.getenv("WEAWARE_GEMINI_MODEL", "gemini-3.8-flash"))
        client = genai.Client(vertexai=True, project=project, location=os.getenv("GOOGLE_CLOUD_LOCATION", "global"))
        response = client.models.generate_content(
            model=model,
            contents=f"{SCRIPT_PROMPT}\n\nPUBLISHED ARTICLES:\n{json.dumps(articles, ensure_ascii=False)}",
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2),
        )
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (response.text or "").strip())
        draft = json.loads(text)
        title, description, script = (str(draft.get(key) or "").strip() for key in ("title", "description", "script"))
        if (not title or not description or len(script.split()) < 200
                or not re.search(rf"(?im)^{re.escape(HOST_ONE_LABEL)}:", script)
                or not re.search(rf"(?im)^{re.escape(HOST_TWO_LABEL)}:", script)):
            raise ValueError("Generated podcast script did not meet the minimum content requirements")

        usage = getattr(response, "usage_metadata", None)
        input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0) if usage else 0
        output_tokens = int(getattr(usage, "candidates_token_count", 0) or 0) if usage else 0
        input_rate = float(os.getenv("WEAWARE_GEMINI_INPUT_USD_PER_MILLION", "1.50"))
        output_rate = float(os.getenv("WEAWARE_GEMINI_OUTPUT_USD_PER_MILLION", "7.50"))
        cost = (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO podcast_episodes
                           (episode_id,title,description,topic,script,source_urls,estimated_cost_usd,status)
                           VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,'draft')""",
                        (episode_id, title, description, str(draft.get("topic") or "Daily Brief"),
                         script, json.dumps(list(dict.fromkeys(source_urls))), cost))
        conn.commit()
        logger.info("Saved podcast draft %s for editor review", episode_id)
        return {"episode_id": episode_id, "status": "draft", "script_words": len(script.split()),
                "estimated_cost_usd": round(cost, 6)}
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(create_daily_draft()))
