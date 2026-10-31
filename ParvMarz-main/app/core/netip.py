"""Real client IP behind Cloudflare / a reverse proxy (only trusted when TRUST_PROXY_HEADERS is on)."""
import ipaddress
from fastapi import Request
from app.config import settings


def real_ip(request: Request) -> str:
    if settings.trust_proxy_headers:
        for h in ("cf-connecting-ip", "x-real-ip"):
            v = (request.headers.get(h) or "").strip()
            try: return str(ipaddress.ip_address(v))
            except ValueError: pass
    return request.client.host if request.client else "unknown"
