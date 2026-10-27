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

def _sys_info():
    import os, shutil, time
    info = {}
    try:
        info["cpu_count"] = os.cpu_count()
        info["load_avg"] = list(os.getloadavg())
        info["cpu_percent"] = round(min(100.0, os.getloadavg()[0] / (os.cpu_count() or 1) * 100), 1)
    except Exception: pass
    try:
        mem = {}
        for line in open("/proc/meminfo"):
            k, v = line.split(":", 1); mem[k] = int(v.split()[0]) * 1024
        total, avail = mem["MemTotal"], mem.get("MemAvailable", mem["MemFree"])
        info["memory"] = {"total": total, "used": total - avail, "percent": round((total - avail) / total * 100, 1)}
        st, sf = mem.get("SwapTotal", 0), mem.get("SwapFree", 0)
        info["swap"] = {"total": st, "used": st - sf, "percent": round((st - sf) / st * 100, 1) if st else 0}
    except Exception: pass
    try:
        d = shutil.disk_usage("/")
        info["disk"] = {"total": d.total, "used": d.used, "percent": round(d.used / d.total * 100, 1)}
    except Exception: pass
    try: info["uptime_seconds"] = int(float(open("/proc/uptime").read().split()[0]))
    except Exception: pass
    try:
        rx = tx = 0
        for line in list(open("/proc/net/dev"))[2:]:
            name, data = line.split(":", 1)
            if name.strip() == "lo": continue
            cols = data.split(); rx += int(cols[0]); tx += int(cols[8])
        info["network"] = {"rx_bytes": rx, "tx_bytes": tx}
    except Exception: pass
    return info


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
    created = sum(u.data_limit or 0 for u in users); used = sum(u.used_traffic or 0 for u in users)
    unlimited = sum(1 for u in users if u.data_limit is None)
    cap = admin.max_total_traffic if admin.role != "sudo" else None
    total = cap if cap is not None else created
    online = sum(1 for u in users if u.online_at and (now - aware(u.online_at)) <= timedelta(minutes=3))
    expiring = sum(1 for u in users if u.expire and now <= aware(u.expire) <= now + timedelta(days=3))
    out = {"scope": "all" if admin.role == "sudo" else "own",
           "total_users": len(users), "active_users": by.get("active", 0), "disabled_users": by.get("disabled", 0),
           "expired_users": by.get("expired", 0), "limited_users": by.get("limited", 0), "on_hold_users": by.get("on_hold", 0),
           "online_users": online, "expiring_soon": expiring, "unlimited_users": unlimited,
           "traffic_total": total, "traffic_created": created, "traffic_used": used,
           "traffic_remaining": max(0, total - used) if total is not None else None,
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
