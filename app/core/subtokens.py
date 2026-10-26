import base64
import hashlib
import hmac
import json
from app.config import settings


def issue_subscription_token(username: str, created_at: int, version: int) -> str:
    body = json.dumps({"u": username, "c": created_at, "v": version}, separators=(",", ":"), ensure_ascii=False).encode()
    encoded = base64.urlsafe_b64encode(body).rstrip(b"=").decode()
    sig = hmac.new(settings.subscription_hmac_key.encode(), encoded.encode(), hashlib.sha256).digest()
    return encoded + "." + base64.urlsafe_b64encode(sig).rstrip(b"=").decode()


def verify_subscription_token(token: str) -> dict | None:
    try:
        encoded, signature = token.split(".", 1)
        expected = base64.urlsafe_b64encode(hmac.new(settings.subscription_hmac_key.encode(), encoded.encode(), hashlib.sha256).digest()).rstrip(b"=").decode()
        if not hmac.compare_digest(signature, expected):
            return None
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        data = json.loads(raw)
        if not isinstance(data.get("u"), str) or not isinstance(data.get("v"), int):
            return None
        return data
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
