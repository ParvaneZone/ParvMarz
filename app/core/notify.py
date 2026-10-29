"""Fire-and-forget notifications: Telegram (admin chat + the owning agent's telegram_id) and a generic webhook."""
import asyncio
import logging
import httpx
from app.config import settings
from app.db.models import Admin
from app.db.session import SessionLocal

log = logging.getLogger("jinxdata.notify")
_TITLES = {
    "user.limited": "⛔ حجم کاربر تمام شد", "user.expired": "⌛ اشتراک کاربر منقضی شد",
    "user.expiring": "⏰ اشتراک نزدیک انقضاست", "panel.down": "🔴 پنل قطع شد", "panel.up": "🟢 پنل وصل شد",
}


def _chat_ids(admin_id) -> list[str]:
    ids = [settings.telegram_admin_chat_id] if settings.telegram_admin_chat_id else []
    if admin_id is not None:
        with SessionLocal() as db:
            a = db.get(Admin, int(admin_id))
            if a and a.telegram_id and a.telegram_id not in ids:
                ids.append(a.telegram_id)
    return ids


async def _send(event: str, data: dict) -> None:
    async with httpx.AsyncClient(timeout=10) as c:
        if settings.webhook_url:
            try:
                await c.post(settings.webhook_url, json={"event": event, **data},
                             headers={"X-Webhook-Secret": settings.webhook_secret} if settings.webhook_secret else {})
            except Exception as exc:
                log.warning("webhook failed: %s", type(exc).__name__)
        if settings.telegram_bot_token:
            text = _TITLES.get(event, event) + "\n" + "\n".join(f"{k}: {v}" for k, v in data.items() if k != "admin_id")
            for chat in _chat_ids(data.get("admin_id")):
                try:
                    await c.post(f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                                 json={"chat_id": chat, "text": text})
                except Exception as exc:
                    log.warning("telegram failed: %s", type(exc).__name__)


def notify_event(event: str, data: dict) -> None:
    if not (settings.webhook_url or settings.telegram_bot_token):
        return
    try:
        asyncio.get_running_loop().create_task(_send(event, data))
    except RuntimeError:
        pass
