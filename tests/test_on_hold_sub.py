import time
from app.routers import subscription


def _u(**kw):
    base = {"status": "active", "expire": 0, "limit": None, "used": 0}
    base.update(kw)
    return base


def test_on_hold_user_is_not_inactive():
    # on_hold users must get configs: their first connection is what starts the clock (usage_sync flips them to active)
    assert subscription._inactive(_u(status="on_hold")) is False


def test_on_hold_user_over_traffic_limit_is_still_inactive():
    assert subscription._inactive(_u(status="on_hold", limit=100, used=100)) is True


def test_on_hold_user_under_traffic_limit_is_not_inactive():
    assert subscription._inactive(_u(status="on_hold", limit=100, used=0)) is False


def test_other_statuses_are_unchanged():
    assert subscription._inactive(_u()) is False
    for s in ("disabled", "limited", "expired"):
        assert subscription._inactive(_u(status=s)) is True
    assert subscription._inactive(_u(expire=int(time.time()) - 10)) is True
    assert subscription._inactive(_u(limit=10, used=10)) is True
