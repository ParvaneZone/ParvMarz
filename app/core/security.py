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
