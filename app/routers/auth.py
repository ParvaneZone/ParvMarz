import re
import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.core import totp
from app.core.crypto import decrypt_secret, encrypt_secret
from app.core.security import hash_password, verify_password, create_access_token, current_admin, session_admin
from app.db.models import Admin, AuditLog, Service, User
from app.db.session import get_db
from app.schemas import AccountOut, OkOut, TokenOut, WhoAmIOut, errs

router = APIRouter(prefix="/api/admin", tags=["auth"])
_login_attempts: dict[str, list[float]] = {}


class LoginInput(BaseModel):
    username: str
    password: str
    otp: str | None = Field(default=None, max_length=32)


class PasswordInput(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=200)


def _err(status: int, detail: str, code: str) -> HTTPException:
    return HTTPException(status, detail={"detail": detail, "code": code})


def _check_second_factor(admin: Admin, code: str, db: Session) -> bool:
    """Accept a fresh TOTP code (no replay) or an unused recovery code."""
    try:
        secret = decrypt_secret(admin.totp_secret_enc or "")
    except Exception:
        secret = ""
    if secret:
        step = totp.verify(secret, code, admin.totp_last_step)
        if step is not None:
            admin.totp_last_step = step
            db.commit()
            return True
    remaining = totp.consume_recovery(admin.recovery_codes, code)
    if remaining is not None:
        admin.recovery_codes = remaining
        db.add(AuditLog(actor_admin_id=admin.id, action="admin.2fa.recovery_used", object_type="admin",
                        object_id=str(admin.id), details={"left": len(remaining)}))
        db.commit()
        return True
    return False


@router.post("/token", response_model=TokenOut, response_model_exclude_unset=True, summary="ورود و دریافت توکن",
             description="با 2FA فعال و بدون otp، پاسخ `{two_factor_required: true}` است؛ همان درخواست را با otp تکرار کنید. بعد از ۵ تلاش ناموفق ۱۵ دقیقه قفل می‌شود (429).",
             responses=errs(401, 429))
def login(body: LoginInput, request: Request, db: Session = Depends(get_db)):
    limited = settings.login_rate_limit_enabled
    ip = request.client.host if request.client else "unknown"
    key = f"{ip}:{body.username.lower()}"
    now = time.time()
    attempts = [t for t in _login_attempts.get(key, []) if now - t < settings.login_lock_seconds] if limited else []
    if limited:
        _login_attempts[key] = attempts
    if limited and len(attempts) >= settings.login_max_attempts:
        raise HTTPException(429, detail={"detail": "تلاش‌های ورود زیاد است؛ ۱۵ دقیقه بعد دوباره تلاش کنید", "code": "LOGIN_LOCKED"})

    def fail(detail: str, code: str):
        if limited:
            attempts.append(now)
            _login_attempts[key] = attempts
        raise _err(401, detail, code)

    admin = db.query(Admin).filter(func.lower(Admin.username) == body.username.lower()).first()
    if not admin or admin.disabled or not verify_password(body.password, admin.password_hash):
        fail("نام کاربری یا رمز عبور نادرست است", "BAD_CREDENTIALS")
    if admin.totp_enabled:
        otp = (body.otp or "").strip()
        if not otp:  # password was right; ask the client for the second factor
            return {"two_factor_required": True}
        if not _check_second_factor(admin, otp, db):
            fail("کد دو مرحله‌ای نادرست است", "BAD_OTP")
    _login_attempts.pop(key, None)
    return {"access_token": create_access_token(admin), "token_type": "bearer"}


@router.get("", response_model=WhoAmIOut, summary="اطلاعات ادمین جاری", responses=errs(401))
def whoami(admin: Admin = Depends(current_admin)):
    return {"id": admin.id, "username": admin.username, "role": admin.role, "permissions": admin.permissions,
            "totp_enabled": bool(admin.totp_enabled)}


@router.post("/password", response_model=OkOut, summary="تغییر رمز (فقط با ورود عادی)", responses=errs(401, 403))
def change_password(body: PasswordInput, admin: Admin = Depends(session_admin), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, admin.password_hash):
        raise HTTPException(400, detail={"detail": "رمز فعلی نادرست است", "code": "BAD_PASSWORD"})
    admin.password_hash = hash_password(body.new_password)
    admin.password_reset_at = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


# ----------------------------------------------------------------------------- my account
@router.get("/account", response_model=AccountOut, summary="خلاصه سهمیه و مصرف ادمین جاری", responses=errs(401))
def my_account(admin: Admin = Depends(current_admin), db: Session = Depends(get_db)):
    """Quota/usage summary of the signed-in admin (their own users only)."""
    mine = db.query(User).filter(User.admin_id == admin.id)
    by_status = dict(db.query(User.status, func.count(User.id)).filter(User.admin_id == admin.id)
                     .group_by(User.status).all())
    used = int(mine.with_entities(func.coalesce(func.sum(User.used_traffic), 0)).scalar() or 0)
    allocated = int(mine.with_entities(func.coalesce(func.sum(User.data_limit), 0)).scalar() or 0)
    unlimited_users = mine.filter(User.data_limit.is_(None)).count()
    total = admin.max_total_traffic
    expire = admin.expire
    days_left = None
    if expire is not None:
        exp = expire if expire.tzinfo else expire.replace(tzinfo=timezone.utc)
        days_left = (exp - datetime.now(timezone.utc)).days
    if admin.role == "sudo":
        services = [{"id": s.id, "name": s.display_name} for s in db.query(Service).order_by(Service.sort_order, Service.id)]
    else:
        ids = admin.allowed_services or []
        services = [{"id": s.id, "name": s.display_name} for s in db.query(Service).filter(Service.id.in_(ids))] if ids else []
    return {
        "id": admin.id, "username": admin.username, "role": admin.role, "disabled": admin.disabled,
        "created_at": admin.created_at, "expire": expire, "days_left": days_left,
        "totp_enabled": bool(admin.totp_enabled),
        "recovery_codes_left": len(admin.recovery_codes or []) if admin.totp_enabled else 0,
        "traffic": {
            "total": total,  # None = unlimited
            "used": used,
            "remaining": None if total is None else max(total - used, 0),
            "allocated": allocated,  # sum of data_limit given to users (what quotas are checked against)
            "unallocated": None if total is None else max(total - allocated, 0),
            "unlimited_users": unlimited_users,
        },
        "users": {"count": sum(by_status.values()), "max": admin.max_users, "by_status": by_status},
        "limits": {"max_user_traffic": admin.max_user_traffic, "max_user_days": admin.max_user_days},
        "services": services,
    }


# ----------------------------------------------------------------------------- UI preferences
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


@router.get("/preferences")
def get_preferences(admin: Admin = Depends(current_admin)):
    return admin.ui_prefs or {}


@router.put("/preferences")
def put_preferences(body: dict, admin: Admin = Depends(current_admin), db: Session = Depends(get_db)):
    clean: dict = {}
    if body.get("lang") in ("fa", "en"):
        clean["lang"] = body["lang"]
    if body.get("theme") in ("light", "dark", "oled"):
        clean["theme"] = body["theme"]
    for key in ("accent", "bg"):
        value = body.get(key)
        if value is None or value == "":
            clean[key] = None
        elif isinstance(value, str) and _HEX.match(value):
            clean[key] = value.lower()
    admin.ui_prefs = clean
    db.commit()
    return clean


# ----------------------------------------------------------------------------- 2FA (optional)
class TwoFASetupInput(BaseModel):
    password: str


class TwoFAEnableInput(BaseModel):
    code: str = Field(min_length=6, max_length=16)


class TwoFADisableInput(BaseModel):
    password: str
    code: str = Field(min_length=6, max_length=32)


@router.post("/2fa/setup")
def twofa_setup(body: TwoFASetupInput, admin: Admin = Depends(session_admin), db: Session = Depends(get_db)):
    """Step 1: create a pending secret. 2FA stays OFF until /2fa/enable proves the app works."""
    if admin.totp_enabled:
        raise _err(409, "احراز هویت دو مرحله‌ای از قبل فعال است", "TOTP_ALREADY_ENABLED")
    if not verify_password(body.password, admin.password_hash):
        raise _err(400, "رمز فعلی نادرست است", "BAD_PASSWORD")
    secret = totp.new_secret()
    try:
        admin.totp_secret_enc = encrypt_secret(secret)
    except RuntimeError as exc:
        raise _err(503, str(exc), "CRYPTO_NOT_CONFIGURED") from exc
    admin.totp_last_step = None
    db.commit()
    return {"secret": secret, "otpauth_uri": totp.provisioning_uri(secret, admin.username, settings.app_name)}


@router.post("/2fa/enable")
def twofa_enable(body: TwoFAEnableInput, admin: Admin = Depends(session_admin), db: Session = Depends(get_db)):
    """Step 2: confirm with a code from the app. Returns one-time recovery codes."""
    if admin.totp_enabled:
        raise _err(409, "احراز هویت دو مرحله‌ای از قبل فعال است", "TOTP_ALREADY_ENABLED")
    if not admin.totp_secret_enc:
        raise _err(409, "ابتدا مرحلهٔ راه‌اندازی را انجام دهید", "TOTP_NOT_SET_UP")
    try:
        secret = decrypt_secret(admin.totp_secret_enc)
    except ValueError as exc:
        raise _err(409, "راه‌اندازی را دوباره انجام دهید", "TOTP_NOT_SET_UP") from exc
    step = totp.verify(secret, body.code)
    if step is None:
        raise _err(400, "کد نادرست است؛ ساعت گوشی را بررسی و دوباره تلاش کنید", "BAD_OTP")
    codes = totp.new_recovery_codes()
    admin.totp_enabled = True
    admin.totp_last_step = step
    admin.recovery_codes = [totp.hash_recovery(c) for c in codes]
    db.add(AuditLog(actor_admin_id=admin.id, action="admin.2fa.enable", object_type="admin",
                    object_id=str(admin.id), details={}))
    db.commit()
    return {"ok": True, "recovery_codes": [totp.format_code(c) for c in codes]}


@router.post("/2fa/disable")
def twofa_disable(body: TwoFADisableInput, admin: Admin = Depends(session_admin), db: Session = Depends(get_db)):
    if not admin.totp_enabled:
        raise _err(409, "احراز هویت دو مرحله‌ای فعال نیست", "TOTP_NOT_ENABLED")
    if not verify_password(body.password, admin.password_hash):
        raise _err(400, "رمز فعلی نادرست است", "BAD_PASSWORD")
    if not _check_second_factor(admin, body.code, db):
        raise _err(400, "کد دو مرحله‌ای نادرست است", "BAD_OTP")
    admin.totp_enabled = False
    admin.totp_secret_enc = None
    admin.totp_last_step = None
    admin.recovery_codes = []
    db.add(AuditLog(actor_admin_id=admin.id, action="admin.2fa.disable", object_type="admin",
                    object_id=str(admin.id), details={}))
    db.commit()
    return {"ok": True}
