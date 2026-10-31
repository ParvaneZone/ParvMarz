"""Telegram bot (long-polling via getUpdates). An admin links a chat with a one-time code created in the dashboard;
an unlinked chat gets nothing. Linked admins only ever receive their own events (see notify.py)."""
import hashlib
import hmac
import logging
import secrets
import httpx
from sqlalchemy import func
from app.config import settings
from app.db.models import Admin, Panel, Setting, User
from app.db.session import SessionLocal

log = logging.getLogger("jinxdata.tgbot")
_bot_name: str | None = None


def _h(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def make_link_code(db, admin: Admin) -> str:
    for s in db.query(Setting).filter(Setting.key.like("tglink:%")).all():  # a new code replaces this admin's older one
        if isinstance(s.value, dict) and s.value.get("admin_id") == admin.id: db.delete(s)
    code = secrets.token_urlsafe(12)
    db.add(Setting(key=f"tglink:{_h(code)}", value={"admin_id": admin.id}))
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
    if not v:
        return "❌ کد نامعتبر است یا قبلاً استفاده شده. از پنل (اکانت من ← ربات تلگرام) لینک جدید بگیرید."
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


def webhook_secret() -> str:
    return hmac.new(settings.jwt_secret.encode(), b"telegram-webhook", hashlib.sha256).hexdigest()[:48]


def process_update(up: dict) -> dict | None:
    """Telegram update -> webhook-response dict (Telegram sends it as the reply), or None."""
    m = (up or {}).get("message") or {}; chat = m.get("chat") or {}
    if chat.get("type") != "private" or not isinstance(m.get("text"), str): return None
    try: reply = handle_text(str(chat["id"]), m["text"][:200])
    except Exception as exc:
        log.warning("bot command failed: %s", type(exc).__name__); return None
    return {"method": "sendMessage", "chat_id": chat["id"], "text": reply} if reply else None


async def set_webhook() -> bool:
    """Register this panel's webhook with Telegram (called on startup). Needs a public HTTPS PUBLIC_BASE_URL."""
    if not settings.telegram_bot_token: return False
    url = settings.public_base_url.rstrip("/") + "/api/telegram/webhook"
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.post(f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook",
                             json={"url": url, "secret_token": webhook_secret(), "allowed_updates": ["message"], "max_connections": 5})
        ok = bool(r.json().get("ok"))
        if not ok: log.warning("setWebhook rejected (needs public HTTPS on port 443/80/88/8443): %s", str(r.json().get("description"))[:120])
        return ok
    except Exception as exc:
        log.warning("setWebhook failed: %s", type(exc).__name__); return False
