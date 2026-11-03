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

GOOD = "x" * 12


@pytest.fixture()
def env(monkeypatch):
    eng = create_engine("sqlite://", future=True, poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    with S() as db:
        db.add(models.Admin(username="ag", password_hash=hash_password(GOOD), role="admin", permissions={}))
        db.commit()
    app = FastAPI()
    app.include_router(auth.router)

    def _db():
        with S() as d:
            yield d
    app.dependency_overrides[get_db] = _db
    monkeypatch.setattr(settings, "login_rate_limit_enabled", True)
    monkeypatch.setattr(settings, "login_max_attempts", 5)
    return TestClient(app), S


def rotate_ips(monkeypatch):
    """Every request comes from a different IP, like a distributed brute-force."""
    ips = iter(f"198.51.100.{i}" for i in range(1, 250))
    monkeypatch.setattr(auth, "real_ip", lambda request: next(ips))


def login(c, user="ag", pw="bad"):
    return c.post("/api/admin/token", json={"username": user, "password": pw})


def test_distributed_attempts_hit_the_username_cap(env, monkeypatch):
    c, _ = env
    monkeypatch.setattr(settings, "login_user_max_attempts", 3)
    rotate_ips(monkeypatch)
    assert [login(c).status_code for _ in range(3)] == [401, 401, 401]
    r = login(c, pw=GOOD)  # even the right password is refused while the username is locked
    assert r.status_code == 429 and r.json()["detail"]["code"] == "LOGIN_LOCKED"


def test_other_usernames_are_not_affected(env, monkeypatch):
    c, _ = env
    monkeypatch.setattr(settings, "login_user_max_attempts", 2)
    rotate_ips(monkeypatch)
    for _ in range(2):
        login(c)
    assert login(c).status_code == 429
    assert login(c, user="someone-else").status_code == 401


def test_username_lock_expires_and_is_configurable(env, monkeypatch):
    c, S = env
    monkeypatch.setattr(settings, "login_user_max_attempts", 3)
    monkeypatch.setattr(settings, "login_user_lock_seconds", 30)
    rotate_ips(monkeypatch)
    now = time.time()
    with S() as db:
        db.add(models.Setting(key="login:user|ag", value={"t": [now - 5, now - 4, now - 3]}))
        db.commit()
    assert login(c, pw=GOOD).status_code == 429  # attempts are inside the 30 s window
    with S() as db:
        db.merge(models.Setting(key="login:user|ag", value={"t": [now - 100, now - 99, now - 98]}))
        db.commit()
    assert login(c, pw=GOOD).status_code == 200  # window passed: the real admin gets back in


def test_username_cap_can_be_disabled(env, monkeypatch):
    c, _ = env
    monkeypatch.setattr(settings, "login_user_max_attempts", 0)
    rotate_ips(monkeypatch)
    assert {login(c).status_code for _ in range(25)} == {401}
