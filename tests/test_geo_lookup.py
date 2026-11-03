import asyncio
import pytest
from app.config import settings
from app.subscription import geo

PUBLIC_IP = "8.8.8.8"


class FakeClient:
    seen: list = []
    payload: dict = {}

    def __init__(self, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, params=None):
        FakeClient.seen.append(url)

        class R:
            def json(self_inner):
                return FakeClient.payload
        return R()


@pytest.fixture(autouse=True)
def fake_http(monkeypatch):
    FakeClient.seen = []
    FakeClient.payload = {"success": True, "country": "Germany", "region": "Hesse", "city": "Frankfurt", "connection": {"isp": "Example ISP"}}
    monkeypatch.setattr(geo.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(geo, "_mem", {})
    monkeypatch.setattr(settings, "geo_lookup_enabled", True)
    monkeypatch.setattr(settings, "geo_lookup_url", "https://ipwho.is/{ip}")


def test_default_provider_is_https():
    assert settings.geo_lookup_url.startswith("https://") and settings.geo_lookup_enabled is True


def test_lookup_uses_https_url_and_parses_the_response():
    assert asyncio.run(geo._lookup(PUBLIC_IP)) == {"country": "Germany", "region": "Hesse", "city": "Frankfurt", "isp": "Example ISP"}
    assert FakeClient.seen == [f"https://ipwho.is/{PUBLIC_IP}"]


def test_lookup_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(settings, "geo_lookup_enabled", False)
    assert asyncio.run(geo._lookup(PUBLIC_IP)) == {} and FakeClient.seen == []


def test_plain_http_provider_is_never_called(monkeypatch):
    monkeypatch.setattr(settings, "geo_lookup_url", "http://ip-api.com/json/{ip}")
    assert asyncio.run(geo._lookup(PUBLIC_IP)) == {} and FakeClient.seen == []


def test_private_addresses_are_not_sent_out():
    assert asyncio.run(geo._lookup("192.168.1.5")) == {} and FakeClient.seen == []


def test_failed_lookup_gives_empty_dict():
    FakeClient.payload = {"success": False, "message": "Invalid IP address"}
    assert asyncio.run(geo._lookup(PUBLIC_IP)) == {}
