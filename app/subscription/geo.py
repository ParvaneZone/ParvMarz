import asyncio
import ipaddress
import logging
from datetime import datetime, timezone
import httpx
from app.db.models import SubAccess
from app.db.session import SessionLocal

log = logging.getLogger("jinxdata.geo")
_mem: dict[str, dict] = {}


def client_ip(request) -> str:
    h = request.headers
    ip = (h.get("cf-connecting-ip") or h.get("x-real-ip") or (h.get("x-forwarded-for") or "").split(",")[0] or (request.client.host if request.client else "")).strip()
    return ip


async def _lookup(ip: str) -> dict:
    if ip in _mem:
        return _mem[ip]
    try:
        if ipaddress.ip_address(ip).is_private:
            return {}
    except ValueError:
        return {}
    try:
        async with httpx.AsyncClient(timeout=4) as c:
            d = (await c.get(f"http://ip-api.com/json/{ip}", params={"fields": "status,country,regionName,city,isp", "lang": "fa"})).json()
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
