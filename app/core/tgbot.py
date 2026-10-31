"""Telegram bot (long-polling via getUpdates). An admin links a chat with a one-time code created in the dashboard;
an unlinked chat gets nothing. Linked admins only ever receive their own events (see notify.py)."""
import hashlib
import logging
import secrets
import time
from datetime import datetime, timezone
import httpx
from sqlalchemy import func
from app.config import settings
from app.db.models import Admin, Panel, Setting, User
from app.db.session import SessionLocal

log = logging.getLogger("jinxdata.tgbot")
CODE_TTL = 600
_bot_name: str | None = None


def _h(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def make_link_code(db, admin: Admin) -> str:
    now = time.time()
    for s in db.query(Setting).filter(Setting.key.like("tglink:%")).all():  # drop expired + this admin's older codes
        v = s.value if isinstance(s.value, dict) else {}
        if v.get("exp", 0) < now or v.get("admin_id") == admin.id: db.delete(s)
    code = secrets.token_urlsafe(12)
    db.add(Setting(key=f"tglink:{_h(code)}", value={"admin_id": admin.id, "exp": now + CODE_TTL}))
    db.commit()
    return code


def bot_username() -> str | None:
    global _bot_name
    if _bot_name or not settings.telegram_bot_token: return _bot_name
    try:
        r = httpx.get(f"https://api.telegram.org/bot{settings.telegram_bot_token}/getMe", timeout=5)
        _bot_name = (r.json().get("result") or {}).get("username")
    except Exception as exc:
        log.warning("getMe failed: %s", type(exc).__name__)
    return _bot_name


def _link(db, chat_id: str, code: str) -> str:
    s = db.get(Setting, f"tglink:{_h(code.strip())}")
    v = s.value if s and isinstance(s.value, dict) else None
    if not v or v.get("exp", 0) < time.time():
        if s: db.delete(s); db.commit()
        return "❌ کد نامعتبر یا منقضی است. از پنل (اکانت من ← تلگرام) کد جدید بگیرید."
    admin = db.get(Admin, int(v["admin_id"]))
    db.delete(s)
    if not admin or admin.disabled:
        db.commit(); return "❌ اکانت ادمین فعال نیست."
    for other in db.query(Admin).filter(Admin.telegram_id == chat_id, Admin.id != admin.id).all(): other.telegram_id = None
    admin.telegram_id = chat_id; db.commit()
    return f"✅ متصل شد: {admin.username}\nاز این پس فقط پیام‌های مربوط به اکانت شما ارسال می‌شود.\n/status وضعیت · /stop قطع اتصال"


def _status(db, a: Admin) -> str:
    if a.role == "sudo":
        total = db.query(func.count(User.id)).scalar() or 0; act = db.query(func.count(User.id)).filter(User.status == "active").scalar() or 0
        down = db.query(func.count(Panel.id)).filter(Panel.enabled.is_(True), Panel.status == "down").scalar() or 0
        return f"👤 {a.username} (مدیر اصلی)\nکاربران: {total} (فعال: {act})\nپنل‌های قطع: {down}"
    q = db.query(User).filter(User.admin_id == a.id)
    used = int(q.with_entities(func.coalesce(func.sum(User.used_traffic), 0)).scalar() or 0)
    gb = lambda v: f"{v / 1024 ** 3:.2f} GB"
    exp = a.expire.strftime("%Y-%m-%d") if a.expire else "نامحدود"
    return (f"👤 {a.username}\nکاربران: {q.count()} / {a.max_users if a.max_users is not None else '∞'}\n"
            f"مصرف: {gb(used)} / {gb(a.max_total_traffic) if a.max_total_traffic is not None else '∞'}\nانقضا: {exp}")


def handle_text(chat_id: str, text: str) -> str | None:
    """Pure command handler (returns the reply text) so it can be tested without Telegram."""
    parts = (text or "").strip().split(maxsplit=1)
    if not parts or not parts[0].startswith("/"): return None
    cmd = parts[0].split("@")[0].lower(); arg = parts[1] if len(parts) > 1 else ""
    with SessionLocal() as db:
        me = db.query(Admin).filter(Admin.telegram_id == chat_id).first()
        if cmd == "/start" and arg: return _link(db, chat_id, arg)
        if cmd == "/start" or cmd == "/help":
            if me and not me.disabled: return f"سلام {me.username} 👋\n/status وضعیت اکانت\n/stop قطع اتصال"
            return "برای دریافت پیام‌ها، در پنل بخش «اکانت من ← ربات تلگرام» لینک اتصال بگیرید و اینجا باز کنید."
        if not me or me.disabled: return "اتصال برقرار نیست؛ ابتدا از پنل لینک اتصال بگیرید."
        if cmd == "/status": return _status(db, me)
        if cmd == "/stop":
            me.telegram_id = None; db.commit(); return "اتصال قطع شد."
    return None


def _offset(db) -> int:
    s = db.get(Setting, "tg:offset")
    return int(s.value.get("v", 0)) if s and isinstance(s.value, dict) else 0


async def poll_updates() -> int:
    if not settings.telegram_bot_token: return 0
    api = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
    with SessionLocal() as db: off = _offset(db)
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"{api}/getUpdates", json={"offset": off, "timeout": 0, "limit": 20, "allowed_updates": ["message"]})
            ups = r.json().get("result") or []
            for up in ups:
                off = max(off, int(up.get("update_id", 0)) + 1)
                m = up.get("message") or {}; chat = m.get("chat") or {}
                if chat.get("type") != "private" or "text" not in m: continue
                try: reply = handle_text(str(chat["id"]), m["text"][:200])
                except Exception as exc:
                    log.warning("bot command failed: %s", type(exc).__name__); reply = None
                if reply: await c.post(f"{api}/sendMessage", json={"chat_id": chat["id"], "text": reply})
    except Exception as exc:
        log.warning("telegram poll failed: %s", type(exc).__name__); return 0
    with SessionLocal() as db:
        db.merge(Setting(key="tg:offset", value={"v": off})); db.commit()
    return len(ups)
