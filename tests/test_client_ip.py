import asyncio
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


def _req(peer: str, **headers) -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "query_string": b"",
                    "headers": [(k.replace("_", "-").encode(), v.encode()) for k, v in headers.items()],
                    "client": (peer, 1234)})


@pytest.fixture
def Session(monkeypatch):
    eng = create_engine("sqlite://", future=True, poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(geo, "SessionLocal", S)
    monkeypatch.setattr(maintenance, "SessionLocal", S)

    async def no_lookup(ip):
        return {}
    monkeypatch.setattr(geo, "_lookup", no_lookup)
    return S


def test_client_ip_ignores_forged_header_from_untrusted_peer(monkeypatch):
    monkeypatch.setattr(settings, "trust_proxy_headers", False)
    assert geo.client_ip(_req("203.0.113.5", x_real_ip="6.6.6.6", x_forwarded_for="7.7.7.7")) == "203.0.113.5"


def test_client_ip_rejects_invalid_header_and_falls_back(monkeypatch):
    monkeypatch.setattr(settings, "trust_proxy_headers", True)
    monkeypatch.setattr(settings, "trusted_proxy_ips", "10.0.0.1")
    assert geo.client_ip(_req("10.0.0.1", x_real_ip="<script>alert(1)</script>", x_forwarded_for="junk")) == "10.0.0.1"
    assert geo.client_ip(_req("10.0.0.1", x_real_ip="1.2.3.4")) == "1.2.3.4"


def test_client_ip_empty_when_peer_is_not_an_ip(monkeypatch):
    monkeypatch.setattr(settings, "trust_proxy_headers", False)
    assert geo.client_ip(_req("testclient")) == ""


def test_sub_access_rows_per_user_are_capped(Session):
    n = geo.MAX_IPS_PER_USER + 5
    for i in range(n):
        asyncio.run(geo.record_access(1, f"198.51.100.{i}", []))
    with Session() as db:
        rows = db.query(models.SubAccess).filter_by(user_id=1).all()
        ips = {r.ip for r in rows}
    assert len(rows) == geo.MAX_IPS_PER_USER
    assert f"198.51.100.{n - 1}" in ips and "198.51.100.0" not in ips  # newest kept, oldest dropped


def test_known_ip_updates_without_growing(Session):
    for _i in range(3):
        asyncio.run(geo.record_access(1, "198.51.100.9", ["a"]))
    with Session() as db:
        rows = db.query(models.SubAccess).all()
    assert len(rows) == 1 and rows[0].hits == 3


def test_prune_removes_old_sub_access(Session):
    old = datetime.now(timezone.utc) - timedelta(days=settings.log_retention_days + 5)
    with Session() as db:
        db.add_all([models.SubAccess(user_id=1, ip="198.51.100.1", first_seen=old, last_seen=old),
                    models.SubAccess(user_id=1, ip="198.51.100.2")])
        db.commit()
    assert maintenance.prune_data()["sub_access"] == 1
    with Session() as db:
        assert [r.ip for r in db.query(models.SubAccess).all()] == ["198.51.100.2"]
