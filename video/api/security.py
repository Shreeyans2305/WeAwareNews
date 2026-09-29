"""
Security and HMAC Token utilities for WeAware Video API.
"""

import hmac
import hashlib
import time
import os
from typing import Optional, Tuple
from fastapi import Header, HTTPException

_DEFAULT_SECRET = "weaware-video-hmac-dev-secret-38a1b2c"


def get_hmac_secret() -> str:
    return os.getenv("VIDEO_HMAC_SECRET") or os.getenv("API_KEY") or _DEFAULT_SECRET


def get_api_key() -> str:
    return os.getenv("API_KEY", "")


def verify_api_key(x_api_key: Optional[str] = Header(None)) -> bool:
    expected_key = get_api_key()
    if not expected_key:
        # If not set in environment or testing without key, accept or check
        return True
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing x-api-key header")
    if not hmac.compare_digest(x_api_key, expected_key):
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return True


def generate_review_token(run_id: str, action: str, expires_in_seconds: int = 86400, secret: Optional[str] = None) -> str:
    """
    Generate an expiring HMAC-signed review token.
    Token format: {run_id}:{action}:{expiry_timestamp}:{signature}
    """
    secret = secret or get_hmac_secret()
    expiry = int(time.time()) + expires_in_seconds
    payload = f"{run_id}:{action}:{expiry}"
    sig = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}:{sig}"


def verify_review_token(token: str, secret: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[str], Optional[str]]:
    """
    Verify an HMAC review token.
    Returns: (is_valid, run_id, action, error_message)
    """
    secret = secret or get_hmac_secret()
    parts = token.split(":")
    if len(parts) != 4:
        return False, None, None, "Malformed token structure"

    run_id, action, expiry_str, signature = parts
    try:
        expiry = int(expiry_str)
    except ValueError:
        return False, None, None, "Invalid expiry timestamp"

    if time.time() > expiry:
        return False, run_id, action, "Token has expired"

    payload = f"{run_id}:{action}:{expiry_str}"
    expected_sig = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(signature, expected_sig):
        return False, run_id, action, "Invalid token signature"

    if action not in ("approve", "reject"):
        return False, run_id, action, f"Invalid action: {action}"

    return True, run_id, action, None
