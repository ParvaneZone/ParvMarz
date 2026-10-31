from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.security import require_sudo
from app.db.models import Admin, Panel, Service, SyncTask, User
from app.db.session import get_db

router = APIRouter(prefix="/api/system", tags=["system"])
ONLINE_WINDOW = timedelta(minutes=3)  # same definition as the dashboard's "online users"


def _aware(d):
    return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)


@router.get("/online")
def online_users(_: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - ONLINE_WINDOW
    users = [u for u in db.query(User).filter(User.online_at.isnot(None)).all() if _aware(u.online_at) >= since]
    admins = {a.id: a.username for a in db.query(Admin.id, Admin.username)}
    services = {s.id: (s.display_name or s.name) for s in db.query(Service.id, Service.display_name, Service.name)}
    users.sort(key=lambda u: _aware(u.online_at), reverse=True)
    return {"window_seconds": int(ONLINE_WINDOW.total_seconds()), "count": len(users),
            "items": [{"username": u.username, "admin": admins.get(u.admin_id, f"[deleted-{u.admin_id}]"),
                       "service": services.get(u.service_id, f"[deleted-{u.service_id}]"), "status": u.status,
                       "used_traffic": u.used_traffic, "data_limit": u.data_limit, "online_at": _aware(u.online_at)}
                      for u in users[:500]]}


@router.get("/diagnostics")
def diagnostics(_: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    panels = db.query(Panel).order_by(Panel.id).all()
    names = {p.id: p.name for p in panels}
    states = dict(db.query(SyncTask.state, func.count(SyncTask.id)).group_by(SyncTask.state).all())
    failed = db.query(SyncTask).filter(SyncTask.state == "failed").order_by(SyncTask.id.desc()).limit(50).all()
    return {"panels": [{"id": p.id, "name": p.name, "type": p.type, "enabled": p.enabled, "status": p.status,
                        "last_ok_at": _aware(p.last_ok_at), "last_error": p.last_error, "sync_interval": p.sync_interval}
                       for p in panels],
            "sync_tasks": {k: int(v) for k, v in states.items()},
            "failed_tasks": [{"id": x.id, "panel": names.get(x.panel_id, f"[deleted-{x.panel_id}]"), "action": x.action,
                              "attempts": x.attempts, "last_error": x.last_error, "created_at": _aware(x.created_at)}
                             for x in failed]}
