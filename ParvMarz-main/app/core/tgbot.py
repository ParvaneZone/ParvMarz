"""Telegram bot. The panel wires the bot up by itself: run_bot() (started with the app) registers the webhook and
re-checks it every few minutes; if no public HTTPS URL is available it falls back to long-polling (getUpdates), so
nobody ever has to call setWebhook by hand.

An admin is connected either by the sudo typing the admin's numeric Telegram ID in the admin form, or by the admin
opening a link code from the dashboard. Neither expires. Linked admins only ever receive their own events (notify.py)."""
import asyncio
import hashlib
import hmac
import logging
import re
import secrets
from urllib.parse import urlsplit
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


_TG_ID = re.compile(r"-?\d{5,20}")


def clean_tg_id(v) -> str | None:
    """Numeric Telegram ID typed in a form -> normalized string; empty -> None; anything else -> ValueError."""
    v = str(v if v is not None else "").strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    if not v: return None
    if not _TG_ID.fullmatch(v): raise ValueError("آیدی عددی تلگرام نامعتبر است (فقط عدد، مثلاً 123456789)")
    return v


def send_text_sync(chat_id: str, text: str) -> bool:
    """Best-effort single message (used to confirm a freshly saved ID). False if Telegram refused (e.g. user never pressed Start)."""
    if not settings.telegram_bot_token: return False
    try:
        r = httpx.post(f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                       json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True}, timeout=8)
        return bool(r.json().get("ok"))
    except Exception as exc:
        log.warning("sendMessage failed: %s", type(exc).__name__); return False


def webhook_url() -> str | None:
    """Public HTTPS URL Telegram should call, or None when this panel is not reachable over HTTPS (-> polling)."""
    base = settings.public_base_url.rstrip("/")
    if not base.startswith("https://") and settings.panel_domain: base = "https://" + settings.panel_domain
    if not base.startswith("https://"): return None
    if (urlsplit(base).port or 443) not in (443, 80, 88, 8443): return None
    return base + "/api/telegram/webhook"


async def ensure_webhook() -> str:
    """Make Telegram point at this panel. Returns 'webhook' (registered) or 'polling' (no usable public HTTPS URL)."""
    url = webhook_url(); api = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
    async with httpx.AsyncClient(timeout=15) as c:
        if not url:
            await c.post(f"{api}/deleteWebhook", json={"drop_pending_updates": False}); return "polling"
        info = (await c.get(f"{api}/getWebhookInfo")).json().get("result") or {}
        if info.get("url") == url and not info.get("last_error_message"): return "webhook"
        r = await c.post(f"{api}/setWebhook", json={"url": url, "secret_token": webhook_secret(),
                                                    "allowed_updates": ["message"], "max_connections": 5})
        ok = bool(r.json().get("ok"))
        if not ok: log.warning("setWebhook rejected, using polling: %s", str(r.json().get("description"))[:120])
        return "webhook" if ok else "polling"


async def _poll(seconds: int) -> None:
    """Long-polling for a while (then the supervisor re-checks whether a webhook became possible)."""
    api = f"https://api.telegram.org/bot{settings.telegram_bot_token}"; offset = 0
    loop = asyncio.get_running_loop(); end = loop.time() + seconds
    async with httpx.AsyncClient(timeout=40) as c:
        while loop.time() < end:
            r = await c.post(f"{api}/getUpdates", json={"offset": offset, "timeout": 25, "allowed_updates": ["message"]})
            data = r.json()
            if not data.get("ok"): raise RuntimeError("getUpdates rejected")
            for up in data.get("result") or []:
                offset = max(offset, int(up.get("update_id", 0)) + 1)
                reply = await asyncio.to_thread(process_update, up)
                if reply: await c.post(f"{api}/{reply.pop('method')}", json=reply)


async def run_bot() -> None:
    """Supervisor started with the app: never raises, retries with backoff, and re-checks the webhook periodically."""
    if not settings.telegram_bot_token: return
    delay = 5
    while True:
        try:
            if await ensure_webhook() == "webhook": await asyncio.sleep(300)
            else: await _poll(600)
            delay = 5
        except asyncio.CancelledError: raise
        except Exception as exc:
            log.warning("telegram bot loop: %s (retry in %ss)", type(exc).__name__, delay)
            await asyncio.sleep(delay); delay = min(delay * 2, 300)


async def set_webhook() -> bool:  # kept for compatibility
    return (await ensure_webhook()) == "webhook"
