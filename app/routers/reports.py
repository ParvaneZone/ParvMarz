import csv
import io
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.security import require_sudo, require_perm
from app.db.models import Admin, AuditLog, Panel, Service, UsageLog, User
from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["reports"])


@router.get("/reports/summary", summary="گزارش مصرف و کاربران به تفکیک نماینده/سرویس/پنل")
def summary(days: int = Query(30, ge=1, le=365), admin: Admin = Depends(require_perm("dashboard.view")), db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=days)
    def usage(col, model):
        q = db.query(col, func.coalesce(func.sum(UsageLog.delta), 0)).filter(UsageLog.recorded_at >= since)
        if admin.role != "sudo": q = q.filter(UsageLog.admin_id == admin.id)
        names = {m.id: getattr(m, "username", None) or getattr(m, "name", None) for m in db.query(model).all()}
        return [{"id": i, "name": names.get(i), "traffic": int(t)} for i, t in q.group_by(col).order_by(func.sum(UsageLog.delta).desc()).all()]
    uq = db.query(User.status, func.count(User.id))
    if admin.role != "sudo": uq = uq.filter(User.admin_id == admin.id)
    out = {"days": days, "users_by_status": dict(uq.group_by(User.status).all()),
           "traffic_by_service": usage(UsageLog.service_id, Service), "traffic_by_panel": usage(UsageLog.panel_id, Panel)}
    if admin.role == "sudo": out["traffic_by_admin"] = usage(UsageLog.admin_id, Admin)
    return out


@router.get("/users/export.csv", summary="خروجی CSV کاربران")
def export_users(admin: Admin = Depends(require_perm("users.view")), db: Session = Depends(get_db)):
    q = db.query(User)
    if admin.role != "sudo": q = q.filter(User.admin_id == admin.id)
    buf = io.StringIO(); w = csv.writer(buf)
    w.writerow(["username", "admin_id", "service_id", "status", "data_limit", "used_traffic", "expire", "created_at", "note"])
    for u in q.order_by(User.id):
        w.writerow([u.username, u.admin_id, u.service_id, u.status, u.data_limit, u.used_traffic, u.expire, u.created_at, (u.note or "").replace("\n", " ")])
    buf.seek(0)
    return StreamingResponse(iter(["\ufeff" + buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=users.csv"})


@router.get("/audit", summary="لاگ عملیات (فقط مدیر اصلی)")
def audit(action: str | None = None, actor_admin_id: int | None = None, object_id: str | None = None,
          limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0),
          _: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    q = db.query(AuditLog)
    if action: q = q.filter(AuditLog.action.like(f"{action}%"))
    if actor_admin_id is not None: q = q.filter(AuditLog.actor_admin_id == actor_admin_id)
    if object_id: q = q.filter(AuditLog.object_id == object_id)
    total = q.count()
    rows = q.order_by(AuditLog.id.desc()).offset(offset).limit(limit).all()
    return {"total": total, "items": [{"id": r.id, "actor_admin_id": r.actor_admin_id, "action": r.action, "object_type": r.object_type,
                                       "object_id": r.object_id, "details": r.details, "created_at": r.created_at} for r in rows]}
