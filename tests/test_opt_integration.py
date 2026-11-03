import asyncio
import pathlib
import shutil
import subprocess
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token, hash_password
from app.db import models
from app.db.session import Base, get_db
from app.jobs import reset_usage, usage_sync
from app.routers import auth

FUTURE = datetime.now(timezone.utc) + timedelta(days=10)


@pytest.fixture()
def env(monkeypatch):
    eng = create_engine("sqlite://", future=True, poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    with Session() as db:
        db.add_all([models.Admin(username="root", password_hash=hash_password("x" * 12), role="sudo", permissions={"*": True}),
                    models.Admin(username="agent", password_hash=hash_password("x" * 12), role="admin", permissions={}, allowed_services=[]),
                    models.Panel(name="p1", type="marzban", base_url="http://p1", enabled=True),
                    models.Service(name="s", display_name="S")])
        db.commit()
        tok = create_access_token(db.query(models.Admin).filter_by(username="root").one())
    app = FastAPI()
    app.include_router(auth.router)

    def _db():
        with Session() as d:
            yield d
    app.dependency_overrides[get_db] = _db
    monkeypatch.setattr(reset_usage, "SessionLocal", Session)
    monkeypatch.setattr(usage_sync, "SessionLocal", Session)
    return TestClient(app), Session, {"Authorization": f"Bearer {tok}"}


def add_user(Session, name, status="active", limit=1000, used=100, strategy="no_reset"):
    with Session() as db:
        u = models.User(username=name, admin_id=2, service_id=1, status=status, data_limit=limit, used_traffic=used,
                        expire=FUTURE, data_limit_reset_strategy=strategy)
        db.add(u); db.flush()
        db.add(models.UserPanelAccount(user_id=u.id, panel_id=1, remote_username=f"r_{name}", last_remote_used_traffic=0))
        db.commit()
        return u.id


def test_logout_revokes_the_token(env):
    c, _, H = env
    assert c.get("/api/admin/preferences", headers=H).status_code == 200
    assert c.post("/api/admin/logout", headers=H).status_code == 200
    r = c.get("/api/admin/preferences", headers=H)
    assert r.status_code == 401 and r.json()["detail"]["code"] == "TOKEN_REVOKED"


def test_reset_job_survives_a_broken_user(env, monkeypatch):
    _, Session, _ = env
    bad = add_user(Session, "bad", strategy="month")
    good = add_user(Session, "good", strategy="month")
    with Session() as db:
        for uid in (bad, good):
            db.add(models.Setting(key=f"user_reset:{uid}", value={"next": 1.0}))
        db.commit()
    real = reset_usage.restore_active

    def flaky(db, u, *a, **k):
        if u.username == "bad":
            raise RuntimeError("boom")
        return real(db, u, *a, **k)
    monkeypatch.setattr(reset_usage, "restore_active", flaky)
    assert reset_usage.reset_usage_job() == {"users_reset": 1}
    with Session() as db:
        assert db.get(models.User, good).used_traffic == 0
        assert db.get(models.User, bad).used_traffic == 100


def test_usage_sync_adds_delta_in_sql(env, monkeypatch):
    _, Session, _ = env
    uid = add_user(Session, "u")

    class FakeDriver:
        async def get_usages(self, names):
            return {"r_u": 150}
    monkeypatch.setattr(usage_sync, "build_driver", lambda *a, **k: FakeDriver())
    monkeypatch.setattr(usage_sync, "get_panel_credentials", lambda *a, **k: {})
    usage_sync._last_run.clear()
    asyncio.run(usage_sync.sync_usage())
    with Session() as db:
        assert db.get(models.User, uid).used_traffic == 250
        log = db.query(models.UsageLog).filter_by(user_id=uid).one()
        assert log.delta == 150 and log.total_after == 250


def test_entrypoint_is_valid_sh():
    sh = shutil.which("sh")
    if not sh:
        pytest.skip("no sh available")
    path = pathlib.Path(__file__).resolve().parent.parent / "docker-entrypoint.sh"
    assert subprocess.run([sh, "-n", str(path)]).returncode == 0
