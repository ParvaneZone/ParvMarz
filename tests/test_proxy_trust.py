import pytest
from starlette.requests import Request
from app.config import Settings, settings
from app.core.netip import real_ip


def _req(peer: str, **headers) -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "query_string": b"",
                    "headers": [(k.replace("_", "-").encode(), v.encode()) for k, v in headers.items()],
                    "client": (peer, 1234)})


@pytest.fixture
def trust(monkeypatch):
    def _set(on: bool, ips: str = ""):
        monkeypatch.setattr(settings, "trust_proxy_headers", on)
        monkeypatch.setattr(settings, "trusted_proxy_ips", ips)
    return _set


def test_trust_proxy_headers_off_by_default():
    s = Settings(_env_file=None)
    assert s.trust_proxy_headers is False
    assert s.trusted_proxy_ips == ""


def test_headers_ignored_when_trust_off(trust):
    trust(False, "10.0.0.1")
    assert real_ip(_req("10.0.0.1", x_real_ip="6.6.6.6")) == "10.0.0.1"


def test_headers_ignored_when_trusted_list_empty(trust):
    trust(True, "")
    assert real_ip(_req("203.0.113.5", x_real_ip="6.6.6.6", x_forwarded_for="6.6.6.6")) == "203.0.113.5"


def test_headers_ignored_from_untrusted_peer(trust):
    trust(True, "10.0.0.1")
    r = _req("203.0.113.5", cf_connecting_ip="6.6.6.6", x_real_ip="7.7.7.7", x_forwarded_for="8.8.8.8")
    assert real_ip(r) == "203.0.113.5"


def test_headers_honoured_from_trusted_peer(trust):
    trust(True, "10.0.0.0/8")
    assert real_ip(_req("10.1.2.3", cf_connecting_ip="1.2.3.4")) == "1.2.3.4"
    assert real_ip(_req("10.1.2.3", x_real_ip="1.2.3.5")) == "1.2.3.5"


def test_invalid_header_falls_back_to_peer(trust):
    trust(True, "10.0.0.1")
    assert real_ip(_req("10.0.0.1", x_real_ip="not-an-ip", x_forwarded_for="junk")) == "10.0.0.1"


def test_xff_uses_first_untrusted_hop_from_right(trust):
    trust(True, "10.0.0.1,10.0.0.2")
    # client-forged leftmost value must not win
    r = _req("10.0.0.1", x_forwarded_for="6.6.6.6, 9.9.9.9, 10.0.0.2")
    assert real_ip(r) == "9.9.9.9"


def test_login_and_api_key_lock_cannot_be_bypassed_with_forged_header(trust):
    # both locks key on real_ip(): rotating a forged header must keep resolving to the same socket IP
    trust(True, "10.0.0.1")
    ips = {real_ip(_req("203.0.113.5", x_real_ip=f"1.1.1.{i}", x_forwarded_for=f"2.2.2.{i}")) for i in range(20)}
    assert ips == {"203.0.113.5"}
