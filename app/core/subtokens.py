"""Subscription link tokens.

New format: a UUID-shaped token (8-4-4-4-12 lowercase hex) = user_id[4] | version[4] | HMAC-SHA256(...)[:8].
 - looks exactly like a config UUID, so the link blends in with the rest
 - no username / personal data inside the link
 - revoking (bumping sub_token_version) still kills the old link instantly

Compact base64url tokens (27 chars) and legacy tokens (``<base64 json>.<sig>``) are still verified so links
already handed out keep working until the owner revokes them.
"""
import base64
import hashlib
import hmac
import json
import re
import struct
from app.config import settings

_MAC_LEN = 12
_UUID_MAC_LEN = 8
_TAG = b"sub2"
_UUID_TAG = b"sub3"
_UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def _key() -> bytes:
    return settings.subscription_hmac_key.encode()


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64d(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _mac(payload: bytes, tag: bytes = _TAG, size: int = _MAC_LEN) -> bytes:
    return hmac.new(_key(), tag + payload, hashlib.sha256).digest()[:size]


def _issue_legacy(username: str, created_at: int, version: int) -> str:
    body = json.dumps({"u": username, "c": created_at, "v": version}, separators=(",", ":"), ensure_ascii=False).encode()
    encoded = _b64e(body)
    sig = hmac.new(_key(), encoded.encode(), hashlib.sha256).digest()
    return encoded + "." + _b64e(sig)


def issue_subscription_token(username: str, created_at: int, version: int, user_id: int | None = None) -> str:
    """With ``user_id`` -> UUID-shaped token (preferred). Without -> legacy token (kept for old callers/tests)."""
    if user_id is None:
        return _issue_legacy(username, created_at, version)
    payload = struct.pack(">II", user_id, version)
    h = (payload + _mac(payload, _UUID_TAG, _UUID_MAC_LEN)).hex()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:]}"


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


def _verify_uuid(token: str) -> dict | None:
    raw = bytes.fromhex(token.replace("-", ""))
    payload, mac = raw[:8], raw[8:]
    if not hmac.compare_digest(mac, _mac(payload, _UUID_TAG, _UUID_MAC_LEN)):
        return None
    user_id, version = struct.unpack(">II", payload)
    return {"id": user_id, "v": version}


def verify_subscription_token(token: str) -> dict | None:
    """Returns {"id", "v"} for UUID/compact tokens or {"u", "c", "v"} for legacy ones; None when invalid."""
    try:
        if len(token) > 512:
            return None
        if _UUID_RE.fullmatch(token):
            return _verify_uuid(token)
        return _verify_legacy(token) if "." in token else _verify_compact(token)
    except (ValueError, TypeError, json.JSONDecodeError, struct.error, UnicodeError):
        return None
