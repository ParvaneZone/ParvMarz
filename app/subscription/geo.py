import asyncio
import ipaddress
import logging
from datetime import datetime, timezone
import httpx
from app.config import settings
from app.core.netip import real_ip
from app.db.models import SubAccess
from app.db.session import SessionLocal

log = logging.getLogger("jinxdata.geo")
_mem: dict[str, dict] = {}
MAX_IPS_PER_USER = 50  # SubAccess rows kept per user; the least recently seen are dropped first


def last_online(online_at, last_fetch):
    """Most recent of the usage-based online_at and the last subscription fetch (naive datetimes are treated as UTC)."""
    vals = [v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v for v in (online_at, last_fetch) if v]
    return max(vals) if vals else None


def client_ip(request) -> str:
    """Validated client IP: proxy headers only count when netip.real_ip trusts them; anything that is not a real IP gives ''."""
    try:
        return str(ipaddress.ip_address(real_ip(request)))
    except ValueError:
        return ""


async def _lookup(ip: str) -> dict:
    if not settings.geo_lookup_enabled:
        return {}
    if ip in _mem:
        return _mem[ip]
    try:
        if ipaddress.ip_address(ip).is_private:
            return {}
    except ValueError:
        return {}
    try:
        async with httpx.AsyncClient(timeout=4) as c:
            d = (await c.get(settings.geo_lookup_url.replace("{ip}", ip), params={"fields": "status,country,regionName,city,isp", "lang": "fa"})).json()
        r = {"country": d.get("country", ""), "region": d.get("regionName", ""), "city": d.get("city", ""), "isp": d.get("isp", "")} if d.get("status") == "success" else {}
    except Exception as exc:
        log.warning("geo lookup failed for %s: %s", ip, exc)
        return {}
    if len(_mem) > 3000:
        _mem.pop(next(iter(_mem)), None)
    _mem[ip] = r
    return r


async def record_access(user_id: int, ip: str, inbound_names: list[str]) -> None:
    if not ip:
        return
    try:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            row = db.query(SubAccess).filter_by(user_id=user_id, ip=ip).first()
            need_geo = not row or not row.country
            if row:
                row.hits += 1; row.last_seen = now; row.inbounds = inbound_names
            else:
                total = db.query(SubAccess).filter_by(user_id=user_id).count()
                if total >= MAX_IPS_PER_USER:  # make room for the new row
                    old = (db.query(SubAccess.id).filter_by(user_id=user_id)
                           .order_by(SubAccess.last_seen.asc(), SubAccess.id.asc()).limit(total - MAX_IPS_PER_USER + 1).all())
                    db.query(SubAccess).filter(SubAccess.id.in_([i for (i,) in old])).delete(synchronize_session=False)
                row = SubAccess(user_id=user_id, ip=ip, inbounds=inbound_names, first_seen=now, last_seen=now)
                db.add(row)
            db.commit()
        if need_geo:
            g = await _lookup(ip)
            if g:
                with SessionLocal() as db:
                    row = db.query(SubAccess).filter_by(user_id=user_id, ip=ip).first()
                    if row:
                        row.country, row.region, row.city, row.isp = g["country"], g["region"], g["city"], g["isp"]; db.commit()
    except Exception as exc:
        log.warning("record_access failed: %s", exc)


_tasks: set = set()


def spawn_record(user_id: int, ip: str, names: list[str]) -> None:
    t = asyncio.create_task(record_access(user_id, ip, names)); _tasks.add(t); t.add_done_callback(_tasks.discard)
