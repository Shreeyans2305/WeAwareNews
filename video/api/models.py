"""
Pydantic models for WeAware Video API.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class CandidateArticle(BaseModel):
    source_name: str
    title: str
    url: str
    excerpt: str
    published_at: Optional[str] = None


class VideoCandidateResponse(BaseModel):
    story_id: str
    headline: str
    source_count: int
    articles: List[CandidateArticle]
    source_urls: List[str]
    combined_story_text: str


class ClaimRequest(BaseModel):
    claim_mode: str = "separate"
    timeout_minutes: int = 45
    headline_snapshot: str
    sources_snapshot: List[Dict[str, Any]]
    source_urls: List[str]
    story_text_snapshot: str


class ClaimResponse(BaseModel):
    run_id: str
    story_id: str
    status: str
    claimed_at: str
    expires_at: str


class StatusUpdateRequest(BaseModel):
    expected_status: str
    new_status: str
    heartbeat: bool = False
    heartbeat_extend_minutes: int = 30
    error_message: Optional[str] = None
    video_gcs_uri: Optional[str] = None
    thumbnail_gcs_uri: Optional[str] = None
    caption: Optional[str] = None
    hashtags: Optional[List[str]] = None
    script_data: Optional[Dict[str, Any]] = None
    claims_data: Optional[List[Dict[str, Any]]] = None
    run_metadata: Optional[Dict[str, Any]] = None
    estimated_cost_usd: Optional[float] = None
    veo_seconds_used: Optional[int] = None


class ReviewCommitRequest(BaseModel):
    token: str
    action: str  # 'approve' or 'reject'


class NextApprovedVideoResponse(BaseModel):
    run_id: str
    story_id: str
    signed_video_url: str
    signed_thumbnail_url: Optional[str] = None
    caption: str
    hashtags: List[str]
    idempotency_key: str
