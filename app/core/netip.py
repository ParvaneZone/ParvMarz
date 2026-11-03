"""Real client IP. Proxy headers (CF-Connecting-IP / X-Real-IP / X-Forwarded-For) are honoured only when
TRUST_PROXY_HEADERS is on AND the direct peer is listed in TRUSTED_PROXY_IPS; otherwise the socket IP is used."""
import ipaddress
from functools import lru_cache
from fastapi import Request
from app.config import settings


@lru_cache(maxsize=8)
def _nets(raw: str) -> tuple:
    out = []
    for part in raw.replace(" ", "").split(","):
        if not part:
            continue
        try:
            out.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            pass
    return tuple(out)


def _parse(value: str):
    try:
        return ipaddress.ip_address((value or "").strip())
    except ValueError:
        return None


def _trusted(ip) -> bool:
    return any(ip in n for n in _nets(settings.trusted_proxy_ips))


def real_ip(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    if not settings.trust_proxy_headers:
        return peer
    peer_ip = _parse(peer)
    if peer_ip is None or not _trusted(peer_ip):
        return peer  # header could be forged by whoever is connected directly
    for h in ("cf-connecting-ip", "x-real-ip"):
        v = _parse(request.headers.get(h) or "")
        if v is not None:
            return str(v)
    # X-Forwarded-For: walk from the right, skipping our own proxies; the first untrusted hop is the client
    for part in reversed((request.headers.get("x-forwarded-for") or "").split(",")):
        v = _parse(part)
        if v is None:
            break
        if not _trusted(v):
            return str(v)
    return peer
