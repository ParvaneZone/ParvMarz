from datetime import timedelta
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.security import create_access_token, hash_password
from app.db import models
from app.db.session import Base, get_db
from app.routers import auth

PW = "Abcdefgh123!"


@pytest.fixture()
def env():
    eng = create_engine("sqlite://", future=True, poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    with S() as db:
        db.add(models.Admin(username="real", password_hash=hash_password(PW), role="admin", permissions={}))
        db.commit()
    app = FastAPI()
    app.include_router(auth.router)

    def _db():
        with S() as d:
            yield d
    app.dependency_overrides[get_db] = _db
    return TestClient(app), S


def H(t):
    return {"Authorization": f"Bearer {t}"}


def test_logout_revokes_the_token(env):
    c, S = env
    tok = c.post("/api/admin/token", json={"username": "real", "password": PW}).json()["access_token"]
    assert c.get("/api/admin", headers=H(tok)).status_code == 200
    assert c.post("/api/admin/logout", headers=H(tok)).status_code == 200
    r = c.get("/api/admin", headers=H(tok))  # a copied token must be dead after logout
    assert r.status_code == 401 and r.json()["detail"]["code"] == "TOKEN_REVOKED"


def test_logout_only_revokes_that_session(env):
    c, S = env
    with S() as db:
        admin = db.query(models.Admin).one()
        other = create_access_token(admin)
        mine = create_access_token(admin)
    assert other != mine
    assert c.post("/api/admin/logout", headers=H(mine)).status_code == 200
    assert c.get("/api/admin", headers=H(mine)).status_code == 401
    assert c.get("/api/admin", headers=H(other)).status_code == 200


def test_logout_without_or_with_junk_token_is_harmless(env):
    c, S = env
    assert c.post("/api/admin/logout").status_code == 200
    assert c.post("/api/admin/logout", headers=H("not-a-jwt")).status_code == 200
    with S() as db:
        assert db.query(models.Setting).filter(models.Setting.key.like("revoked:%")).count() == 0


def test_prune_removes_only_expired_revocations(env, monkeypatch):
    import time
    from app.jobs import maintenance
    c, S = env
    with S() as db:
        db.add_all([models.Setting(key="revoked:old", value={"exp": int(time.time()) - 10}),
                    models.Setting(key="revoked:live", value={"exp": int(time.time()) + 3600})])
        db.commit()
    monkeypatch.setattr(maintenance, "SessionLocal", S)
    maintenance.prune_data()
    with S() as db:
        keys = {k for (k,) in db.query(models.Setting.key).filter(models.Setting.key.like("revoked:%"))}
    assert keys == {"revoked:live"}
