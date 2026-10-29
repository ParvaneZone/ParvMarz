from datetime import datetime, timedelta, timezone
from app.config import settings
from app.core.notify import notify_event
from app.db.models import Setting, SyncTask, User, UserPanelAccount, AuditLog
from app.db.session import SessionLocal


def warn_expiring() -> int:
    """Notify once per (user, expire date) when a user is within expiry_warn_days of expiring."""
    now = datetime.now(timezone.utc); sent = 0
    with SessionLocal() as db:
        rows = db.query(User).filter(User.status == "active", User.expire.is_not(None), User.expire > now,
                                     User.expire <= now + timedelta(days=settings.expiry_warn_days)).all()
        for u in rows:
            key = f"warned:{u.id}"; stamp = int(u.expire.timestamp())
            s = db.get(Setting, key)
            if s and s.value.get("expire") == stamp:
                continue
            db.merge(Setting(key=key, value={"expire": stamp}))
            notify_event("user.expiring", {"username": u.username, "expire": u.expire.isoformat(), "admin_id": u.admin_id})
            sent += 1
        db.commit()
    return sent


def delete_old_expired() -> int:
    if settings.auto_delete_expired_days <= 0:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.auto_delete_expired_days)
    with SessionLocal() as db:
        rows = db.query(User).filter(User.expire.is_not(None), User.expire <= cutoff).all()
        for u in rows:
            for a in db.query(UserPanelAccount).filter_by(user_id=u.id).all():
                db.add(SyncTask(user_id=None, panel_id=a.panel_id, action="delete",
                                payload={"username": a.remote_username, "admin_id": u.admin_id}))
                db.delete(a)
            db.delete(u)
        if rows:
            db.add(AuditLog(actor_admin_id=None, action="users.auto_delete_expired", object_type="users",
                            object_id="auto", details={"count": len(rows)}))
        db.commit()
        return len(rows)
