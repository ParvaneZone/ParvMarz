from starlette.requests import Request
from app.config import settings
from app.routers import subscription


def _req(host: str) -> Request:
    return Request({"type": "http", "method": "GET", "path": "/sub/x", "query_string": b"", "scheme": "http",
                    "server": (host, 80), "client": ("203.0.113.5", 1234), "headers": [(b"host", host.encode())]})


def test_forged_host_is_never_used_when_public_url_is_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "sub_port", None)
    monkeypatch.setattr(settings, "public_base_url", "http://localhost:8000")  # the default = not configured
    assert subscription._public_base(_req("evil.example.com")) == ""


def test_empty_public_url_also_gives_no_host_based_link(monkeypatch):
    monkeypatch.setattr(settings, "sub_port", None)
    monkeypatch.setattr(settings, "public_base_url", "")
    assert subscription._public_base(_req("evil.example.com")) == ""


def test_configured_public_url_wins_over_the_host_header(monkeypatch):
    monkeypatch.setattr(settings, "sub_port", None)
    monkeypatch.setattr(settings, "public_base_url", "https://panel.example.com/")
    assert subscription._public_base(_req("evil.example.com")) == "https://panel.example.com"


def test_split_mode_uses_the_sub_url_and_ignores_host(monkeypatch):
    monkeypatch.setattr(settings, "sub_port", 8001)
    monkeypatch.setattr(settings, "sub_public_base_url", "https://sub.example.com:8001")
    assert subscription._public_base(_req("evil.example.com")) == "https://sub.example.com:8001"
    monkeypatch.setattr(settings, "sub_public_base_url", "")
    monkeypatch.setattr(settings, "public_base_url", "http://localhost:8000")
    assert subscription._public_base(_req("evil.example.com")) == ""
