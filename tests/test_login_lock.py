import time
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.config import settings
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
                    models.Admin(username="other", password_hash=hash_password(GOOD), role="admin", permissions={}, allowed_services=[])])
        db.commit()
    app = FastAPI()
    app.include_router(auth.router)

    def _db():
        with Session() as d:
            yield d
    app.dependency_overrides[get_db] = _db
    monkeypatch.setattr(settings, "login_rate_limit_enabled", True)
    monkeypatch.setattr(settings, "login_max_attempts", 5)
    monkeypatch.setattr(settings, "login_user_max_attempts", 3)
    monkeypatch.setattr(settings, "login_user_lock_seconds", 900)
    ips = iter(f"198.51.100.{i}" for i in range(1, 250))  # every request comes from a new IP
    monkeypatch.setattr(auth, "real_ip", lambda request: next(ips))
    return TestClient(app), Session


def _login(c, user, pw):
    return c.post("/api/admin/token", json={"username": user, "password": pw})


def test_username_cap_blocks_distributed_bruteforce(env):
    c, _ = env
    for _i in range(3):
        assert _login(c, "agent", "wrong").status_code == 401
    r = _login(c, "agent", GOOD)  # correct password, but the username is locked across all IPs
    assert r.status_code == 429 and r.json()["detail"]["code"] == "LOGIN_LOCKED"
    assert _login(c, "other", GOOD).status_code == 200  # other usernames unaffected


def test_username_lock_is_temporary(env):
    c, Session = env
    for _i in range(3):
        _login(c, "agent", "wrong")
    assert _login(c, "agent", GOOD).status_code == 429
    with Session() as db:  # age the recorded failures past the lock window
        row = db.get(models.Setting, "login:user:agent")
        row.value = {"t": [time.time() - settings.login_user_lock_seconds - 1] * 3}
        db.commit()
    assert _login(c, "agent", GOOD).status_code == 200


def test_success_clears_username_counter(env):
    c, Session = env
    for _i in range(2):
        _login(c, "agent", "wrong")
    assert _login(c, "agent", GOOD).status_code == 200
    with Session() as db:
        assert db.get(models.Setting, "login:user:agent") is None
