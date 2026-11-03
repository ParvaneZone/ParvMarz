import asyncio

from app.config import settings
from app.subscription import geo


def test_geo_lookup_can_be_disabled(monkeypatch):
    monkeypatch.setattr(settings, "geo_lookup_enabled", False)
    monkeypatch.setattr(geo, "_mem", {})
    assert asyncio.run(geo._lookup("8.8.8.8")) == {}
