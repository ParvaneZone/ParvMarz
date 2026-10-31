from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.security import new_api_key, require_sudo, session_admin
from app.db.models import Admin, ApiKey, AuditLog
from app.db.session import get_db
from app.schemas import ApiKeyCreate, ApiKeyCreated, ApiKeyOut, OkOut, errs

router = APIRouter(tags=["api-keys"])
MAX_ACTIVE = 5


def _aware(d):
    return d if d is None or d.tzinfo else d.replace(tzinfo=timezone.utc)


def _active(row: ApiKey) -> bool:
    return not row.revoked and not (row.expire and _aware(row.expire) <= datetime.now(timezone.utc))


def _out(k: ApiKey) -> dict:
    return {"id": k.id, "name": k.name, "key_prefix": k.key_prefix, "created_at": k.created_at,
            "last_used_at": k.last_used_at, "expire": k.expire, "revoked": k.revoked}


def _create(target: Admin, body: ApiKeyCreate, actor: Admin, db: Session) -> dict:
    if target.role == "sudo":
        raise HTTPException(422, detail={"detail": "برای مدیر اصلی (sudo) کلید API صادر نمی‌شود", "code": "SUDO_API_KEY"})
    if sum(1 for k in db.query(ApiKey).filter_by(admin_id=target.id).all() if _active(k)) >= MAX_ACTIVE:
        raise HTTPException(409, detail={"detail": f"حداکثر {MAX_ACTIVE} کلید فعال مجاز است", "code": "API_KEY_LIMIT"})
    key, prefix, digest = new_api_key()
    row = ApiKey(admin_id=target.id, name=body.name, key_prefix=prefix, key_hash=digest,
                 expire=datetime.now(timezone.utc) + timedelta(days=body.expire_days) if body.expire_days else None)
    db.add(row); db.flush()
    db.add(AuditLog(actor_admin_id=actor.id, action="api_key.create", object_type="api_key", object_id=str(row.id),
                    details={"admin_id": target.id, "name": body.name}))
    db.commit(); db.refresh(row)
    return {**_out(row), "key": key}


def _revoke(target_id: int, key_id: int, actor: Admin, db: Session) -> dict:
    row = db.query(ApiKey).filter_by(id=key_id, admin_id=target_id).first()
    if not row:
        raise HTTPException(404, detail={"detail": "کلید پیدا نشد", "code": "API_KEY_NOT_FOUND"})
    row.revoked = True
    db.add(AuditLog(actor_admin_id=actor.id, action="api_key.revoke", object_type="api_key", object_id=str(row.id),
                    details={"admin_id": target_id}))
    db.commit()
    return {"ok": True}


# ---- هر ادمین برای خودش (فقط با ورود عادی، نه با خود کلید API)
@router.post("/api/admin/api-keys", response_model=ApiKeyCreated, summary="ساخت کلید API برای خودم",
             description="کلید کامل فقط همین یک‌بار برگردانده می‌شود. حداکثر ۵ کلید فعال. با هدر `X-API-Key` یا `Authorization: Bearer <key>` استفاده می‌شود.",
             responses=errs(401, 403, 409))
def create_my_key(body: ApiKeyCreate, admin: Admin = Depends(session_admin), db: Session = Depends(get_db)):
    return _create(admin, body, admin, db)


@router.get("/api/admin/api-keys", response_model=list[ApiKeyOut], summary="کلیدهای API من", responses=errs(401, 403))
def list_my_keys(admin: Admin = Depends(session_admin), db: Session = Depends(get_db)):
    return [_out(k) for k in db.query(ApiKey).filter_by(admin_id=admin.id).order_by(ApiKey.id.desc()).all()]


@router.delete("/api/admin/api-keys/{key_id}", response_model=OkOut, summary="ابطال کلید API من", responses=errs(401, 403, 404))
def revoke_my_key(key_id: int, admin: Admin = Depends(session_admin), db: Session = Depends(get_db)):
    return _revoke(admin.id, key_id, admin, db)


# ---- مدیر اصلی برای هر ادمین
@router.post("/api/admins/{admin_id}/api-keys", response_model=ApiKeyCreated, summary="ساخت کلید API برای ادمین",
             responses=errs(401, 403, 404, 409))
def create_admin_key(admin_id: int, body: ApiKeyCreate, actor: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    target = db.get(Admin, admin_id)
    if not target:
        raise HTTPException(404, detail={"detail": "ادمین پیدا نشد", "code": "ADMIN_NOT_FOUND"})
    return _create(target, body, actor, db)


@router.get("/api/admins/{admin_id}/api-keys", response_model=list[ApiKeyOut], summary="کلیدهای API یک ادمین", responses=errs(401, 403, 404))
def list_admin_keys(admin_id: int, _: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    if not db.get(Admin, admin_id):
        raise HTTPException(404, detail={"detail": "ادمین پیدا نشد", "code": "ADMIN_NOT_FOUND"})
    return [_out(k) for k in db.query(ApiKey).filter_by(admin_id=admin_id).order_by(ApiKey.id.desc()).all()]


@router.delete("/api/admins/{admin_id}/api-keys/{key_id}", response_model=OkOut, summary="ابطال کلید API یک ادمین", responses=errs(401, 403, 404))
def revoke_admin_key(admin_id: int, key_id: int, actor: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    return _revoke(admin_id, key_id, actor, db)
