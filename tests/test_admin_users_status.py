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
    Session = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    with Session() as db:
        db.add_all([models.Admin(username="root", password_hash=hash_password("x" * 12), role="sudo", permissions={"*": True}),
                    models.Admin(username="agent", password_hash=hash_password("x" * 12), role="admin", permissions={}, allowed_services=[]),
                    models.Admin(username="agent2", password_hash=hash_password("x" * 12), role="admin", permissions={}, allowed_services=[]),
                    models.Panel(name="p1", type="marzban", base_url="http://p1"),
                    models.Panel(name="p2", type="marzban", base_url="http://p2"),
                    models.Service(name="s", display_name="S")])
        db.commit()
        db.add_all([models.User(username="u1", admin_id=2, service_id=1, status="active"),
                    models.User(username="u2", admin_id=2, service_id=1, status="active"),
                    models.User(username="noacc", admin_id=2, service_id=1, status="active"),
                    models.User(username="theirs", admin_id=3, service_id=1, status="active")])
        db.commit()
        db.add_all([models.UserPanelAccount(user_id=1, panel_id=1, remote_username="u1"),
                    models.UserPanelAccount(user_id=1, panel_id=2, remote_username="pre_u1"),
                    models.UserPanelAccount(user_id=2, panel_id=1, remote_username="u2"),
                    models.UserPanelAccount(user_id=4, panel_id=1, remote_username="theirs")])
        db.commit()
        root = db.query(models.Admin).filter_by(username="root").one()
        tok = create_access_token(root)
    app = FastAPI()
    app.include_router(admins.router)

    def _db():
        with Session() as d:
            yield d
    app.dependency_overrides[get_db] = _db
    return TestClient(app), Session, {"Authorization": f"Bearer {tok}"}


def test_users_status_queues_sync_task_per_panel_account(env):
    c, Session, H = env
    r = c.post("/api/admins/2/users-status", json={"status": "disabled"}, headers=H)
    assert r.status_code == 200 and r.json() == {"updated": 3}
    with Session() as db:
        tasks = db.query(models.SyncTask).order_by(models.SyncTask.id).all()
        assert all(u.status == "disabled" for u in db.query(models.User).filter_by(admin_id=2))
        assert db.query(models.User).filter_by(username="theirs").one().status == "active"
    assert len(tasks) == 3  # u1 on two panels + u2 on one; no account => nothing to sync; other admin untouched
    assert {(t.user_id, t.panel_id, t.payload["username"]) for t in tasks} == {(1, 1, "u1"), (1, 2, "pre_u1"), (2, 1, "u2")}
    assert all(t.action == "modify" and t.state == "pending" and t.payload["status"] == "disabled" for t in tasks)


def test_users_status_reactivation_also_syncs(env):
    c, Session, H = env
    c.post("/api/admins/2/users-status", json={"status": "disabled"}, headers=H)
    assert c.post("/api/admins/2/users-status", json={"status": "active"}, headers=H).status_code == 200
    with Session() as db:
        tasks = db.query(models.SyncTask).order_by(models.SyncTask.id).all()
    assert len(tasks) == 6 and {t.payload["status"] for t in tasks[3:]} == {"active"}


def test_users_status_invalid_status_creates_nothing(env):
    c, Session, H = env
    assert c.post("/api/admins/2/users-status", json={"status": "bogus"}, headers=H).status_code == 422
    with Session() as db:
        assert db.query(models.SyncTask).count() == 0
