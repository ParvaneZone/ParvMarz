"""Fire-and-forget notifications: Telegram + a generic webhook.

Routing: every event goes to the sudo chats (TELEGRAM_ADMIN_CHAT_ID + linked sudo admins). An event that carries
`admin_id` also goes to that one admin's linked chat (never to other admins), unless it is sudo-only."""
import asyncio
import logging
import threading
import time
import httpx
from app.config import settings
from app.db.models import Admin
from app.db.session import SessionLocal

log = logging.getLogger("jinxdata.notify")
_TITLES = {
    "user.limited": "⛔ حجم کاربر تمام شد", "user.expired": "⌛ اشتراک کاربر منقضی شد",
    "user.expiring": "⏰ اشتراک کاربر نزدیک انقضاست", "panel.down": "🔴 پنل قطع شد", "panel.up": "🟢 پنل وصل شد",
    "admin.login": "🔐 ورود ادمین", "admin.login_failed": "⚠️ ورود ناموفق به اکانت ادمین", "admin.locked": "🚫 قفل شدن ورود (تلاش زیاد)",
    "admin.expired": "⌛ اکانت ادمین منقضی شد", "admin.expiring": "⏰ اکانت ادمین نزدیک انقضاست", "admin.traffic_full": "⛔ حجم کل ادمین تمام شد",
    "error.critical": "🚨 خطای مهم سیستم", "sync.failed": "❗ همگام‌سازی با پنل ناموفق ماند", "backup.failed": "❗ پشتیبان‌گیری ناموفق بود",
}
_LABELS = {"username": "نام کاربری", "ip": "آیپی", "time": "زمان", "reason": "علت", "panel": "پنل", "error": "خطا", "expire": "انقضا",
           "path": "مسیر", "method": "متد", "action": "عملیات", "attempts": "تعداد تلاش", "used": "مصرف", "limit": "سقف", "user": "کاربر"}
SUDO_ONLY = {"panel.down", "panel.up", "error.critical", "sync.failed", "backup.failed"}
_err_seen: dict[str, float] = {}


def _chat_ids(event: str, admin_id) -> list[str]:
    ids = [settings.telegram_admin_chat_id] if settings.telegram_admin_chat_id else []
    with SessionLocal() as db:
        for a in db.query(Admin).filter(Admin.role == "sudo", Admin.telegram_id.is_not(None), Admin.disabled.is_(False)).all():
            if a.telegram_id not in ids: ids.append(a.telegram_id)
        if admin_id is not None and event not in SUDO_ONLY:
            a = db.get(Admin, int(admin_id))
            if a and a.telegram_id and not a.disabled and a.telegram_id not in ids: ids.append(a.telegram_id)
    return ids


def format_message(event: str, data: dict) -> str:
    lines = [_TITLES.get(event, event)]
    lines += [f"{_LABELS.get(k, k)}: {str(v)[:300]}" for k, v in data.items() if k != "admin_id" and v not in (None, "")]
    return "\n".join(lines)


async def tg_send(c: httpx.AsyncClient, chat, text: str) -> None:
    try:
        await c.post(f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                     json={"chat_id": chat, "text": text[:3500], "disable_web_page_preview": True})
    except Exception as exc:
        log.warning("telegram failed: %s", type(exc).__name__)


async def _send(event: str, data: dict) -> None:
    async with httpx.AsyncClient(timeout=10) as c:
        if settings.webhook_url:
            try:
                await c.post(settings.webhook_url, json={"event": event, **data},
                             headers={"X-Webhook-Secret": settings.webhook_secret} if settings.webhook_secret else {})
            except Exception as exc:
                log.warning("webhook failed: %s", type(exc).__name__)
        if settings.telegram_bot_token:
            try: chats = await asyncio.to_thread(_chat_ids, event, data.get("admin_id"))
            except Exception as exc:
                log.warning("telegram recipients failed: %s", type(exc).__name__); return
            text = format_message(event, data)
            for chat in chats: await tg_send(c, chat, text)


def notify_event(event: str, data: dict) -> None:
    """Safe from async code and from sync request threads."""
    if not (settings.webhook_url or settings.telegram_bot_token):
        return
    try:
        asyncio.get_running_loop().create_task(_send(event, data))
    except RuntimeError:
        threading.Thread(target=lambda: asyncio.run(_send(event, data)), daemon=True).start()


def report_error(where: str, exc_type: str, method: str = "", throttle: int = 600) -> None:
    """Critical-error alert (sudo only). Never includes exception text, query strings or bodies; throttled per place+type."""
    key = f"{where}|{exc_type}"; now = time.time()
    if now - _err_seen.get(key, 0) < throttle: return
    if len(_err_seen) > 500: _err_seen.clear()
    _err_seen[key] = now
    notify_event("error.critical", {"path": where, "method": method, "error": exc_type})
