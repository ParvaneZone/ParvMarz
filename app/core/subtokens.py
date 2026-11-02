"""Subscription link tokens.

Current format: a random per-user UUID (``users.sub_uuid``) used directly as the link path: ``/sub/<uuid>``.
 - nothing about the user can be derived from the link
 - rotated on revoke / owner change, so the old link dies instantly

Older formats keep working until the owner revokes them:

Compact token: base64url( user_id[4] | version[4] | HMAC-SHA256(...)[:12] ) -> 27 URL-safe chars.
Legacy token (``<base64 json>.<sig>``).
"""
import base64
import hashlib
import hmac
import json
import re
import struct
import uuid
from app.config import settings

_MAC_LEN = 12
_TAG = b"sub2"
_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def new_sub_uuid() -> str:
    return str(uuid.uuid4())


def is_sub_uuid(value: str) -> bool:
    return bool(_UUID_RE.fullmatch(value.lower()))


def _key() -> bytes:
    return settings.subscription_hmac_key.encode()


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _mac(payload: bytes) -> bytes:
    return hmac.new(_key(), _TAG + payload, hashlib.sha256).digest()[:_MAC_LEN]


def _issue_legacy(username: str, created_at: int, version: int) -> str:
    body = json.dumps({"u": username, "c": created_at, "v": version}, separators=(",", ":"), ensure_ascii=False).encode()
    encoded = _b64e(body)
    sig = hmac.new(_key(), encoded.encode(), hashlib.sha256).digest()
    return encoded + "." + _b64e(sig)


def issue_subscription_token(username: str, created_at: int, version: int, user_id: int | None = None) -> str:
    """With ``user_id`` -> compact token (fallback for users without ``sub_uuid``). Without -> legacy token (kept for old callers/tests)."""
    if user_id is None:
        return _issue_legacy(username, created_at, version)
    payload = struct.pack(">II", user_id, version)
    return _b64e(payload + _mac(payload))


def _verify_legacy(token: str) -> dict | None:
    encoded, signature = token.split(".", 1)
    expected = _b64e(hmac.new(_key(), encoded.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        return None
    data = json.loads(_b64d(encoded))
    if not isinstance(data.get("u"), str) or not isinstance(data.get("v"), int):
        return None
    return data


def _verify_compact(token: str) -> dict | None:
    raw = _b64d(token)
    if len(raw) != 8 + _MAC_LEN:
        return None
    payload, mac = raw[:8], raw[8:]
    if not hmac.compare_digest(mac, _mac(payload)):
        return None
    user_id, version = struct.unpack(">II", payload)
    return {"id": user_id, "v": version}


def verify_subscription_token(token: str) -> dict | None:
    """Returns {"id", "v"} for compact tokens or {"u", "c", "v"} for legacy ones; None when invalid."""
    try:
        if len(token) > 512:
            return None
        return _verify_legacy(token) if "." in token else _verify_compact(token)
    except (ValueError, TypeError, json.JSONDecodeError, struct.error, UnicodeError):
        return None
