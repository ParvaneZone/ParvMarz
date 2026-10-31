"""Minimal RFC 6238 TOTP (Google Authenticator compatible) using only the stdlib."""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from app.config import settings

STEP = 30
DIGITS = 6
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def _hotp(secret: str, counter: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    mac = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = mac[-1] & 0x0F
    value = (struct.unpack(">I", mac[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** DIGITS)
    return f"{value:0{DIGITS}d}"


def verify(secret: str, code: str, last_step: int | None = None, now: float | None = None,
           window: int = 1) -> int | None:
    """Return the matched time-step, or None. A step <= last_step is rejected (no replay)."""
    digits = "".join(ch for ch in str(code) if ch.isdigit())
    if len(digits) != DIGITS:
        return None
    current = int((time.time() if now is None else now) // STEP)
    matched: int | None = None
    for step in range(current - window, current + window + 1):
        if hmac.compare_digest(_hotp(secret, step), digits) and (last_step is None or step > last_step):
            matched = step
    return matched


def provisioning_uri(secret: str, username: str, issuer: str) -> str:
    label = quote(f"{issuer}:{username}", safe="")
    return (f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer, safe='')}"
            f"&algorithm=SHA1&digits={DIGITS}&period={STEP}")


# ---- recovery codes: random, shown once, stored only as keyed hashes ----
def new_recovery_codes(count: int = 8) -> list[str]:
    return ["".join(secrets.choice(_ALPHABET) for _ in range(10)) for _ in range(count)]


def format_code(code: str) -> str:
    return f"{code[:5]}-{code[5:]}"


def _norm(code: str) -> str:
    return "".join(ch for ch in str(code).upper() if ch.isalnum())


def hash_recovery(code: str) -> str:
    return hmac.new(settings.jwt_secret.encode(), _norm(code).encode(), hashlib.sha256).hexdigest()


def consume_recovery(hashes: list[str] | None, code: str) -> list[str] | None:
    """Return the remaining hashes if `code` matched one of them, else None."""
    if len(_norm(code)) != 10:
        return None
    target = hash_recovery(code)
    remaining, hit = [], False
    for h in hashes or []:
        if not hit and hmac.compare_digest(h, target):
            hit = True
        else:
            remaining.append(h)
    return remaining if hit else None
