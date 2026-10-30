from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import Base
from app.db import models
from app.routers.usage import usage


def test_usage_buckets_follow_timezone_and_group_by_dimensions():
    eng = create_engine("sqlite://", future=True)
    Base.metadata.create_all(eng)
    db = sessionmaker(bind=eng)()
    def t(*a):
        return datetime(*a, tzinfo=timezone.utc)
    db.add_all([
        models.UsageLog(user_id=1, delta=100, total_after=100, recorded_at=t(2026, 10, 1, 20, 0), admin_id=1, panel_id=1, service_id=1),
        models.UsageLog(user_id=1, delta=50, total_after=150, recorded_at=t(2026, 10, 1, 21, 0), admin_id=1, panel_id=2, service_id=1),
        models.UsageLog(user_id=2, delta=7, total_after=7, recorded_at=t(2026, 10, 2, 5, 0), admin_id=9, panel_id=None, service_id=None),
        models.UsageLog(user_id=2, delta=999, total_after=9, recorded_at=t(2026, 10, 5, 0, 0), admin_id=1, panel_id=1, service_id=1),  # outside
    ])
    db.commit()
    r = usage(start=t(2026, 9, 30, 20, 30), end=t(2026, 10, 3, 20, 30), bucket="day", tz_offset=210, _=None, db=db)
    assert r["total"] == 157
    days = {(x["t"], x["admin"], x["panel"]): x["bytes"] for x in r["rows"]}
    # 20:00 UTC = 23:30 Tehran (Oct 1); 21:00 UTC = 00:30 Tehran (Oct 2)
    assert days[("2026-10-01", 1, 1)] == 100
    assert days[("2026-10-02", 1, 2)] == 50
    assert days[("2026-10-02", 9, None)] == 7
    assert r["deleted"]["admins"] == [1, 9]
