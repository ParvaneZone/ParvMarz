import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request
from app.config import Settings, settings
from app.core import security
from app.core.netip import real_ip
from app.core.security import hash_password
from app.db import models
from app.db.session import Base, get_db
from app.routers import auth


def req(peer="203.0.113.9", **headers):
    scope = {"type": "http", "method": "GET", "path": "/", "query_string": b"",
             "headers": [(k.replace("_", "-").encode(), v.encode()) for k, v in headers.items()],
             "client": (peer, 5555) if peer else None}
    return Request(scope)


def trust(monkeypatch, ips="10.0.0.0/8"):
    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    monkeypatch.setattr(settings, "trusted_proxy_ips", ips)


def test_default_is_off():
    assert Settings(_env_file=None).trust_proxy_headers is False
    assert Settings(_env_file=None).trusted_proxy_ips == ""


def test_invalid_trusted_proxy_entry_is_rejected():
    with pytest.raises(ValueError):
        Settings(_env_file=None, trusted_proxy_ips="10.0.0.0/8, not-an-ip")


def test_headers_ignored_when_trust_is_off(monkeypatch):
    monkeypatch.setattr(settings, "trust_proxy_headers", False)
    assert real_ip(req(peer="10.0.0.5", x_real_ip="1.2.3.4", cf_connecting_ip="5.6.7.8")) == "10.0.0.5"


def test_untrusted_peer_cannot_spoof_headers(monkeypatch):
    trust(monkeypatch)
    r = req(peer="203.0.113.9", x_real_ip="1.2.3.4", cf_connecting_ip="5.6.7.8", x_forwarded_for="9.9.9.9")
    assert real_ip(r) == "203.0.113.9"


def test_trust_on_but_empty_list_fails_closed(monkeypatch):
    trust(monkeypatch, ips="")
    assert real_ip(req(peer="10.0.0.5", x_real_ip="1.2.3.4")) == "10.0.0.5"


def test_trusted_peer_headers_are_honoured_and_validated(monkeypatch):
    trust(monkeypatch)
    assert real_ip(req(peer="10.0.0.5", cf_connecting_ip="5.6.7.8", x_real_ip="1.2.3.4")) == "5.6.7.8"
    assert real_ip(req(peer="10.0.0.5", cf_connecting_ip="garbage", x_real_ip="1.2.3.4")) == "1.2.3.4"
    assert real_ip(req(peer="10.0.0.5", x_real_ip="<script>")) == "10.0.0.5"
    assert real_ip(req(peer="::ffff:10.0.0.5", x_real_ip="1.2.3.4")) == "1.2.3.4"  # IPv4-mapped peer


def test_forwarded_for_uses_first_untrusted_hop_from_the_right(monkeypatch):
    trust(monkeypatch)
    # the client forged the left part; our proxy appended the real client, then another trusted hop
    r = req(peer="10.0.0.5", x_forwarded_for="6.6.6.6, 198.51.100.7, 10.0.0.9")
    assert real_ip(r) == "198.51.100.7"
    assert real_ip(req(peer="10.0.0.5", x_forwarded_for="6.6.6.6, junk")) == "10.0.0.5"
    assert real_ip(req(peer="10.0.0.5", x_forwarded_for="10.0.0.9, 10.0.0.8")) == "10.0.0.5"


@pytest.fixture()
def env(monkeypatch):
    eng = create_engine("sqlite://", future=True, poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    with S() as db:
        db.add(models.Admin(username="ag", password_hash=hash_password("x" * 12), role="admin", permissions={}))
        db.commit()
    app = FastAPI()
    app.include_router(auth.router)

    def _db():
        with S() as d:
            yield d
    app.dependency_overrides[get_db] = _db
    security._key_failures.clear()
    return TestClient(app)


def test_login_lock_is_not_bypassed_with_forged_headers(env, monkeypatch):
    trust(monkeypatch, ips="0.0.0.0/0,::/0")  # even "trust everything": the test peer is not an IP at all
    monkeypatch.setattr(settings, "login_rate_limit_enabled", True)
    monkeypatch.setattr(settings, "login_max_attempts", 5)
    codes = [env.post("/api/admin/token", json={"username": "ag", "password": "bad"},
                      headers={"X-Real-IP": f"198.51.100.{i}"}).status_code for i in range(1, 8)]
    assert codes[:5] == [401] * 5 and codes[5:] == [429, 429]


def test_api_key_lock_is_not_bypassed_with_forged_headers(env, monkeypatch):
    trust(monkeypatch, ips="0.0.0.0/0,::/0")
    codes = [env.get("/api/admin", headers={"X-API-Key": "pmk_deadbeef.zzz", "X-Real-IP": f"198.51.100.{i}"}).status_code
             for i in range(1, 23)]
    assert codes[:20] == [401] * 20 and codes[20:] == [429, 429]
