import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.security import create_access_token, hash_password
from app.db import models
from app.db.session import Base, get_db
from app.routers import admins


@pytest.fixture()
def env():
    eng = create_engine("sqlite://", future=True, poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    with S() as db:
        svc = models.Service(name="s", display_name="S")
        root = models.Admin(username="root", password_hash=hash_password("x" * 12), role="sudo", permissions={"*": True})
        ag = models.Admin(username="ag", password_hash=hash_password("x" * 12), role="admin", permissions={})
        ag2 = models.Admin(username="ag2", password_hash=hash_password("x" * 12), role="admin", permissions={})
        p1 = models.Panel(name="p1", type="rebecca", base_url="http://p1")
        p2 = models.Panel(name="p2", type="marzban", base_url="http://p2")
        db.add_all([svc, root, ag, ag2, p1, p2]); db.flush()
        owners = {"u1": ag, "u2": ag, "x1": ag2}
        panels = {"u1": (p1, p2), "u2": (p1,), "x1": (p1,)}
        users = {}
        for name, owner in owners.items():
            u = models.User(username=name, admin_id=owner.id, service_id=svc.id, status="active")
            db.add(u); db.flush(); users[name] = u
            for p in panels[name]:
                db.add(models.UserPanelAccount(user_id=u.id, panel_id=p.id, remote_username=f"{p.name}_{name}", sync_state="synced"))
        db.commit()
        ids = {"ag": ag.id, "u1": users["u1"].id, "u2": users["u2"].id, "x1": users["x1"].id}
        tok = {a.username: create_access_token(a) for a in db.query(models.Admin)}
    app = FastAPI()
    app.include_router(admins.router)

    def _db():
        with S() as d:
            yield d
    app.dependency_overrides[get_db] = _db
    return TestClient(app), S, tok, ids


def H(t): return {"Authorization": f"Bearer {t}"}


def test_users_status_queues_a_sync_task_per_panel_account(env):
    c, S, tok, ids = env
    r = c.post(f"/api/admins/{ids['ag']}/users-status", json={"status": "disabled"}, headers=H(tok["root"]))
    assert r.status_code == 200 and r.json() == {"updated": 2}
    with S() as db:
        tasks = db.query(models.SyncTask).all()
        assert len(tasks) == 3  # u1 has two panel accounts, u2 one; the other admin's user is untouched
        assert {t.action for t in tasks} == {"modify"} and {t.state for t in tasks} == {"pending"}
        assert {t.payload["status"] for t in tasks} == {"disabled"}
        assert {t.payload["username"] for t in tasks} == {"p1_u1", "p2_u1", "p1_u2"}
        assert {t.user_id for t in tasks} == {ids["u1"], ids["u2"]}
        assert {u.username: u.status for u in db.query(models.User)} == {"u1": "disabled", "u2": "disabled", "x1": "active"}


def test_enabling_again_is_pushed_too(env):
    c, S, tok, ids = env
    for status in ("disabled", "active"):
        assert c.post(f"/api/admins/{ids['ag']}/users-status", json={"status": status}, headers=H(tok["root"])).status_code == 200
    with S() as db:
        tasks = db.query(models.SyncTask).order_by(models.SyncTask.id).all()
    assert [t.payload["status"] for t in tasks] == ["disabled"] * 3 + ["active"] * 3


def test_invalid_status_creates_nothing(env):
    c, S, tok, ids = env
    r = c.post(f"/api/admins/{ids['ag']}/users-status", json={"status": "nope"}, headers=H(tok["root"]))
    assert r.status_code == 422
    with S() as db:
        assert db.query(models.SyncTask).count() == 0
