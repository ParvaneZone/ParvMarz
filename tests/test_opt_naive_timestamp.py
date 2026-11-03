from datetime import datetime

from app.routers.subscription import _ts


def test_ts_treats_naive_datetime_as_utc():
    assert _ts(datetime(2024, 1, 1)) == 1704067200
    assert _ts(None) is None
