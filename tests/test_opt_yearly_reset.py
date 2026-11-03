from datetime import datetime, timezone

from app.jobs.reset_usage import _next_reset


def test_yearly_reset_from_feb_29_does_not_raise():
    got = _next_reset(datetime(2024, 2, 29, tzinfo=timezone.utc), "year")
    assert got == datetime(2025, 2, 28, tzinfo=timezone.utc)
