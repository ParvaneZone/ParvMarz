from datetime import datetime, timedelta, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.security import create_access_token, hash_password
from app.db import models
from app.db.session import Base, get_db
from app.routers import users, bulk, reports, auth


def make():
    eng = create_engine("sqlite://", future=True, poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    S = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    with S() as db:
        svc = models.Service(name="s", display_name="S"); db.add(svc)
        root = models.Admin(username="root", password_hash=hash_password("x" * 12), role="sudo", permissions={"*": True})
        ag = models.Admin(username="ag", password_hash=hash_password("x" * 12), role="admin", permissions={}, max_user_days=30, max_user_traffic=10 * 2**30)
        ag2 = models.Admin(username="ag2", password_hash=hash_password("x" * 12), role="admin", permissions={})
        db.add_all([root, ag, ag2]); db.flush()
        for n, adm, exp in (("a1", ag, now + timedelta(days=2)), ("a2", ag, now + timedelta(days=20)), ("b1", ag2, now + timedelta(days=2))):
            db.add(models.User(username=n, admin_id=adm.id, service_id=svc.id, data_limit=2**30, used_traffic=2**29, expire=exp))
        db.commit()
        tok = {a.username: create_access_token(a) for a in db.query(models.Admin)}
    app = FastAPI()
    for r in (auth.router, users.router, bulk.router, reports.router): app.include_router(r)
    def _db():
        with S() as d: yield d
    app.dependency_overrides[get_db] = _db
    return TestClient(app), S, tok


def H(t): return {"Authorization": f"Bearer {t}"}


def test_edit_keeps_subscription_link():
    c, S, tok = make()
    before = c.get("/api/user/a1", headers=H(tok["ag"])).json()["subscription_url"]
    assert c.put("/api/user/a1", json={"note": "x"}, headers=H(tok["ag"])).status_code == 200
    assert c.get("/api/user/a1", headers=H(tok["ag"])).json()["subscription_url"] == before
    assert c.post("/api/user/a1/revoke_sub", headers=H(tok["ag"])).status_code == 200
    assert c.get("/api/user/a1", headers=H(tok["ag"])).json()["subscription_url"] != before


def test_list_filters_and_sort():
    c, S, tok = make()
    r = c.get("/api/users?expiring_in_days=5&sort=username", headers=H(tok["root"])).json()
    assert [u["username"] for u in r["items"]] == ["a1", "b1"]
    assert c.get("/api/users?near_limit_percent=50", headers=H(tok["root"])).json()["total"] == 3
    assert c.get("/api/users?near_limit_percent=60", headers=H(tok["root"])).json()["total"] == 0


def test_bulk_agent_scope_and_quota():
    c, S, tok = make()
    with S() as db: ids = {u.username: u.id for u in db.query(models.User)}
    r = c.post("/api/bulk/extend", json={"user_ids": [ids["a1"], ids["b1"]], "amount": 5}, headers=H(tok["ag"]))
    assert r.json() == {"updated": 1}  # b1 belongs to another agent
    assert c.post("/api/bulk/extend", json={"user_ids": [ids["a2"]], "amount": 20}, headers=H(tok["ag"])).status_code == 403
    assert c.post("/api/bulk/traffic", json={"user_ids": [ids["a1"]], "amount": 20 * 2**30}, headers=H(tok["ag"])).status_code == 403


def test_reports_audit_csv():
    c, S, tok = make()
    assert c.get("/api/reports/summary", headers=H(tok["root"])).json()["users_by_status"]
    assert c.get("/api/users/export.csv", headers=H(tok["ag"])).text.count("\n") == 3
    assert c.get("/api/audit", headers=H(tok["ag"])).status_code == 403
    assert c.get("/api/audit", headers=H(tok["root"])).status_code == 200


def test_login_lock_persists_in_db():
    c, S, tok = make()
    for _ in range(5): c.post("/api/admin/token", json={"username": "ag", "password": "bad"})
    with S() as db: assert db.query(models.Setting).filter(models.Setting.key.like("login:%")).count() == 1


def test_admin_create_errors_are_specific():
    from app.routers import admins
    from app.main import validation_error  # noqa: F401
    c, S, tok = make()
    c.app.include_router(admins.router)
    from fastapi.exceptions import RequestValidationError
    c.app.add_exception_handler(RequestValidationError, validation_error)
    h = H(tok["root"])
    r = c.post("/api/admins", json={"username": "ab", "password": "short"}, headers=h)
    d = r.json()["detail"]
    assert r.status_code == 422 and d["code"] == "VALIDATION_ERROR" and "رمز" in d["detail"] and "نام کاربری" in d["detail"]
    r = c.post("/api/admins", json={"username": "newadmin", "password": "x" * 12, "permissions": {"nope": True}}, headers=h)
    assert r.json()["detail"]["invalid_keys"] == ["nope"]
    r = c.post("/api/admins", json={"username": "newadmin", "password": "x" * 12, "allowed_services": [999]}, headers=h)
    assert r.json()["detail"]["code"] == "SERVICE_NOT_FOUND"
    r = c.post("/api/admins", json={"username": "newadmin", "password": "x" * 12}, headers=h)
    assert r.status_code == 200 and len(r.json()["warnings"]) == 2
