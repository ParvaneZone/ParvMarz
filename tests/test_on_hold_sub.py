import base64
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.routers import subscription as sub

LINK = "vless://1234@example.com:443#first"


def _u(**kw):
    base = {"id": 1, "username": "ali", "version": 1, "status": "active", "used": 0, "limit": 2**30,
            "expire": 0, "created": 1_700_000_000, "service_id": 1, "groups": [], "service_name": "S",
            "inb_mode": "all", "inb_interval": 60, "inb_count": 1, "admin_id": 1, "online_at": None,
            "reset": "no_reset", "on_hold_days": 7}
    base.update(kw)
    return base


def test_on_hold_user_is_not_inactive():
    # on_hold users have no expiry yet (it starts at the first connection), so they must still get configs
    assert sub._inactive(_u(status="on_hold")) is False


@pytest.mark.parametrize("status", ["disabled", "limited", "expired"])
def test_other_non_active_statuses_stay_inactive(status):
    assert sub._inactive(_u(status=status)) is True


def test_active_user_limits_still_apply():
    assert sub._inactive(_u()) is False
    assert sub._inactive(_u(expire=1)) is True  # expiry in the past
    assert sub._inactive(_u(used=2**30)) is True  # traffic used up


def test_on_hold_user_with_used_up_traffic_stays_inactive():
    assert sub._inactive(_u(status="on_hold", used=2**30)) is True


def _client(monkeypatch, user):
    calls = []

    async def fake_links(user_id, version):
        calls.append((user_id, version))
        return [LINK], {}

    monkeypatch.setattr(sub, "_load_user", lambda token: user)
    monkeypatch.setattr(sub, "_remote_links", fake_links)
    monkeypatch.setattr(sub, "spawn_record", lambda *a, **k: None)
    monkeypatch.setattr(sub, "_off_links", lambda u: [])
    app = FastAPI()
    app.include_router(sub.router)
    return TestClient(app), calls


def test_on_hold_subscription_fetches_configs(monkeypatch):
    c, calls = _client(monkeypatch, _u(status="on_hold"))
    r = c.get("/sub/tok")
    assert r.status_code == 200
    assert calls == [(1, 1)]
    assert "example.com" in base64.b64decode(r.text).decode()


def test_disabled_subscription_does_not_fetch_configs(monkeypatch):
    c, calls = _client(monkeypatch, _u(status="disabled"))
    r = c.get("/sub/tok")
    assert r.status_code == 200
    assert calls == []
    assert "example.com" not in base64.b64decode(r.text).decode()
