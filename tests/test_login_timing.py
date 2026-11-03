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

GOOD = "Aa1$" * 4


@pytest.fixture()
def env(monkeypatch):
    eng = create_engine("sqlite://", future=True, poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    with Session() as db:
        db.add_all([models.Admin(username="agent", password_hash=hash_password(GOOD), role="admin", permissions={}, allowed_services=[]),
                    models.Admin(username="off", password_hash=hash_password(GOOD), role="admin", permissions={}, allowed_services=[], disabled=True)])
        db.commit()
    app = FastAPI()
    app.include_router(auth.router)

    def _db():
        with Session() as d:
            yield d
    app.dependency_overrides[get_db] = _db
    calls = []
    real = auth.verify_password

    def spy(password, hashed):
        calls.append(hashed)
        return real(password, hashed)
    monkeypatch.setattr(auth, "verify_password", spy)
    return TestClient(app), calls


def _login(c, user, pw=GOOD):
    return c.post("/api/admin/token", json={"username": user, "password": pw})


def test_unknown_username_still_runs_one_bcrypt_check(env):
    c, calls = env
    r = _login(c, "ghost")
    assert r.status_code == 401 and r.json()["detail"]["code"] == "BAD_CREDENTIALS"
    assert calls == [security.dummy_hash()]


def test_disabled_admin_runs_bcrypt_and_cannot_login(env):
    c, calls = env
    r = _login(c, "off")
    assert r.status_code == 401 and r.json()["detail"]["code"] == "BAD_CREDENTIALS"
    assert len(calls) == 1 and calls[0] != security.dummy_hash()


def test_real_login_runs_exactly_one_check(env):
    c, calls = env
    assert _login(c, "agent").status_code == 200
    assert len(calls) == 1 and calls[0] != security.dummy_hash()


def test_dummy_hash_is_a_stable_valid_bcrypt_hash():
    h = security.dummy_hash()
    assert h.startswith("$2") and security.dummy_hash() == h
    assert security.verify_password(GOOD, h) is False
