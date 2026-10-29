import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.config import settings
from app.db.models import Admin, ApiKey
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


KEY_PREFIX = "pmk_"
_key_failures: dict[str, list[float]] = {}


def hash_api_key(key: str) -> str:
    return hmac.new((settings.jwt_secret + ":apikey").encode(), key.encode(), hashlib.sha256).hexdigest()


def new_api_key() -> tuple[str, str, str]:
    """(full key, public prefix, hash). The full key is shown once and never stored."""
    prefix = secrets.token_hex(4)
    key = f"{KEY_PREFIX}{prefix}.{secrets.token_urlsafe(32)}"
    return key, prefix, hash_api_key(key)


def _key_fail(request: Request, code: str):
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    hits = [t for t in _key_failures.get(ip, []) if now - t < 900] + [now]
    _key_failures[ip] = hits
    raise HTTPException(401, detail={"detail": "کلید API نامعتبر است", "code": code})


def _admin_from_key(token: str, request: Request, db: Session) -> Admin:
    ip = request.client.host if request.client else "unknown"
    now = time.time()
    if len([t for t in _key_failures.get(ip, []) if now - t < 900]) >= 20:
        raise HTTPException(429, detail={"detail": "تلاش‌های ناموفق زیاد است؛ بعداً دوباره تلاش کنید", "code": "API_KEY_LOCKED"})
    prefix = token[len(KEY_PREFIX):].split(".", 1)[0]
    row = db.query(ApiKey).filter(ApiKey.key_prefix == prefix).first()
    if not row or row.revoked or not hmac.compare_digest(row.key_hash, hash_api_key(token)):
        _key_fail(request, "INVALID_API_KEY")
    if row.expire:
        exp = row.expire if row.expire.tzinfo else row.expire.replace(tzinfo=timezone.utc)
        if exp <= datetime.now(timezone.utc):
            _key_fail(request, "API_KEY_EXPIRED")
    admin = db.get(Admin, row.admin_id)
    if not admin or admin.disabled or admin.role == "sudo":
        _key_fail(request, "INVALID_API_KEY")
    last = row.last_used_at
    if last is not None and not last.tzinfo:
        last = last.replace(tzinfo=timezone.utc)
    if last is None or (datetime.now(timezone.utc) - last).total_seconds() > 60:
        row.last_used_at = datetime.now(timezone.utc)
        db.commit()
    return admin


def current_admin(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_api_key: str | None = Header(default=None, alias="X-API-Key", description="کلید API ادمین (به‌جای توکن)"),
    db: Session = Depends(get_db),
) -> Admin:
    token = x_api_key or (creds.credentials if creds else None)
    if not token:
        raise HTTPException(401, detail={"detail": "احراز هویت لازم است", "code": "AUTH_REQUIRED"})
    if token.startswith(KEY_PREFIX):
        admin = _admin_from_key(token, request, db)
        request.state.auth_via = "key"
        return admin
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
        admin = db.get(Admin, int(payload["sub"]))
    except Exception:
        admin = None
        payload = {}
    if not admin or admin.disabled:
        raise HTTPException(401, detail={"detail": "توکن نامعتبر است", "code": "INVALID_TOKEN"})
    if admin.password_reset_at and payload.get("password_reset_at") != admin.password_reset_at.isoformat():
        raise HTTPException(401, detail={"detail": "رمز تغییر کرده؛ دوباره وارد شوید", "code": "TOKEN_REVOKED"})
    request.state.auth_via = "jwt"
    return admin


def session_admin(request: Request, admin: Admin = Depends(current_admin)) -> Admin:
    """Login-session only: API keys may not change passwords, 2FA or manage keys."""
    if getattr(request.state, "auth_via", "jwt") == "key":
        raise HTTPException(403, detail={"detail": "این عملیات فقط با ورود عادی (نه کلید API) مجاز است", "code": "SESSION_REQUIRED"})
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
