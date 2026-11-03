from datetime import datetime, timedelta, timezone
import logging
from app.config import settings
from app.core.notify import notify_event
from app.core.timeutil import utc_ts
from sqlalchemy import func
from app.db.models import Admin, Setting, SyncTask, User, UserPanelAccount, AuditLog, SubAccess, UsageLog
from app.db.session import SessionLocal

log = logging.getLogger("jinxdata.maintenance")


def warn_expiring() -> int:
    """Notify once per (user, expire date) when a user is within expiry_warn_days of expiring."""
    now = datetime.now(timezone.utc); sent = 0
    with SessionLocal() as db:
        rows = db.query(User).filter(User.status == "active", User.expire.is_not(None), User.expire > now,
                                     User.expire <= now + timedelta(days=settings.expiry_warn_days)).all()
        for u in rows:
            key = f"warned:{u.id}"; stamp = utc_ts(u.expire)
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


def compact_usage(db, now: datetime | None = None, max_days: int = 20) -> int:
    """Old usage rows (one per user+panel per 30 min) -> one row per user+panel+service+admin per local day, stamped at
    local noon. Day reports stay exact; hour reports are limited to 8 days, which is newer than the compaction age."""
    days = settings.usage_compact_days
    if days <= 0: return 0
    off = timedelta(minutes=settings.tz_offset_minutes)
    now = now or datetime.now(timezone.utc)
    now = now.astimezone(timezone.utc).replace(tzinfo=None) if now.tzinfo else now  # naive UTC, like `day` below
    cutoff = (now + off - timedelta(days=max(days, 9))).replace(hour=0, minute=0, second=0, microsecond=0)
    first = db.query(func.min(UsageLog.recorded_at)).scalar()
    if first is None: return 0
    first = first.astimezone(timezone.utc).replace(tzinfo=None) if first.tzinfo else first
    day = (first + off).replace(hour=0, minute=0, second=0, microsecond=0)
    removed = done = 0
    while day < cutoff and done < max_days:
        lo = (day - off).replace(tzinfo=timezone.utc); hi = lo + timedelta(days=1); noon = lo + timedelta(hours=12)
        day += timedelta(days=1)
        span = (UsageLog.recorded_at >= lo, UsageLog.recorded_at < hi)
        if not db.query(func.count(UsageLog.id)).filter(*span, UsageLog.recorded_at != noon).scalar(): continue
        agg = {}; n = 0
        for uid, aid, pid, sid, delta, total, rid in db.query(UsageLog.user_id, UsageLog.admin_id, UsageLog.panel_id, UsageLog.service_id,
                                                              UsageLog.delta, UsageLog.total_after, UsageLog.id).filter(*span).yield_per(5000):
            n += 1; a = agg.get((uid, aid, pid, sid))
            if a is None: agg[(uid, aid, pid, sid)] = [delta, total, rid]
            else:
                a[0] += delta
                if rid > a[2]: a[1], a[2] = total, rid
        db.query(UsageLog).filter(*span).delete(synchronize_session=False)
        db.add_all(UsageLog(user_id=k[0], admin_id=k[1], panel_id=k[2], service_id=k[3], delta=v[0], total_after=v[1], recorded_at=noon)
                   for k, v in agg.items())
        db.commit(); removed += n - len(agg); done += 1
    return removed


def vacuum_if_needed() -> bool:
    """SQLite never shrinks its file after deletes; rewrite it when a big share of it is free pages."""
    if not settings.database_url.startswith("sqlite") or ":memory:" in settings.database_url: return False
    from app.db.session import engine
    try:
        with engine.connect() as c:
            free = c.exec_driver_sql("PRAGMA freelist_count").scalar() or 0
            total = c.exec_driver_sql("PRAGMA page_count").scalar() or 1
            size = c.exec_driver_sql("PRAGMA page_size").scalar() or 4096
        if free * size < 16 * 1024 * 1024 or free / total < 0.3: return False
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
            c.exec_driver_sql("VACUUM")
        return True
    except Exception as exc:
        log.warning("vacuum skipped: %s", type(exc).__name__); return False


def prune_data() -> dict:
    """Keep the DB, disk and RAM small over months: stale caches/locks, finished sync tasks, old access/usage/audit rows."""
    import time
    now = time.time(); nowdt = datetime.now(timezone.utc); out = {}
    with SessionLocal() as db:
        n = 0
        for row in db.query(Setting).filter(Setting.key.like("subcache:%")).all():
            v = row.value if isinstance(row.value, dict) else {}
            if v.get("expires", 0) < now - 3600:
                db.delete(row); n += 1
        for row in db.query(Setting).filter(Setting.key.like("login:%")).all():
            ts = (row.value or {}).get("t", []) if isinstance(row.value, dict) else []
            if not ts or max(ts) < now - max(settings.login_lock_seconds, settings.login_user_lock_seconds, 900):
                db.delete(row); n += 1
        warned = {}
        for (k,) in db.query(Setting.key).filter(Setting.key.like("warned:%")).all():
            if k[7:].isdigit(): warned[int(k[7:])] = k
        if warned:  # expiry-warning marks of users that no longer exist
            ids = list(warned); alive = set()
            for i in range(0, len(ids), 500):
                alive.update(x for (x,) in db.query(User.id).filter(User.id.in_(ids[i:i + 500])))
            for uid, k in warned.items():
                if uid not in alive:
                    db.query(Setting).filter(Setting.key == k).delete(synchronize_session=False); n += 1
        out["settings"] = n
        if settings.sync_task_retention_days > 0:
            out["sync_done"] = db.query(SyncTask).filter(SyncTask.state == "done", SyncTask.created_at < nowdt - timedelta(days=settings.sync_task_retention_days)).delete(synchronize_session=False)
        out["sync_failed"] = db.query(SyncTask).filter(SyncTask.state == "failed", SyncTask.created_at < nowdt - timedelta(days=30)).delete(synchronize_session=False)
        if settings.sub_access_retention_days > 0:
            out["sub_access"] = db.query(SubAccess).filter(SubAccess.last_seen < nowdt - timedelta(days=settings.sub_access_retention_days)).delete(synchronize_session=False)
        if settings.log_retention_days > 0:
            cutoff = nowdt - timedelta(days=settings.log_retention_days)
            out["usage"] = db.query(UsageLog).filter(UsageLog.recorded_at < cutoff).delete(synchronize_session=False)
            out["audit"] = db.query(AuditLog).filter(AuditLog.created_at < cutoff).delete(synchronize_session=False)
        db.commit()
        out["usage_compacted"] = compact_usage(db)
    out["vacuum"] = vacuum_if_needed()
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


def check_admins() -> int:
    """Notify (once per state) when an agent's account expires / is about to expire / used up its total traffic."""
    now = datetime.now(timezone.utc); sent = 0
    def once(db, a, kind, mark, event, data):
        nonlocal sent
        key = f"adminwarn:{a.id}:{kind}"; s = db.get(Setting, key)
        if s and s.value.get("m") == mark: return
        db.merge(Setting(key=key, value={"m": mark})); notify_event(event, {"username": a.username, **data, "admin_id": a.id}); sent += 1
    def clear(db, a, kind):
        s = db.get(Setting, f"adminwarn:{a.id}:{kind}")
        if s: db.delete(s)
    with SessionLocal() as db:
        for a in db.query(Admin).filter(Admin.role != "sudo", Admin.disabled.is_(False)).all():
            if a.expire is not None:
                exp = a.expire if a.expire.tzinfo else a.expire.replace(tzinfo=timezone.utc); stamp = int(exp.timestamp())
                if exp <= now: once(db, a, "expired", stamp, "admin.expired", {"expire": exp.isoformat()})
                elif exp <= now + timedelta(days=settings.expiry_warn_days): once(db, a, "expiring", stamp, "admin.expiring", {"expire": exp.isoformat()})
                else: clear(db, a, "expiring"); clear(db, a, "expired")
            else: clear(db, a, "expiring"); clear(db, a, "expired")
            if a.max_total_traffic:
                used = int(db.query(func.coalesce(func.sum(User.used_traffic), 0)).filter(User.admin_id == a.id).scalar() or 0)
                if used >= a.max_total_traffic: once(db, a, "traffic", int(a.max_total_traffic), "admin.traffic_full", {"used": used, "limit": a.max_total_traffic})
                else: clear(db, a, "traffic")
        db.commit()
    return sent
