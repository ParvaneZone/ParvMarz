from app.config import settings
from app.routers.subscription import _public_base


class _Req:
    base_url = "http://evil.example/"


def test_public_base_never_uses_host(monkeypatch):
    monkeypatch.setattr(settings, "public_base_url", "http://localhost:8000")
    monkeypatch.setattr(settings, "sub_port", None)
    assert "evil.example" not in _public_base(_Req())
