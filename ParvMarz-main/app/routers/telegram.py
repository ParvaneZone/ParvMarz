import asyncio
import hmac
from fastapi import APIRouter, Request, Response
from app.core.tgbot import process_update, webhook_secret

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.post("/webhook", include_in_schema=False)
async def webhook(request: Request):
    """Called by Telegram only; the secret header is set by this panel via setWebhook. Anything else gets 403."""
    if not hmac.compare_digest(request.headers.get("x-telegram-bot-api-secret-token", ""), webhook_secret()):
        return Response(status_code=403)
    try: up = await request.json()
    except Exception: return Response(status_code=200)
    return (await asyncio.to_thread(process_update, up)) or {}
