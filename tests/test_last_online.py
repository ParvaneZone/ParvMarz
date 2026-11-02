from datetime import datetime, timezone
from app.subscription.geo import last_online


def t(*a):
    return datetime(*a, tzinfo=timezone.utc)


def test_last_online_picks_latest_and_handles_missing():
    assert last_online(None, None) is None
    assert last_online(t(2026, 10, 1), None) == t(2026, 10, 1)
    assert last_online(None, t(2026, 10, 2)) == t(2026, 10, 2)
    assert last_online(t(2026, 10, 1), t(2026, 10, 3)) == t(2026, 10, 3)
    assert last_online(t(2026, 10, 4), t(2026, 10, 3)) == t(2026, 10, 4)


def test_last_online_accepts_naive_datetimes_as_utc():
    assert last_online(datetime(2026, 10, 1), t(2026, 10, 2)) == t(2026, 10, 2)
    assert last_online(t(2026, 10, 5), datetime(2026, 10, 2)) == t(2026, 10, 5)
