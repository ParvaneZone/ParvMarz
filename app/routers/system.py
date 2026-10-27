import os
import shutil
import threading
import time

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.security import current_admin, require_sudo, require_perm, admin_state
from app.db.models import Admin, User, Panel, SyncTask
from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "subhub"}


@router.get("/system/stats")
def stats(_: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    counts = dict(db.query(User.status, func.count(User.id)).group_by(User.status).all())
    return {"users_by_status": counts, "total_users": sum(counts.values()),
            "panels": {"healthy": db.query(Panel).filter(Panel.status == "healthy").count(),
                       "total": db.query(Panel).count()},
            "pending_sync_tasks": db.query(SyncTask).filter(SyncTask.state == "pending").count()}


@router.get("/admin")
def admin_profile(admin: Admin = Depends(current_admin), db: Session = Depends(get_db)):
    from app.core.permissions import effective
    return {"id": admin.id, "username": admin.username, "role": admin.role, "permissions": effective(admin), "state": admin_state(admin, db), "expire": admin.expire}

_sample_lock = threading.Lock()
_prev: dict = {}          # last raw counters: {"t": monotonic, "cpu": (busy, total), "rx": int, "tx": int}
_last: dict = {}          # last computed rates, reused when polled faster than _MIN_WINDOW
_MIN_WINDOW = 0.4         # seconds; shorter windows give noisy CPU numbers


def _read_cpu() -> tuple[float, float] | None:
    """(busy_jiffies, total_jiffies) summed over all cores, from /proc/stat."""
    try:
        with open("/proc/stat") as fh:
            parts = fh.readline().split()
        if parts[0] != "cpu":
            return None
        vals = [float(x) for x in parts[1:]]
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0.0)   # idle + iowait
        total = sum(vals[:8]) if len(vals) >= 8 else sum(vals)  # exclude guest (already in user/nice)
        return total - idle, total
    except Exception:
        return None


def _read_net() -> tuple[int, int] | None:
    try:
        rx = tx = 0
        with open("/proc/net/dev") as fh:
            lines = fh.readlines()[2:]
        for line in lines:
            name, data = line.split(":", 1)
            if name.strip() == "lo":
                continue
            cols = data.split()
            rx += int(cols[0]); tx += int(cols[8])
        return rx, tx
    except Exception:
        return None


def _rates() -> dict:
    """Real CPU % and network speed measured between two samples (not load average)."""
    with _sample_lock:
        now = time.monotonic()
        cpu, net = _read_cpu(), _read_net()
        prev = _prev
        if prev and now - prev["t"] < _MIN_WINDOW and _last:
            return dict(_last)
        out: dict = {}
        if cpu is not None and prev.get("cpu"):
            db_, dt_ = cpu[0] - prev["cpu"][0], cpu[1] - prev["cpu"][1]
            if dt_ > 0:
                out["cpu_percent"] = round(max(0.0, min(100.0, db_ / dt_ * 100.0)), 2)
        if net is not None and prev.get("rx") is not None and now > prev["t"]:
            span = now - prev["t"]
            out["rx_speed"] = round(max(0, net[0] - prev["rx"]) / span, 2)
            out["tx_speed"] = round(max(0, net[1] - prev["tx"]) / span, 2)
        _prev.clear()
        _prev.update({"t": now, "cpu": cpu, "rx": net[0] if net else None, "tx": net[1] if net else None})
        if out:
            _last.clear(); _last.update(out)
            return out
        return dict(_last)


def _sys_info():
    info: dict = {}
    try:
        info["cpu_count"] = os.cpu_count()
        info["load_avg"] = [round(x, 2) for x in os.getloadavg()]
    except Exception: pass
    rates = _rates()
    if "cpu_percent" in rates:
        info["cpu_percent"] = rates["cpu_percent"]
    elif info.get("load_avg"):  # first call after start: no previous sample yet
        info["cpu_percent"] = round(min(100.0, info["load_avg"][0] / (os.cpu_count() or 1) * 100), 2)
    try:
        mem = {}
        for line in open("/proc/meminfo"):
            k, v = line.split(":", 1); mem[k] = int(v.split()[0]) * 1024
        total, avail = mem["MemTotal"], mem.get("MemAvailable", mem["MemFree"])
        info["memory"] = {"total": total, "used": total - avail, "percent": round((total - avail) / total * 100, 2)}
        st, sf = mem.get("SwapTotal", 0), mem.get("SwapFree", 0)
        info["swap"] = {"total": st, "used": st - sf, "percent": round((st - sf) / st * 100, 2) if st else 0.0}
    except Exception: pass
    try:
        d = shutil.disk_usage("/")
        info["disk"] = {"total": d.total, "used": d.used, "percent": round(d.used / d.total * 100, 2)}
    except Exception: pass
    try: info["uptime_seconds"] = int(float(open("/proc/uptime").read().split()[0]))
    except Exception: pass
    net = _read_net()
    if net:
        info["network"] = {"rx_bytes": net[0], "tx_bytes": net[1],
                           "rx_speed": rates.get("rx_speed"), "tx_speed": rates.get("tx_speed")}
    info["ts"] = time.time()
    return info


@router.get("/system/live")
def live_system(_: Admin = Depends(require_sudo)):
    """Lightweight, poll-every-second-or-two snapshot of server load (decimals, real CPU %)."""
    return _sys_info()


@router.get("/system/dashboard")
def dashboard(admin: Admin = Depends(require_perm("dashboard.view")), db: Session = Depends(get_db)):
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    q = db.query(User)
    if admin.role != "sudo": q = q.filter(User.admin_id == admin.id)
    users = q.all()
    def aware(d): return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)
    by = {}
    for u in users: by[u.status] = by.get(u.status, 0) + 1
    limited = [u for u in users if u.data_limit is not None]
    created = sum(u.data_limit for u in limited)           # volume handed out to users that have a limit
    used = sum(u.used_traffic or 0 for u in users)         # everything consumed, unlimited users included
    unlimited = len(users) - len(limited)
    cap = admin.max_total_traffic if admin.role != "sudo" else None
    if cap is not None:
        # Reseller with a quota: quota is checked against everything their users consumed.
        total, remaining = cap, max(0, cap - used)
    else:
        # No quota: total = sum of the users' limits; remaining counted per user so one user's
        # overuse (or an unlimited user's traffic) can never eat into another user's volume.
        total = created
        remaining = sum(max(0, u.data_limit - (u.used_traffic or 0)) for u in limited)
    online = sum(1 for u in users if u.online_at and (now - aware(u.online_at)) <= timedelta(minutes=3))
    expiring = sum(1 for u in users if u.expire and now <= aware(u.expire) <= now + timedelta(days=3))
    out = {"scope": "all" if admin.role == "sudo" else "own",
           "total_users": len(users), "active_users": by.get("active", 0), "disabled_users": by.get("disabled", 0),
           "expired_users": by.get("expired", 0), "limited_users": by.get("limited", 0), "on_hold_users": by.get("on_hold", 0),
           "online_users": online, "expiring_soon": expiring, "unlimited_users": unlimited,
           "traffic_total": total, "traffic_created": created, "traffic_used": used,
           "traffic_remaining": remaining,
           "max_users": admin.max_users if admin.role != "sudo" else None}
    if admin.role == "sudo":
        out["admins_total"] = db.query(Admin).count()
        out["panels"] = {"healthy": db.query(Panel).filter(Panel.status == "healthy").count(), "total": db.query(Panel).count()}
        out["pending_sync_tasks"] = db.query(SyncTask).filter(SyncTask.state == "pending").count()
        out["failed_sync_tasks"] = db.query(SyncTask).filter(SyncTask.state == "failed").count()
        out["system"] = _sys_info()
    return out


@router.get('/system/audit')
def audit_logs(limit:int=100,offset:int=0,_:Admin=Depends(require_sudo),db:Session=Depends(get_db)):
    from app.db.models import AuditLog
    limit=max(1,min(limit,500)); offset=max(0,offset)
    rows=db.query(AuditLog).order_by(AuditLog.id.desc()).offset(offset).limit(limit).all()
    return {'items':[{'id':x.id,'actor_admin_id':x.actor_admin_id,'action':x.action,'object_type':x.object_type,'object_id':x.object_id,'details':x.details,'created_at':x.created_at} for x in rows]}

@router.get('/system/settings')
def get_settings(_:Admin=Depends(require_sudo),db:Session=Depends(get_db)):
    from app.db.models import Setting
    return {x.key:(x.value.get('value') if isinstance(x.value,dict) and 'value' in x.value else x.value) for x in db.query(Setting).all() if not x.key.startswith('subcache:')}

@router.put('/system/settings')
def put_settings(body:dict,actor:Admin=Depends(require_sudo),db:Session=Depends(get_db)):
    from app.db.models import Setting, AuditLog
    if len(body)>100: return {'detail':'Too many settings','code':'TOO_MANY_SETTINGS'}
    for key,value in body.items():
        if not isinstance(key,str) or not key or len(key)>120 or key.startswith('subcache:'):
            from fastapi import HTTPException
            raise HTTPException(422,detail={'detail':'کلید تنظیمات نامعتبر است','code':'INVALID_SETTING'})
        db.merge(Setting(key=key,value={'value':value}))
    db.add(AuditLog(actor_admin_id=actor.id,action='system.settings.update',object_type='settings',object_id='global',details={'keys':list(body)})); db.commit(); return {'ok':True}

@router.post('/system/backup')
def manual_backup(_:Admin=Depends(require_sudo)):
    from app.jobs.backup import backup_database
    try: return backup_database()
    except Exception as exc:
        from fastapi import HTTPException
        raise HTTPException(503,detail={'detail':'تهیه نسخه پشتیبان ناموفق بود','code':'BACKUP_FAILED'}) from exc
