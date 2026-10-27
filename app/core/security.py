from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.config import settings
from app.db.models import Admin
from app.db.session import get_db

bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except (ValueError, TypeError):
        return False


def create_access_token(admin: Admin) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(admin.id), "username": admin.username, "role": admin.role,
                       "iat": now, "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
                       "password_reset_at": admin.password_reset_at.isoformat() if admin.password_reset_at else None},
                      settings.jwt_secret, algorithm="HS256")


def current_admin(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> Admin:
    if not creds:
        raise HTTPException(401, detail={"detail": "احراز هویت لازم است", "code": "AUTH_REQUIRED"})
    try:
        payload = jwt.decode(creds.credentials, settings.jwt_secret, algorithms=["HS256"])
        admin = db.get(Admin, int(payload["sub"]))
    except Exception:
        admin = None
        payload = {}
    if not admin or admin.disabled:
        raise HTTPException(401, detail={"detail": "توکن نامعتبر است", "code": "INVALID_TOKEN"})
    if admin.password_reset_at and payload.get("password_reset_at") != admin.password_reset_at.isoformat():
        raise HTTPException(401, detail={"detail": "رمز تغییر کرده؛ دوباره وارد شوید", "code": "TOKEN_REVOKED"})
    return admin


def require_sudo(admin: Admin = Depends(current_admin)) -> Admin:
    if admin.role != "sudo":
        raise HTTPException(403, detail={"detail": "دسترسی مدیر اصلی لازم است", "code": "FORBIDDEN"})
    return admin


SUSPEND_ALLOWED = {"users.view", "users.view_sub", "users.usage_logs", "users.delete", "dashboard.view", "services.view", "templates.view"}


def admin_state(admin: Admin, db: Session) -> str:
    """active | disabled | expired | traffic_exhausted. Computed live, so recharging restores access instantly."""
    if admin.role == "sudo": return "active"
    if admin.disabled: return "disabled"
    if admin.expire:
        exp = admin.expire if admin.expire.tzinfo else admin.expire.replace(tzinfo=timezone.utc)
        if exp <= datetime.now(timezone.utc): return "expired"
    if admin.max_total_traffic is not None:
        from sqlalchemy import func
        from app.db.models import User
        used = db.query(func.coalesce(func.sum(User.used_traffic), 0)).filter(User.admin_id == admin.id).scalar() or 0
        if used >= admin.max_total_traffic: return "traffic_exhausted"
    return "active"


def require_perm(key: str):
    from app.core.permissions import has_perm

    def dep(admin: Admin = Depends(current_admin), db: Session = Depends(get_db)) -> Admin:
        if key not in SUSPEND_ALLOWED and admin_state(admin, db) != "active":
            raise HTTPException(403, detail={"detail": "حساب شما معلق است (اتمام زمان یا حجم)؛ با مدیر اصلی تماس بگیرید", "code": "ADMIN_SUSPENDED"})
        if not has_perm(admin, key):
            raise HTTPException(403, detail={"detail": "این دسترسی برای شما فعال نیست", "code": "PERMISSION_DENIED"})
        return admin
    return dep
