import pytest
from app.config import settings
from app.core import tgbot


def test_clean_tg_id():
    assert tgbot.clean_tg_id(" 123456789 ") == "123456789"
    assert tgbot.clean_tg_id("۱۲۳۴۵۶۷۸۹") == "123456789"
    assert tgbot.clean_tg_id("") is None and tgbot.clean_tg_id(None) is None
    assert tgbot.clean_tg_id("-1001234567890") == "-1001234567890"
    for bad in ("abc", "12", "@user", "12 34 56"):
        with pytest.raises(ValueError): tgbot.clean_tg_id(bad)


def test_webhook_url(monkeypatch):
    monkeypatch.setattr(settings, "panel_domain", "")
    monkeypatch.setattr(settings, "public_base_url", "https://panel.example.com/")
    assert tgbot.webhook_url() == "https://panel.example.com/api/telegram/webhook"
    monkeypatch.setattr(settings, "public_base_url", "http://1.2.3.4:8000")
    assert tgbot.webhook_url() is None  # no HTTPS -> polling fallback
    monkeypatch.setattr(settings, "panel_domain", "p.example.com")
    assert tgbot.webhook_url() == "https://p.example.com/api/telegram/webhook"
    monkeypatch.setattr(settings, "public_base_url", "https://panel.example.com:8000")
    monkeypatch.setattr(settings, "panel_domain", "")
    assert tgbot.webhook_url() is None  # Telegram only allows 443/80/88/8443
