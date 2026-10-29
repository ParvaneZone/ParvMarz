from datetime import datetime, timedelta, timezone
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.security import create_access_token, hash_password
from app.db import models
from app.db.session import Base, get_db
from app.routers import api_keys, docs_api, users, auth, services, templates


@pytest.fixture()
def env():
    eng = create_engine("sqlite://", future=True, poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng, autoflush=False, expire_on_commit=False)
    with Session() as db:
        db.add_all([models.Admin(username="root", password_hash=hash_password("x" * 12), role="sudo", permissions={"*": True}),
                    models.Admin(username="agent", password_hash=hash_password("x" * 12), role="admin", permissions={}, allowed_services=[]),
                    models.Admin(username="agent2", password_hash=hash_password("x" * 12), role="admin", permissions={}, allowed_services=[])])
        db.commit()
    app = FastAPI()
    for r in (auth.router, users.router, services.router, templates.router, api_keys.router, docs_api.router):
        app.include_router(r)
    def _db():
        with Session() as d:
            yield d
    app.dependency_overrides[get_db] = _db
    with Session() as db:
        tok = {a.username: create_access_token(a) for a in db.query(models.Admin).all()}
    return TestClient(app), Session, tok


def H(t): return {"Authorization": f"Bearer {t}"}


def test_key_lifecycle_and_limits(env):
    c, Session, tok = env
    r = c.post("/api/admin/api-keys", json={"name": "bot"}, headers=H(tok["agent"]))
    assert r.status_code == 200
    key = r.json()["key"]
    assert key.startswith("pmk_")
    with Session() as db:  # only a hash is stored
        row = db.query(models.ApiKey).one()
        assert key not in (row.key_hash, row.key_prefix) and len(row.key_hash) == 64
    assert c.get("/api/admin", headers={"X-API-Key": key}).json()["username"] == "agent"
    assert c.get("/api/admin", headers=H(key)).status_code == 200  # also as Bearer
    assert c.get("/api/users", headers={"X-API-Key": key}).status_code == 200
    # key cannot manage keys / password / 2FA
    assert c.post("/api/admin/api-keys", json={"name": "x"}, headers={"X-API-Key": key}).status_code == 403
    assert c.post("/api/admin/password", json={"current_password": "x" * 12, "new_password": "y" * 12}, headers={"X-API-Key": key}).status_code == 403
    for i in range(4):
        assert c.post("/api/admin/api-keys", json={"name": f"k{i}"}, headers=H(tok["agent"])).status_code == 200
    assert c.post("/api/admin/api-keys", json={"name": "extra"}, headers=H(tok["agent"])).status_code == 409
    kid = c.get("/api/admin/api-keys", headers=H(tok["agent"])).json()[-1]["id"]
    assert c.delete(f"/api/admin/api-keys/{kid}", headers={"X-API-Key": key}).status_code == 403
    assert c.delete(f"/api/admin/api-keys/{kid}", headers=H(tok["agent"])).status_code == 200


def test_invalid_expired_revoked_disabled_and_sudo(env):
    c, Session, tok = env
    key = c.post("/api/admin/api-keys", json={"name": "bot"}, headers=H(tok["agent"])).json()["key"]
    assert c.get("/api/admin", headers={"X-API-Key": key + "x"}).status_code == 401
    assert c.get("/api/admin", headers={"X-API-Key": "pmk_deadbeef.zzz"}).status_code == 401
    with Session() as db:
        row = db.query(models.ApiKey).one(); row.expire = datetime.now(timezone.utc) - timedelta(seconds=1); db.commit()
    assert c.get("/api/admin", headers={"X-API-Key": key}).json()["detail"]["code"] == "API_KEY_EXPIRED"
    with Session() as db:
        row = db.query(models.ApiKey).one(); row.expire = None; db.commit()
        assert c.get("/api/admin", headers={"X-API-Key": key}).status_code == 200
        db.query(models.Admin).filter_by(username="agent").one().disabled = True; db.commit()
    assert c.get("/api/admin", headers={"X-API-Key": key}).status_code == 401
    with Session() as db:
        a = db.query(models.Admin).filter_by(username="agent").one(); a.disabled = False
        db.query(models.ApiKey).one().revoked = True; db.commit()
    assert c.get("/api/admin", headers={"X-API-Key": key}).status_code == 401
    sid = 1  # sudo gets no keys
    assert c.post(f"/api/admins/{sid}/api-keys", json={"name": "x"}, headers=H(tok["root"])).status_code == 422


def test_sudo_manages_agent_keys_and_scope(env):
    c, _, tok = env
    assert c.post("/api/admins/2/api-keys", json={"name": "bot"}, headers=H(tok["agent"])).status_code == 403
    r = c.post("/api/admins/2/api-keys", json={"name": "bot", "expire_days": 30}, headers=H(tok["root"]))
    assert r.status_code == 200 and r.json()["expire"]
    assert len(c.get("/api/admins/2/api-keys", headers=H(tok["root"])).json()) == 1
    assert c.get("/api/admins/3/api-keys", headers=H(tok["root"])).json() == []
    kid = r.json()["id"]
    assert c.delete(f"/api/admins/3/api-keys/{kid}", headers=H(tok["root"])).status_code == 404  # wrong owner


def test_docs_are_private_and_role_filtered(env):
    c, _, tok = env
    assert c.get("/api/docs/openapi.json").status_code == 401
    full = c.get("/api/docs/openapi.json", headers=H(tok["root"])).json()
    agent = c.get("/api/docs/openapi.json", headers=H(tok["agent"])).json()
    assert "/api/usage" not in agent["paths"] and "/api/user/{username}/set-owner" not in agent["paths"]
    assert "/api/user/{username}" in agent["paths"] and "/api/admin/api-keys" in agent["paths"]
    assert "/api/user/{username}/set-owner" in full["paths"]
    assert "/api/admins/{admin_id}/api-keys" not in agent["paths"]
    md = c.get("/api/docs/api.md", headers=H(tok["agent"])).text
    assert "X-API-Key" in md and "/api/users" in md and "set-owner" not in md
    assert "pmk_" not in str(agent.get("components", {}).get("schemas", {}).get("ApiKeyOut", {}))


def test_existing_json_shape_unchanged(env):
    c, Session, tok = env
    with Session() as db:
        db.add(models.Service(name="s", display_name="S")); db.commit()
    r = c.post("/api/admin/token", json={"username": "agent", "password": "x" * 12})
    assert set(r.json()) == {"access_token", "token_type"}
    me = c.get("/api/admin", headers=H(tok["agent"])).json()
    assert set(me) == {"id", "username", "role", "permissions", "totp_enabled"}
    sv = c.get("/api/services", headers=H(tok["root"])).json()[0]
    assert "items" in sv and "inbound_names" not in sv
