"""Real client IP behind Cloudflare / a reverse proxy.

Proxy headers (CF-Connecting-IP, X-Real-IP, X-Forwarded-For) are only honoured when TRUST_PROXY_HEADERS is on
AND the direct TCP peer is one of TRUSTED_PROXY_IPS. Anything else gets the peer address, so a client that
reaches the panel directly cannot spoof its IP (login lock, API-key lock, subscription brake all key on it).
"""
import ipaddress
import logging
from functools import lru_cache
from fastapi import Request
from app.config import settings

log = logging.getLogger("jinxdata.netip")
_warned_empty = False


@lru_cache(maxsize=16)
def _networks(raw: str) -> tuple:
    nets = []
    for item in (x.strip() for x in (raw or "").split(",")):
        if not item:
            continue
        try:
            nets.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            log.warning("ignoring invalid TRUSTED_PROXY_IPS entry %r", item)
    return tuple(nets)


def _parse(value):
    try:
        return ipaddress.ip_address((value or "").strip())
    except ValueError:
        return None


def is_trusted_proxy(host: str) -> bool:
    ip = _parse(host)
    if ip is None:
        return False
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return any(ip in net for net in _networks(settings.trusted_proxy_ips))


def real_ip(request: Request) -> str:
    global _warned_empty
    peer = request.client.host if request.client else ""
    if not settings.trust_proxy_headers:
        return peer or "unknown"
    if not _networks(settings.trusted_proxy_ips):
        if not _warned_empty:
            _warned_empty = True
            log.warning("TRUST_PROXY_HEADERS is on but TRUSTED_PROXY_IPS is empty: proxy headers are ignored")
        return peer or "unknown"
    if not is_trusted_proxy(peer):
        return peer or "unknown"
    headers = request.headers
    for name in ("cf-connecting-ip", "x-real-ip"):
        ip = _parse(headers.get(name))
        if ip is not None:
            return str(ip)
    # X-Forwarded-For: walk from the right (the hop our proxy appended), skip our own trusted proxies;
    # the first untrusted hop is the client. A malformed hop ends the walk and we fall back to the peer.
    for part in reversed((headers.get("x-forwarded-for") or "").split(",")):
        ip = _parse(part)
        if ip is None:
            break
        if not is_trusted_proxy(str(ip)):
            return str(ip)
    return peer
