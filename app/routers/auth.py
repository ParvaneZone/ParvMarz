from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.config import settings
from app.db.models import Admin
from app.db.session import get_db
from app.core.security import hash_password, verify_password, create_access_token, current_admin

router = APIRouter(prefix="/api/admin", tags=["auth"])
_login_attempts: dict[str, list[float]] = {}


class LoginInput(BaseModel):
    username: str
    password: str


class PasswordInput(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=200)


@router.post("/token")
def login(body: LoginInput, request: Request, db: Session = Depends(get_db)):
    import time
    limited = settings.login_rate_limit_enabled
    ip = request.client.host if request.client else "unknown"
    key=f"{ip}:{body.username.lower()}"
    now=time.time(); attempts=[t for t in _login_attempts.get(key,[]) if now-t<settings.login_lock_seconds] if limited else []
    if limited: _login_attempts[key]=attempts
    if limited and len(attempts)>=settings.login_max_attempts:
        raise HTTPException(429, detail={"detail":"تلاش‌های ورود زیاد است؛ ۱۵ دقیقه بعد دوباره تلاش کنید", "code":"LOGIN_LOCKED"})
    admin = db.query(Admin).filter(func.lower(Admin.username) == body.username.lower()).first()
    if not admin or admin.disabled or not verify_password(body.password, admin.password_hash):
        if limited:
            attempts.append(now); _login_attempts[key]=attempts
        raise HTTPException(401, detail={"detail": "نام کاربری یا رمز عبور نادرست است", "code": "BAD_CREDENTIALS"})
    _login_attempts.pop(key, None)
    return {"access_token": create_access_token(admin), "token_type": "bearer"}


@router.get("")
def whoami(admin: Admin = Depends(current_admin)):
    return {"id": admin.id, "username": admin.username, "role": admin.role, "permissions": admin.permissions}


@router.post("/password")
def change_password(body: PasswordInput, admin: Admin = Depends(current_admin), db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    if not verify_password(body.current_password, admin.password_hash):
        raise HTTPException(400, detail={"detail": "رمز فعلی نادرست است", "code": "BAD_PASSWORD"})
    admin.password_hash = hash_password(body.new_password)
    admin.password_reset_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}
