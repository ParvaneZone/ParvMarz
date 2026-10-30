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


def prune_data() -> dict:
    """Keep the DB and RAM small over months: stale sub-cache / login-lock rows and old usage/audit logs."""
    import time
    from app.db.models import UsageLog
    now = time.time(); out = {}
    with SessionLocal() as db:
        n = 0
        for row in db.query(Setting).filter(Setting.key.like("subcache:%")).all():
            v = row.value if isinstance(row.value, dict) else {}
            if v.get("expires", 0) < now - 3600:
                db.delete(row); n += 1
        for row in db.query(Setting).filter(Setting.key.like("login:%")).all():
            ts = (row.value or {}).get("t", []) if isinstance(row.value, dict) else []
            if not ts or max(ts) < now - max(settings.login_lock_seconds, 900):
                db.delete(row); n += 1
        out["settings"] = n
        if settings.log_retention_days > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=settings.log_retention_days)
            out["usage"] = db.query(UsageLog).filter(UsageLog.recorded_at < cutoff).delete(synchronize_session=False)
            out["audit"] = db.query(AuditLog).filter(AuditLog.created_at < cutoff).delete(synchronize_session=False)
        db.commit()
    return out


def trim_memory() -> None:
    """Return freed heap pages to the OS (glibc keeps them otherwise, so RSS only ever grows)."""
    import gc
    gc.collect()
    try:
        import ctypes
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:
        pass
