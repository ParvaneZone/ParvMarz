from datetime import datetime, timedelta, timezone
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.security import create_access_token, hash_password
from app.core.status import restore_active
from app.db import models
from app.db.session import Base, get_db
from app.jobs import reset_usage
from app.routers import admins, bulk, users

PAST = datetime.now(timezone.utc) - timedelta(days=1)
FUTURE = datetime.now(timezone.utc) + timedelta(days=10)


@pytest.fixture()
def env(monkeypatch):
    eng = create_engine("sqlite://", future=True, poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    with Session() as db:
        db.add_all([models.Admin(username="root", password_hash=hash_password("x" * 12), role="sudo", permissions={"*": True}),
                    models.Admin(username="agent", password_hash=hash_password("x" * 12), role="admin", permissions={}, allowed_services=[]),
                    models.Panel(name="p1", type="marzban", base_url="http://p1"),
                    models.Service(name="s", display_name="S")])
        db.commit()
        tok = create_access_token(db.query(models.Admin).filter_by(username="root").one())
    app = FastAPI()
    for r in (users.router, bulk.router, admins.router):
        app.include_router(r)

    def _db():
        with Session() as d:
            yield d
    app.dependency_overrides[get_db] = _db
    monkeypatch.setattr(reset_usage, "SessionLocal", Session)
    return TestClient(app), Session, {"Authorization": f"Bearer {tok}"}


def add_user(Session, name="u", status="limited", limit=100, used=100, expire=FUTURE, strategy="no_reset"):
    with Session() as db:
        u = models.User(username=name, admin_id=2, service_id=1, status=status, data_limit=limit, used_traffic=used,
                        expire=expire, data_limit_reset_strategy=strategy)
        db.add(u); db.flush()
        db.add(models.UserPanelAccount(user_id=u.id, panel_id=1, remote_username=f"r_{name}"))
        db.commit()
        return u.id


def state(Session, uid):
    with Session() as db:
        return db.get(models.User, uid).status, db.query(models.SyncTask).filter_by(user_id=uid).order_by(models.SyncTask.id).all()


def test_restore_active_rules(env):
    _, Session, _ = env
    with Session() as db:
        mk = lambda **kw: models.User(username="x", admin_id=2, service_id=1, **kw)
        assert restore_active(db, mk(status="limited", data_limit=100, used_traffic=0)) is True
        assert restore_active(db, mk(status="limited", data_limit=None, used_traffic=10**12)) is True
        assert restore_active(db, mk(status="limited", data_limit=100, used_traffic=100)) is False
        assert restore_active(db, mk(status="expired", data_limit=100, used_traffic=0, expire=PAST)) is False
        for s in ("active", "disabled", "on_hold"):  # never auto-revive these
            u = mk(status=s, data_limit=100, used_traffic=0)
            assert restore_active(db, u) is False and u.status == s


def test_manual_reset_restores_limited_and_syncs(env):
    c, Session, H = env
    uid = add_user(Session)
    assert c.post("/api/user/u/reset", headers=H).status_code == 200
    status, tasks = state(Session, uid)
    assert status == "active"
    assert [t.action for t in tasks] == ["reset_usage", "modify"] and tasks[1].payload == {"username": "r_u", "status": "active"}


def test_manual_reset_keeps_expired_when_date_passed(env):
    c, Session, H = env
    uid = add_user(Session, status="expired", used=0, expire=PAST)
    c.post("/api/user/u/reset", headers=H)
    assert state(Session, uid)[0] == "expired"


def test_monthly_reset_job_restores_limited(env):
    _, Session, _ = env
    uid = add_user(Session, strategy="month")
    with Session() as db:
        db.add(models.Setting(key=f"user_reset:{uid}", value={"next": 1.0})); db.commit()
    assert reset_usage.reset_usage_job() == {"users_reset": 1}
    status, tasks = state(Session, uid)
    assert status == "active" and [t.action for t in tasks] == ["reset_usage", "modify"]


def test_bulk_traffic_increase_restores_limited_with_single_modify(env):
    c, Session, H = env
    uid = add_user(Session)
    assert c.post("/api/bulk/traffic", json={"user_ids": [uid], "amount": 50}, headers=H).status_code == 200
    status, tasks = state(Session, uid)
    assert status == "active" and len(tasks) == 1 and tasks[0].payload["status"] == "active" and tasks[0].payload["data_limit"] == 150


def test_bulk_extend_restores_expired(env):
    c, Session, H = env
    uid = add_user(Session, status="expired", used=0, expire=PAST)
    assert c.post("/api/bulk/extend", json={"user_ids": [uid], "amount": 30}, headers=H).status_code == 200
    status, tasks = state(Session, uid)
    assert status == "active" and len(tasks) == 1 and tasks[0].payload["status"] == "active"


def test_bulk_traffic_keeps_limited_if_still_over(env):
    c, Session, H = env
    uid = add_user(Session, used=500)
    c.post("/api/bulk/traffic", json={"user_ids": [uid], "amount": 50}, headers=H)
    assert state(Session, uid)[0] == "limited"


def test_admin_reset_usage_and_recharge_restore_users(env):
    c, Session, H = env
    a, b = add_user(Session, "a"), add_user(Session, "b")
    assert c.post("/api/admins/2/reset-usage", headers=H).status_code == 200
    assert state(Session, a)[0] == "active" and state(Session, a)[1][0].payload["status"] == "active"
    with Session() as db:
        x = db.get(models.User, b); x.used_traffic = 100; db.commit()
    assert c.post("/api/admins/2/recharge", json={"reset_usage": True}, headers=H).status_code == 200
    assert state(Session, b)[0] == "active"
