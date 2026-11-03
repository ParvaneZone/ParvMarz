from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.db.session import Base
from app.db import models
from app.jobs.maintenance import compact_usage
from app.jobs.usage_sync import add_usage


def _db():
    eng = create_engine("sqlite://", future=True)
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng)()


class _U:
    id = 1; admin_id = 1; service_id = 1; used_traffic = 0


def test_add_usage_merges_inside_half_hour_slot():
    db = _db(); u = _U(); t = datetime(2026, 10, 1, 10, 5, tzinfo=timezone.utc)
    u.used_traffic = 100; add_usage(db, u, 7, 100, t); db.commit()
    u.used_traffic = 160; add_usage(db, u, 7, 60, t + timedelta(minutes=20)); db.commit()
    u.used_traffic = 170; add_usage(db, u, 7, 10, t + timedelta(minutes=30)); db.commit()
    rows = db.query(models.UsageLog).order_by(models.UsageLog.id).all()
    assert [(r.delta, r.total_after) for r in rows] == [(160, 160), (10, 170)]


def test_compact_usage_merges_old_days_per_local_day(monkeypatch):
    monkeypatch.setattr(settings, "usage_compact_days", 10)
    monkeypatch.setattr(settings, "tz_offset_minutes", 210)
    db = _db(); now = datetime(2026, 10, 30, 12, 0, tzinfo=timezone.utc)
    t = lambda *a: datetime(*a, tzinfo=timezone.utc)
    for ts, d, tot in [(t(2026, 10, 1, 2, 0), 10, 10), (t(2026, 10, 1, 5, 0), 20, 30),
                       (t(2026, 10, 1, 21, 0), 5, 35), (t(2026, 10, 28, 5, 0), 99, 99)]:
        db.add(models.UsageLog(user_id=1, delta=d, total_after=tot, recorded_at=ts, admin_id=1, panel_id=1, service_id=1))
    db.commit()
    assert compact_usage(db, now) == 1
    got = sorted((r.recorded_at.replace(tzinfo=None), r.delta, r.total_after) for r in db.query(models.UsageLog))
    assert got == [(datetime(2026, 10, 1, 8, 30), 30, 30), (datetime(2026, 10, 2, 8, 30), 5, 35), (datetime(2026, 10, 28, 5, 0), 99, 99)]
    assert compact_usage(db, now) == 0
