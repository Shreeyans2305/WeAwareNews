"""
WeAware Video API - FastAPI Service (Option A: weaware-video-api).
Exposes candidate retrieval, atomic claiming, status reporting, HMAC review,
and Make.com publishing endpoints.
"""

import os
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

from fastapi import FastAPI, Depends, HTTPException, Header, Response, Query, Request
from fastapi.responses import HTMLResponse
import psycopg2.extras

from video.api.models import (
    VideoCandidateResponse,
    CandidateArticle,
    ClaimRequest,
    ClaimResponse,
    StatusUpdateRequest,
    ReviewCommitRequest,
    NextApprovedVideoResponse,
)
from video.api.security import (
    verify_api_key,
    verify_review_token,
    generate_review_token,
)
from video.api.db import get_db_connection, get_dict_cursor
from video.pipeline.text_utils import clamp_caption

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("weaware-video-api")

app = FastAPI(
    title="WeAware Late Night Video API",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


def canonicalize_url(url: Optional[str]) -> str:
    """
    Canonicalizes a URL for deduplication:
    - Lowercase scheme and netloc (hostname)
    - Strip common tracking query params (utm_*, ref, fbclid, gclid, etc.)
    - Strip fragments (#...)
    - Normalize trailing slashes on paths
    """
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/")
        if not path and netloc:
            path = ""
        # Filter tracking params
        filtered_query = [
            (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if not (k.startswith("utm_") or k.lower() in ("ref", "fbclid", "gclid", "ocid", "cmpid"))
        ]
        filtered_query.sort()
        query_str = urlencode(filtered_query)
        return urlunparse((scheme, netloc, path, "", query_str, ""))
    except Exception:
        return url.strip().lower()


def truncate_excerpt(text: Optional[str], max_chars: int = 1200) -> str:
    if not text:
        return ""
    clean = " ".join(text.split())
    if len(clean) <= max_chars:
        return clean
    # Truncate at last word boundary
    truncated = clean[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars * 0.8:
        truncated = truncated[:last_space]
    return truncated + "..."


@app.get("/health")
def health_check(check_db: bool = False):
    if check_db:
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                    cur.fetchone()
            return {"status": "ok", "service": "weaware-video-api", "database": "connected"}
        except Exception as e:
            logger.error(f"Health DB check failed: {e}")
            raise HTTPException(status_code=503, detail="Database unhealthy")
    return {"status": "ok", "service": "weaware-video-api"}


@app.get("/healthz")
def healthz_check():
    """Liveness probe running SELECT 1 against database. No auth, no data returned."""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                cur.fetchone()
        return Response(status_code=200)
    except Exception as e:
        logger.error(f"Healthz check failed: {e}")
        raise HTTPException(status_code=503, detail="Database unhealthy")


@app.get("/stories/video-candidates", response_model=List[VideoCandidateResponse])
def get_video_candidates(
    limit: int = Query(10, ge=1, le=50),
    min_sources: int = Query(2, ge=2),
    dedupe_days: int = Query(14, ge=1, le=90),
    auth: bool = Depends(verify_api_key),
):
    """
    Returns corroborated stories without active video runs and without URL overlap
    in recent video runs (within dedupe_days).
    Applies strict item quality filtering (no paywalls, no social, clean text >= 150 chars).
    """
    with get_db_connection() as conn:
        with get_dict_cursor(conn) as cur:
            # 1. Fetch recent video runs source_urls to deduplicate against
            cur.execute(
                """
                SELECT array_agg(DISTINCT u)
                FROM (
                    SELECT unnest(source_urls) AS u
                    FROM video_runs
                    WHERE created_at >= NOW() - (%s * INTERVAL '1 day')
                      AND status NOT IN ('failed', 'rejected')
                ) sub
                """,
                (dedupe_days,),
            )
            row = cur.fetchone()
            urls_list = None
            if row:
                urls_list = row[0] if isinstance(row, (tuple, list)) else list(row.values())[0]
            recent_run_urls = {canonicalize_url(u) for u in (urls_list or []) if canonicalize_url(u)}

            # 2. Query corroborated stories with no active video runs
            cur.execute(
                """
                SELECT s.story_id, s.source_count, s.recency
                FROM stories s
                WHERE s.source_count >= %s
                  AND NOT EXISTS (
                      SELECT 1 FROM video_runs vr
                      WHERE vr.story_id = s.story_id
                        AND vr.status IN (
                            'claimed', 'scripting', 'generating_video', 'post_processing',
                            'ready_for_review', 'approved', 'publishing', 'published'
                        )
                        AND (vr.expires_at > NOW() OR vr.status IN ('ready_for_review', 'approved', 'publishing', 'published'))
                  )
                ORDER BY s.recency DESC
                LIMIT %s
                """,
                (min_sources, limit * 4),  # Fetch extra to account for item-level and URL filters
            )
            story_rows = cur.fetchall()

            candidates: List[VideoCandidateResponse] = []

            for s_row in story_rows:
                story_id = s_row["story_id"]
                source_count = s_row["source_count"]

                # Fetch eligible items for this story
                cur.execute(
                    """
                    SELECT source_name, title, url, raw_text, published_at
                    FROM items
                    WHERE story_id = %s
                      AND paywall = 0
                      AND is_social = 0
                      AND extraction_status = 'ok'
                      AND raw_text IS NOT NULL
                      AND LENGTH(TRIM(raw_text)) >= 150
                      AND title IS NOT NULL
                      AND TRIM(title) != ''
                    ORDER BY published_at DESC NULLS LAST
                    """,
                    (story_id,),
                )
                item_rows = cur.fetchall()

                # Verify >= 2 distinct publishers among surviving items
                distinct_publishers = {r["source_name"].strip() for r in item_rows if r["source_name"]}
                if len(distinct_publishers) < min_sources:
                    continue

                # Verify no URL overlap with recent runs (using canonicalized URLs)
                raw_story_urls = [r["url"].strip() for r in item_rows if r["url"]]
                canonical_story_urls = [canonicalize_url(u) for u in raw_story_urls if canonicalize_url(u)]
                if any(u in recent_run_urls for u in canonical_story_urls):
                    continue

                # Select best headline (most recent article with non-empty title)
                best_headline = item_rows[0]["title"].strip()

                articles: List[CandidateArticle] = []
                excerpts_list: List[str] = []

                for r in item_rows[:5]:  # Up to 5 articles
                    excerpt = truncate_excerpt(r["raw_text"], max_chars=1200)
                    articles.append(
                        CandidateArticle(
                            source_name=r["source_name"],
                            title=r["title"],
                            url=r["url"],
                            excerpt=excerpt,
                            published_at=str(r["published_at"]) if r["published_at"] else None,
                        )
                    )
                    excerpts_list.append(f"[{r['source_name']}] {r['title']}: {excerpt}")

                combined_text = "\n\n".join(excerpts_list)

                candidates.append(
                    VideoCandidateResponse(
                        story_id=story_id,
                        headline=best_headline,
                        source_count=len(distinct_publishers),
                        articles=articles,
                        source_urls=canonical_story_urls,
                        combined_story_text=combined_text,
                    )
                )

                if len(candidates) >= limit:
                    break

            return candidates


@app.post("/stories/{story_id}/video-claim", response_model=ClaimResponse, status_code=201)
def claim_story_for_video(
    story_id: str,
    req: ClaimRequest,
    auth: bool = Depends(verify_api_key),
):
    """
    Atomically claims a story for video generation.
    Fails expired claims first via sweeper. Returns 409 if already claimed.
    """
    run_id = str(uuid.uuid4())

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # 1. Sweeper: expire any stalled runs
            cur.execute(
                """
                UPDATE video_runs
                SET status = 'failed',
                    error_message = 'Claim expired (sweeper)',
                    updated_at = NOW()
                WHERE status IN ('claimed', 'scripting', 'generating_video', 'post_processing')
                  AND expires_at < NOW()
                """
            )

            canonical_source_urls = [canonicalize_url(u) for u in (req.source_urls or []) if canonicalize_url(u)]
            # 2. Atomic claim insert
            cur.execute(
                """
                INSERT INTO video_runs (
                    run_id, story_id, status, claim_mode, claimed_at,
                    expires_at, heartbeat_at, headline_snapshot,
                    sources_snapshot, source_urls, story_text_snapshot,
                    created_at, updated_at
                )
                VALUES (
                    %s, %s, 'claimed', %s, NOW(),
                    NOW() + (%s * INTERVAL '1 minute'), NOW(), %s,
                    %s, %s, %s,
                    NOW(), NOW()
                )
                ON CONFLICT (story_id) WHERE status IN (
                    'claimed', 'scripting', 'generating_video', 'post_processing',
                    'ready_for_review', 'approved', 'publishing', 'published'
                )
                DO NOTHING
                RETURNING run_id, claimed_at, expires_at
                """,
                (
                    run_id,
                    story_id,
                    req.claim_mode,
                    req.timeout_minutes,
                    req.headline_snapshot,
                    json.dumps(req.sources_snapshot),
                    canonical_source_urls,
                    req.story_text_snapshot,
                ),
            )
            row = cur.fetchone()
            conn.commit()

            if not row:
                raise HTTPException(
                    status_code=409,
                    detail=f"Story {story_id} is already claimed by an active video run.",
                )

            return ClaimResponse(
                run_id=str(row[0]),
                story_id=story_id,
                status="claimed",
                claimed_at=row[1].isoformat(),
                expires_at=row[2].isoformat(),
            )


@app.post("/videos/{run_id}/status")
def update_video_status(
    run_id: str,
    req: StatusUpdateRequest,
    auth: bool = Depends(verify_api_key),
):
    """
    Compare-and-set status update for a video run.
    Supports heartbeats to extend expires_at while generating clips.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Check current status
            cur.execute("SELECT status FROM video_runs WHERE run_id = %s", (run_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

            actual_status = row[0]
            if actual_status != req.expected_status:
                raise HTTPException(
                    status_code=409,
                    detail=f"Status conflict: expected '{req.expected_status}', found '{actual_status}'",
                )

            # Build update query
            update_clauses = ["status = %s", "updated_at = NOW()"]
            params = [req.new_status]

            if req.heartbeat:
                update_clauses.append("heartbeat_at = NOW()")
                update_clauses.append("expires_at = NOW() + (%s * INTERVAL '1 minute')")
                params.append(req.heartbeat_extend_minutes)

            if req.error_message is not None:
                update_clauses.append("error_message = %s")
                params.append(req.error_message)

            if req.video_gcs_uri is not None:
                update_clauses.append("video_gcs_uri = %s")
                params.append(req.video_gcs_uri)

            if req.thumbnail_gcs_uri is not None:
                update_clauses.append("thumbnail_gcs_uri = %s")
                params.append(req.thumbnail_gcs_uri)

            if req.caption is not None:
                update_clauses.append("caption = %s")
                params.append(req.caption)

            if req.hashtags is not None:
                update_clauses.append("hashtags = %s")
                params.append(req.hashtags)

            if req.script_data is not None:
                update_clauses.append("script_data = %s")
                params.append(json.dumps(req.script_data))

            if req.claims_data is not None:
                update_clauses.append("claims_data = %s")
                params.append(json.dumps(req.claims_data))

            if req.run_metadata is not None:
                update_clauses.append("run_metadata = %s")
                params.append(json.dumps(req.run_metadata))

            if req.estimated_cost_usd is not None:
                update_clauses.append("estimated_cost_usd = %s")
                params.append(req.estimated_cost_usd)

            if req.veo_seconds_used is not None:
                update_clauses.append("veo_seconds_used = %s")
                params.append(req.veo_seconds_used)

            params.append(run_id)
            params.append(req.expected_status)

            sql = f"UPDATE video_runs SET {', '.join(update_clauses)} WHERE run_id = %s AND status = %s"
            cur.execute(sql, tuple(params))
            conn.commit()

            return {"status": "ok", "run_id": run_id, "current_status": req.new_status}


# In-memory sliding window rate limiter for review endpoints
_review_rate_limit: Dict[str, List[float]] = {}


def check_rate_limit(client_ip: str, limit: int = 20, window_seconds: int = 60):
    now = time.time()
    timestamps = _review_rate_limit.setdefault(client_ip, [])
    _review_rate_limit[client_ip] = [t for t in timestamps if now - t < window_seconds]
    if len(_review_rate_limit[client_ip]) >= limit:
        raise HTTPException(status_code=429, detail="Too many review attempts. Please slow down.")
    _review_rate_limit[client_ip].append(now)


@app.get("/videos/review", response_class=HTMLResponse)
def get_video_review_page(
    request: Request,
    token: str = Query(...),
    action: Optional[str] = Query(None, pattern="^(approve|reject|review)$"),
):
    """
    Confirm page only (NO state change on GET).
    Verifies HMAC token and renders human approval confirmation UI with QA checklist.
    Provides distinct Approve and Reject POST buttons.
    """
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)

    valid, run_id, token_action, err = verify_review_token(token)
    if not valid:
        return HTMLResponse(
            status_code=400,
            content=f"<html><body style='font-family:sans-serif;padding:40px;text-align:center;'><h2>Invalid or Expired Review Token</h2><p>{err or 'Invalid token'}</p></body></html>",
        )
    if action and token_action not in ("review", action):
        return HTMLResponse(
            status_code=400,
            content="<html><body style='font-family:sans-serif;padding:40px;text-align:center;'><h2>Invalid Review Token</h2><p>Action mismatch</p></body></html>",
        )

    with get_db_connection() as conn:
        with get_dict_cursor(conn) as cur:
            cur.execute(
                "SELECT status, headline_snapshot, caption, video_gcs_uri, thumbnail_gcs_uri, run_metadata FROM video_runs WHERE run_id = %s",
                (run_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Run not found")

            current_status = row.get("status")
            if current_status != "ready_for_review":
                return HTMLResponse(
                    content=f"<html><body style='font-family:sans-serif;padding:40px;text-align:center;'><h2>Review Already Completed</h2><p>This video run is currently in status: <b>{current_status}</b>.</p></body></html>"
                )

            headline = row.get("headline_snapshot", "")
            caption = row.get("caption") or "No caption provided."
            video_uri = row.get("video_gcs_uri") or ""
            metadata = row.get("run_metadata") or {}
            transcript_checks = metadata.get("transcript_checks", [])

            transcript_html = ""
            if transcript_checks:
                transcript_items = []
                for tc in transcript_checks:
                    c_idx = tc.get("clip_index", "?")
                    spk = tc.get("speaker", "Anchor")
                    ratio = tc.get("match_ratio", 0.0)
                    mismatches = tc.get("mismatches", [])
                    
                    status_badge = f"<span style='color:#10b981;font-weight:bold;'>{ratio}% Match</span>" if ratio >= 90 else f"<span style='color:#f59e0b;font-weight:bold;'>{ratio}% Match</span>"
                    mismatch_desc = ""
                    if mismatches:
                        mismatch_desc = "<div style='color:#f87171;font-size:0.8rem;margin-top:4px;'><b>Mismatches:</b> " + "; ".join(mismatches) + "</div>"
                    else:
                        mismatch_desc = "<div style='color:#34d399;font-size:0.8rem;margin-top:4px;'>✓ 100% Word-for-Word Lip Match</div>"

                    transcript_items.append(
                        f"""<div style='background:#0f172a;border-radius:6px;padding:8px;margin-bottom:8px;'>
                            <div style='display:flex;justify-content:space-between;font-size:0.85rem;'>
                                <b>Clip {c_idx} ({spk.title()}):</b> {status_badge}
                            </div>
                            <div style='font-size:0.8rem;color:#94a3b8;margin-top:4px;'><b>Script:</b> "{tc.get('scripted', '')}"</div>
                            <div style='font-size:0.8rem;color:#cbd5e1;margin-top:2px;'><b>Heard:</b> "{tc.get('transcribed', '')}"</div>
                            {mismatch_desc}
                        </div>"""
                    )
                transcript_html = f"""
                <div style='background:#1e293b;border:1px solid #334155;border-radius:8px;padding:12px;margin-bottom:16px;'>
                    <h4 style='margin:0 0 8px 0;color:#38bdf8;font-size:0.9rem;'>Automated Spoken Dialogue Transcript Check (Gemini Flash Audio)</h4>
                    {"".join(transcript_items)}
                    <div style='font-size:0.75rem;color:#64748b;'>*Informational only — check audio/video before final approval.</div>
                </div>
                """

            is_flash_fallback = (
                metadata.get("pro_selection_reason") == "pro_unavailable_flash_fallback"
                or metadata.get("model_fallback_reason") == "pro_unavailable_flash_fallback"
                or metadata.get("pro_unavailable_flash_fallback") is True
                or metadata.get("editor_fallback_active") is True
            )

            fallback_badge_html = ""
            if is_flash_fallback:
                fallback_badge_html = """
                <div style='background:#451a03;border:1px solid #f59e0b;color:#fef3c7;border-radius:8px;padding:12px;margin-bottom:16px;font-size:0.85rem;'>
                    <div style='display:flex;align-items:center;gap:8px;'>
                        <span style='background:#f59e0b;color:#000;font-size:0.75rem;font-weight:bold;padding:2px 6px;border-radius:4px;'>editor: flash fallback</span>
                        <span style='font-family:monospace;font-size:0.8rem;color:#fcd34d;'>pro_unavailable_flash_fallback</span>
                    </div>
                    <div style='margin-top:6px;color:#fde68a;'>
                        ⚠️ <b>Notice:</b> Pro model is unavailable; Editor audit ran with stricter claim-by-claim Flash fallback. Please inspect the claims checklist extra carefully.
                    </div>
                </div>
                """

            claims_checklist_html = (
                "<label style='color:#f87171;font-weight:bold;'><input type=\"checkbox\"> ⚠️ <b>[editor: flash fallback]</b> Factual claims match corroborated source articles (inspect claim-by-claim checklist carefully)</label>"
                if is_flash_fallback
                else "<label><input type=\"checkbox\" checked> Factual claims match corroborated source articles</label>"
            )

            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>WeAware News - Review Video</title>
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; padding: 20px; display: flex; justify-content: center; }}
                    .card {{ background: #1e293b; border-radius: 12px; max-width: 560px; width: 100%; padding: 24px; box-shadow: 0 10px 25px -5px rgba(0,0,0,0.5); }}
                    h2 {{ margin-top: 0; color: #38bdf8; font-size: 1.25rem; }}
                    .caption {{ background: #0f172a; border-radius: 8px; padding: 12px; font-size: 0.9rem; color: #94a3b8; white-space: pre-wrap; margin-bottom: 16px; }}
                    .checklist {{ background: #0f172a; border-radius: 8px; padding: 12px; font-size: 0.85rem; color: #cbd5e1; margin-bottom: 20px; }}
                    .checklist h4 {{ margin: 0 0 8px 0; color: #f59e0b; font-size: 0.9rem; }}
                    .checklist label {{ display: block; margin-bottom: 6px; cursor: pointer; }}
                    .uri {{ font-size: 0.8rem; color: #64748b; margin-bottom: 20px; word-break: break-all; }}
                    .actions {{ display: flex; gap: 16px; margin-top: 20px; }}
                    .actions form {{ flex: 1; }}
                    button.approve {{ background: #10b981; color: white; border: none; padding: 14px 20px; border-radius: 8px; font-size: 1rem; font-weight: bold; width: 100%; cursor: pointer; transition: opacity 0.2s; }}
                    button.reject {{ background: #ef4444; color: white; border: none; padding: 14px 20px; border-radius: 8px; font-size: 1rem; font-weight: bold; width: 100%; cursor: pointer; transition: opacity 0.2s; }}
                    button:hover {{ opacity: 0.9; }}
                </style>
            </head>
            <body>
                <div class="card">
                    <h2>WeAware News Review</h2>
                    <p><b>Headline:</b> {headline}</p>
                    <div class="caption"><b>Caption:</b><br>{caption}</div>
                    
                    {fallback_badge_html}

                    {transcript_html}

                    <div class="checklist">
                        <h4>Pre-Publication QA Checklist</h4>
                        <label><input type="checkbox" checked> Face & voice consistent across all clips</label>
                        <label><input type="checkbox" checked> Dialogue accurately matches script</label>
                        {claims_checklist_html}
                        <label><input type="checkbox" checked> Subtitles & lower-third stay within mobile-safe margins</label>
                    </div>

                    <div class="uri"><b>Video GCS:</b> {video_uri}</div>
                    <div class="actions">
                        <form method="POST" action="/videos/review">
                            <input type="hidden" name="token" value="{token}">
                            <input type="hidden" name="action" value="approve">
                            <button type="submit" class="approve">Approve Video</button>
                        </form>
                        <form method="POST" action="/videos/review">
                            <input type="hidden" name="token" value="{token}">
                            <input type="hidden" name="action" value="reject">
                            <button type="submit" class="reject">Reject Video</button>
                        </form>
                    </div>
                </div>
            </body>
            </html>
            """
            return HTMLResponse(content=html)


@app.post("/videos/review")
async def commit_video_review(request: Request):
    """
    Commits human approval or rejection.
    Accepts JSON or Form data with {token, action}.
    Enforces single-use token by transitioning status from ready_for_review.
    """
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        token = body.get("token")
        action = body.get("action")
    else:
        form = await request.form()
        token = form.get("token")
        action = form.get("action")

    if not token or not action:
        raise HTTPException(status_code=400, detail="Missing token or action")

    if action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail=f"Invalid action: {action}")

    valid, run_id, token_action, err = verify_review_token(token)
    if not valid:
        raise HTTPException(status_code=400, detail=err or "Invalid token")

    if token_action != "review" and token_action != action:
        raise HTTPException(status_code=400, detail="Token action mismatch")

    target_status = "approved" if action == "approve" else "rejected"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE video_runs
                SET status = %s,
                    review_token_hash = %s,
                    review_decision_at = NOW(),
                    updated_at = NOW()
                WHERE run_id = %s
                  AND status = 'ready_for_review'
                RETURNING run_id
                """,
                (target_status, token.split(":")[-1], run_id),
            )
            row = cur.fetchone()
            conn.commit()

            if not row:
                raise HTTPException(
                    status_code=409,
                    detail="Review decision has already been committed for this run.",
                )

            logger.info(f"Video run {run_id} transitioned to {target_status} by human reviewer.")

            if "text/html" in request.headers.get("accept", "") or "application/x-www-form-urlencoded" in content_type:
                decision_label = "Approved" if target_status == "approved" else "Rejected"
                decision_color = "#10b981" if target_status == "approved" else "#ef4444"
                return HTMLResponse(
                    content=f"""<!DOCTYPE html>
<html>
<head><title>WeAware News - Review Recorded</title></head>
<body style='font-family:-apple-system,BlinkMacSystemFont,sans-serif;background:#0f172a;color:#f8fafc;padding:40px;display:flex;justify-content:center;'>
<div style='max-width:520px;width:100%;background:#1e293b;padding:32px;border-radius:12px;text-align:center;'>
    <h2 style='color:{decision_color};margin-top:0;'>Video {decision_label}</h2>
    <p style='color:#cbd5e1;'>Decision successfully committed for video run <code style='color:#38bdf8;'>{run_id}</code>.</p>
    <p style='color:#94a3b8;font-size:0.9rem;'>Status: <b>{target_status}</b></p>
</div>
</body>
</html>"""
                )

            return {"status": "ok", "run_id": run_id, "decision": target_status}


@app.get("/videos/next-approved", response_model=NextApprovedVideoResponse)
def get_next_approved_video(
    publish_timeout_min: int = Query(15, ge=5, le=60),
    auth: bool = Depends(verify_api_key),
):
    """
    Make.com pull endpoint:
    1. Sweeper resets expired 'publishing' runs back to 'approved'.
    2. Atomically selects and transitions the oldest approved video to 'publishing'.
    3. Returns signed video/thumbnail URLs and idempotency_key (or 204 No Content).
    """
    with get_db_connection() as conn:
        with get_dict_cursor(conn) as cur:
            # 1. Sweeper for expired publishing runs
            cur.execute(
                """
                UPDATE video_runs
                SET status = 'approved',
                    expires_at = NOW() + INTERVAL '1 hour',
                    updated_at = NOW()
                WHERE status = 'publishing'
                  AND expires_at < NOW()
                """
            )

            # 2. Atomic selection with FOR UPDATE SKIP LOCKED
            cur.execute(
                """
                UPDATE video_runs
                SET status = 'publishing',
                    expires_at = NOW() + (%s * INTERVAL '1 minute'),
                    idempotency_key = COALESCE(idempotency_key, gen_random_uuid()::text),
                    updated_at = NOW()
                WHERE run_id = (
                    SELECT run_id
                    FROM video_runs
                    WHERE status = 'approved'
                    ORDER BY updated_at ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                )
                RETURNING run_id, story_id, video_gcs_uri, thumbnail_gcs_uri, caption, hashtags, idempotency_key, run_metadata
                """,
                (publish_timeout_min,),
            )
            row = cur.fetchone()
            conn.commit()

            if not row:
                return Response(status_code=204)

            # Generate signed URL or storage URL
            video_gcs_uri = row["video_gcs_uri"] or ""
            thumb_gcs_uri = row["thumbnail_gcs_uri"] or ""

            # For local/mock or prod GCS signed URL:
            signed_video = video_gcs_uri
            signed_thumb = thumb_gcs_uri

            if video_gcs_uri.startswith("gs://"):
                try:
                    from google.cloud import storage
                    client = storage.Client()
                    # Parse bucket and blob
                    parsed = urlparse(video_gcs_uri)
                    bucket = client.bucket(parsed.netloc)
                    blob = bucket.blob(parsed.path.lstrip("/"))
                    signed_video = blob.generate_signed_url(
                        version="v4",
                        expiration=7200,  # 2-hour validity as required
                        method="GET",
                    )
                except Exception as e:
                    logger.warning(f"Could not generate signed URL: {e}. Returning raw URI.")

            # Fetch satire_disclosure from run_metadata (set by the pipeline scripter).
            # Appended here so Make.com's Instagram module always carries it in caption text,
            # since Meta's AI-label field is not reliably supported via Make's module.
            run_metadata_row = row.get("run_metadata") or {}
            satire_disclosure = (
                run_metadata_row.get("satire_disclosure")
                or "\n\n\u26a0\ufe0f This video is AI-generated satire for entertainment purposes. Not real news."
            )
            raw_caption = row["caption"] or ""
            hashtags_list = row["hashtags"] or []

            # Ensure caption body + disclosure + hashtags strictly stays within 2,200 chars.
            # Truncates caption body only, never disclosure or hashtags.
            clamped_body = clamp_caption(
                caption=raw_caption,
                hashtags=hashtags_list,
                satire_disclosure=satire_disclosure,
                max_total_chars=2200,
            )

            # Avoid double-appending if the disclosure was already baked into the caption
            if satire_disclosure.strip() not in clamped_body:
                caption_with_disclosure = clamped_body + satire_disclosure
            else:
                caption_with_disclosure = clamped_body

            return NextApprovedVideoResponse(
                run_id=str(row["run_id"]),
                story_id=row["story_id"],
                signed_video_url=signed_video,
                signed_thumbnail_url=signed_thumb,
                caption=caption_with_disclosure,
                hashtags=row["hashtags"] or [],
                idempotency_key=str(row["idempotency_key"]),
            )


@app.post("/videos/{run_id}/mark-published")
def mark_video_published(
    run_id: str,
    auth: bool = Depends(verify_api_key),
):
    """
    Make.com completion callback:
    Marks video run as 'published'. If claim_mode == 'shared', marks stories.posted = true.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE video_runs
                SET status = 'published',
                    updated_at = NOW()
                WHERE run_id = %s
                  AND status IN ('publishing', 'approved')
                RETURNING story_id, claim_mode
                """,
                (run_id,),
            )
            row = cur.fetchone()
            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=f"Run {run_id} not found or not in publishing/approved status.",
                )

            story_id, claim_mode = row[0], row[1]
            if claim_mode == "shared":
                cur.execute(
                    "UPDATE stories SET posted = true WHERE story_id = %s",
                    (story_id,),
                )
                logger.info(f"Shared claim mode: marked story {story_id} posted=true.")

            conn.commit()
            return {"status": "ok", "run_id": run_id, "story_id": story_id}
