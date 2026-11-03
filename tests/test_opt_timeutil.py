from datetime import datetime

from app.core.timeutil import utc_ts


def test_utc_ts_treats_naive_as_utc():
    assert utc_ts(datetime(2024, 1, 1)) == 1704067200
