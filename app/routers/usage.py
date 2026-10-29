from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.security import require_sudo
from app.db.models import Admin, Panel, Service, UsageLog
from app.db.session import get_db

router = APIRouter(prefix="/api/usage", tags=["usage"])


def _bad(msg: str, code: str = "INVALID_RANGE"):
    return HTTPException(422, detail={"detail": msg, "code": code})


def _bucket_expr(db: Session, bucket: str, offset_min: int):
    """Local-time bucket label (offset applied in SQL so day boundaries follow the viewer's timezone)."""
    if db.bind.dialect.name == "sqlite":
        fmt = "%Y-%m-%d" if bucket == "day" else "%Y-%m-%dT%H:00"
        return func.strftime(fmt, UsageLog.recorded_at, f"{offset_min:+d} minutes")
    fmt = "YYYY-MM-DD" if bucket == "day" else 'YYYY-MM-DD"T"HH24":00"'
    return func.to_char(UsageLog.recorded_at + timedelta(minutes=offset_min), fmt)


@router.get("")
def usage(start: datetime, end: datetime, bucket: str = Query("day", pattern="^(day|hour)$"),
          tz_offset: int = Query(0, ge=-840, le=840),
          _: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    """Traffic added in [start, end) grouped by bucket x admin x node(panel) x service.
    start/end are UTC instants; tz_offset is minutes east of UTC and only decides bucket labels."""
    s = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
    e = end if end.tzinfo else end.replace(tzinfo=timezone.utc)
    s, e = s.astimezone(timezone.utc), e.astimezone(timezone.utc)
    if e <= s: raise _bad("بازه زمانی نامعتبر است")
    if (e - s) > (timedelta(days=8) if bucket == "hour" else timedelta(days=400)):
        raise _bad("بازه زمانی بیش از حد بزرگ است")
    naive = db.bind.dialect.name == "sqlite"  # sqlite stores UTC wall-clock without tzinfo
    lo, hi = (s.replace(tzinfo=None), e.replace(tzinfo=None)) if naive else (s, e)
    b = _bucket_expr(db, bucket, tz_offset).label("b")
    rows = (db.query(b, UsageLog.admin_id, UsageLog.panel_id, UsageLog.service_id, func.sum(UsageLog.delta))
            .filter(UsageLog.recorded_at >= lo, UsageLog.recorded_at < hi)
            .group_by(b, UsageLog.admin_id, UsageLog.panel_id, UsageLog.service_id).all())
    admins = {a.id: a.username for a in db.query(Admin.id, Admin.username)}
    panels = {p.id: p.name for p in db.query(Panel.id, Panel.name)}
    services = {x.id: (x.display_name or x.name) for x in db.query(Service.id, Service.display_name, Service.name)}
    return {"bucket": bucket, "total": int(sum(r[4] or 0 for r in rows)),
            "rows": [{"t": r[0], "admin": r[1], "panel": r[2], "service": r[3], "bytes": int(r[4] or 0)} for r in rows],
            "admins": {str(k): v for k, v in admins.items()}, "panels": {str(k): v for k, v in panels.items()},
            "services": {str(k): v for k, v in services.items()},
            "deleted": {"admins": sorted({r[1] for r in rows if r[1] is not None and r[1] not in admins}),
                        "panels": sorted({r[2] for r in rows if r[2] is not None and r[2] not in panels}),
                        "services": sorted({r[3] for r in rows if r[3] is not None and r[3] not in services})}}
