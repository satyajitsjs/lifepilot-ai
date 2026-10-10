"""Short-lived signed demo sessions. Replace with OIDC/OAuth for production."""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import time
from fastapi import HTTPException
from .config import API_SECRET, DEMO_MODE


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def issue_token(user_id: str) -> str:
    payload = _b64(json.dumps({"sub": user_id, "exp": int(time.time()) + 8 * 3600}, separators=(",", ":")).encode())
    sig = _b64(hmac.new(API_SECRET.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def verify_token(token: str) -> str:
    try:
        payload, signature = token.split(".")
        check = _b64(hmac.new(API_SECRET.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, check):
            raise ValueError("bad signature")
        value = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if int(value["exp"]) < time.time():
            raise ValueError("expired")
        return str(value["sub"])
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid or expired session") from e


def require_demo():
    if not DEMO_MODE:
        raise HTTPException(403, "Demo login disabled. Configure production identity provider.")


def require_membership(conn, user_id: str, circle_id: str) -> dict:
    member = conn.execute("SELECT * FROM memberships WHERE user_id=? AND circle_id=?", (user_id,circle_id)).fetchone()
    if not member:
        raise HTTPException(403, "You do not have access to this circle")
    return dict(member)
