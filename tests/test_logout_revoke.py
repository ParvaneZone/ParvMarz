import time
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.security import hash_password
from app.db import models
from app.db.session import Base, get_db
from app.routers import auth

GOOD = "Aa1$" * 4


@pytest.fixture()
def env():
    eng = create_engine("sqlite://", future=True, poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    with Session() as db:
        db.add(models.Admin(username="agent", password_hash=hash_password(GOOD), role="admin", permissions={}, allowed_services=[]))
        db.commit()
    app = FastAPI()
    app.include_router(auth.router)

    def _db():
        with Session() as d:
            yield d
    app.dependency_overrides[get_db] = _db
    return TestClient(app), Session


def _login(c):
    r = c.post("/api/admin/token", json={"username": "agent", "password": GOOD})
    assert r.status_code == 200
    return r.json()["access_token"]


def H(t):
    return {"Authorization": f"Bearer {t}"}


def test_logout_revokes_that_token_only(env):
    c, _ = env
    t1, t2 = _login(c), _login(c)  # two sessions (e.g. two devices)
    assert c.get("/api/admin", headers=H(t1)).status_code == 200
    assert c.post("/api/admin/logout", headers=H(t1)).status_code == 200
    r = c.get("/api/admin", headers=H(t1))
    assert r.status_code == 401 and r.json()["detail"]["code"] == "TOKEN_REVOKED"
    assert c.get("/api/admin", headers=H(t2)).status_code == 200


def test_logout_with_cookie_denylists_the_copied_token(env):
    c, _ = env
    token = _login(c)  # the login also set the session cookie on this client
    assert c.post("/api/admin/logout").status_code == 200
    r = c.get("/api/admin", headers=H(token))  # someone replays the token they copied before logout
    assert r.status_code == 401 and r.json()["detail"]["code"] == "TOKEN_REVOKED"


def test_logout_with_garbage_or_api_key_is_harmless(env):
    c, Session = env
    assert c.post("/api/admin/logout", headers=H("not-a-jwt")).status_code == 200
    assert c.post("/api/admin/logout", headers=H("pmk_abcd1234.secret")).status_code == 200
    assert c.post("/api/admin/logout").status_code == 200
    with Session() as db:
        assert db.query(models.Setting).filter(models.Setting.key.like("revoked:%")).count() == 0


def test_expired_denylist_rows_are_pruned_on_logout(env):
    c, Session = env
    with Session() as db:
        db.add(models.Setting(key="revoked:old", value={"exp": int(time.time()) - 10}))
        db.add(models.Setting(key="revoked:fresh", value={"exp": int(time.time()) + 600}))
        db.commit()
    assert c.post("/api/admin/logout", headers=H(_login(c))).status_code == 200
    with Session() as db:
        keys = {k for (k,) in db.query(models.Setting.key).filter(models.Setting.key.like("revoked:%"))}
    assert "revoked:old" not in keys and "revoked:fresh" in keys and len(keys) == 2
