from datetime import datetime, timedelta, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request
from app.config import settings
from app.db import models
from app.db.session import Base
from app.jobs import maintenance
from app.subscription import geo


def req(peer="203.0.113.9", **headers):
    scope = {"type": "http", "method": "GET", "path": "/", "query_string": b"",
             "headers": [(k.replace("_", "-").encode(), v.encode()) for k, v in headers.items()],
             "client": (peer, 5555) if peer else None}
    return Request(scope)


@pytest.fixture()
def db_env(monkeypatch):
    eng = create_engine("sqlite://", future=True, poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    with S() as db:
        svc = models.Service(name="s", display_name="S")
        adm = models.Admin(username="root", password_hash="x", role="sudo", permissions={"*": True})
        db.add_all([svc, adm]); db.flush()
        user = models.User(username="u1", admin_id=adm.id, service_id=svc.id)
        db.add(user); db.commit()
        uid = user.id
    monkeypatch.setattr(geo, "SessionLocal", S)
    monkeypatch.setattr(maintenance, "SessionLocal", S)

    async def no_geo(ip):
        return {}
    monkeypatch.setattr(geo, "_lookup", no_geo)
    return S, uid


def test_client_ip_ignores_spoofed_headers_from_untrusted_peers(monkeypatch):
    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    monkeypatch.setattr(settings, "trusted_proxy_ips", "10.0.0.0/8")
    assert geo.client_ip(req(peer="203.0.113.9", x_forwarded_for="<script>alert(1)</script>")) == "203.0.113.9"
    assert geo.client_ip(req(peer="203.0.113.9", x_real_ip="1.2.3.4", cf_connecting_ip="5.6.7.8")) == "203.0.113.9"


def test_client_ip_rejects_invalid_values(monkeypatch):
    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    monkeypatch.setattr(settings, "trusted_proxy_ips", "10.0.0.0/8")
    # trusted proxy sent garbage -> direct connection address
    assert geo.client_ip(req(peer="10.0.0.5", x_forwarded_for="not-an-ip")) == "10.0.0.5"
    assert geo.client_ip(req(peer="10.0.0.5", x_real_ip="1.2.3.4")) == "1.2.3.4"
    # a peer that is not an IP at all is never stored
    assert geo.client_ip(req(peer="testclient", x_forwarded_for="1.2.3.4")) == ""
    assert geo.client_ip(req(peer=None)) == ""


async def test_sub_access_rows_are_capped_per_user(db_env):
    S, uid = db_env
    base = datetime.now(timezone.utc) - timedelta(days=1)
    with S() as db:
        for i in range(geo.MAX_IPS_PER_USER):
            when = base + timedelta(minutes=i)
            db.add(models.SubAccess(user_id=uid, ip=f"10.0.0.{i + 1}", inbounds=[], country="x", first_seen=when, last_seen=when))
        db.commit()
    await geo.record_access(uid, "198.51.100.1", ["a"])
    with S() as db:
        ips = {r.ip for r in db.query(models.SubAccess).filter_by(user_id=uid)}
    assert len(ips) == geo.MAX_IPS_PER_USER
    assert "198.51.100.1" in ips and "10.0.0.1" not in ips and "10.0.0.2" in ips  # oldest evicted


async def test_known_ip_updates_in_place(db_env):
    S, uid = db_env
    await geo.record_access(uid, "198.51.100.1", ["a"])
    await geo.record_access(uid, "198.51.100.1", ["b"])
    with S() as db:
        rows = db.query(models.SubAccess).filter_by(user_id=uid).all()
    assert len(rows) == 1 and rows[0].hits == 2 and rows[0].inbounds == ["b"]


def test_prune_removes_old_sub_access(db_env, monkeypatch):
    S, uid = db_env
    monkeypatch.setattr(settings, "log_retention_days", 180)
    old = datetime.now(timezone.utc) - timedelta(days=185)
    with S() as db:
        db.add(models.SubAccess(user_id=uid, ip="10.1.1.1", inbounds=[], first_seen=old, last_seen=old))
        db.add(models.SubAccess(user_id=uid, ip="10.1.1.2", inbounds=[]))
        db.commit()
    assert maintenance.prune_data()["sub_access"] == 1
    with S() as db:
        assert [r.ip for r in db.query(models.SubAccess)] == ["10.1.1.2"]
