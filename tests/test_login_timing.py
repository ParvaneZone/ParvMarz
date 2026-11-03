import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core import security
from app.core.security import hash_password
from app.db import models
from app.db.session import Base, get_db
from app.routers import auth

PW = "Abcdefgh123!"


@pytest.fixture()
def env(monkeypatch):
    eng = create_engine("sqlite://", future=True, poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    with S() as db:
        db.add_all([models.Admin(username="real", password_hash=hash_password(PW), role="admin", permissions={}),
                    models.Admin(username="off", password_hash=hash_password(PW), role="admin", permissions={}, disabled=True)])
        db.commit()
    app = FastAPI()
    app.include_router(auth.router)

    def _db():
        with S() as d:
            yield d
    app.dependency_overrides[get_db] = _db
    calls = []
    real = auth.verify_password

    def spy(password, hashed):
        calls.append(hashed)
        return real(password, hashed)
    monkeypatch.setattr(auth, "verify_password", spy)
    return TestClient(app), calls


def test_unknown_username_still_runs_one_bcrypt_check(env):
    c, calls = env
    r = c.post("/api/admin/token", json={"username": "ghost", "password": PW})
    assert r.status_code == 401 and r.json()["detail"]["code"] == "BAD_CREDENTIALS"
    assert calls == [security.dummy_hash()]


def test_disabled_admin_also_runs_one_bcrypt_check(env):
    c, calls = env
    r = c.post("/api/admin/token", json={"username": "off", "password": PW})
    assert r.status_code == 401
    assert len(calls) == 1


def test_real_login_still_works_and_wrong_password_fails(env):
    c, calls = env
    assert c.post("/api/admin/token", json={"username": "real", "password": "wrong-password"}).status_code == 401
    assert c.post("/api/admin/token", json={"username": "real", "password": PW}).status_code == 200
    assert len(calls) == 2


def test_dummy_hash_is_a_stable_valid_bcrypt_hash():
    assert security.dummy_hash() == security.dummy_hash()
    assert security.dummy_hash().startswith("$2")
    assert not security.verify_password(PW, security.dummy_hash())
