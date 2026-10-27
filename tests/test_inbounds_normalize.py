import httpx
import pytest
import respx

from app.drivers.base import normalize_inbounds
from app.drivers.pasarguard import PasarGuardDriver
from app.drivers.rebecca import RebeccaDriver


def test_pasarguard_style_plain_tag_strings():
    rows = normalize_inbounds(["VLESS TCP", "VMESS WS"])
    assert [r["tag"] for r in rows] == ["VLESS TCP", "VMESS WS"]


def test_marzban_style_protocol_map_and_tls_becomes_security():
    rows = normalize_inbounds({"vless": [{"tag": "A", "tls": "none"}], "vmess": [{"tag": "B", "tls": "tls"}]})
    assert {(r["protocol"], r["tag"], r["security"]) for r in rows} == {("vless", "A", "none"), ("vmess", "B", "tls")}


def test_items_wrapper_dedupes_and_ignores_junk():
    rows = normalize_inbounds({"items": [{"id": 1, "tag": "a"}, {"id": 2, "tag": "a"}, None, {}], "total": 4})
    assert [r["tag"] for r in rows] == ["a"]
    assert normalize_inbounds(None) == [] and normalize_inbounds("x") == []


@respx.mock
@pytest.mark.asyncio
async def test_pasarguard_inbounds_endpoint_returning_strings():
    respx.get("https://p.example.com/api/inbounds").mock(return_value=httpx.Response(200, json=["in-a", "in-b"]))
    respx.get("https://p.example.com/api/hosts").mock(return_value=httpx.Response(200, json=[{"inbound_tag": "in-a", "security": "tls"}]))
    d = PasarGuardDriver("https://p.example.com", {"username": "a", "password": "pg_key_x"})
    rows = await d.list_inbounds()
    assert [r["tag"] for r in rows] == ["in-a", "in-b"] and rows[0]["security"] == "tls"


@respx.mock
@pytest.mark.asyncio
async def test_rebecca_falls_back_to_plain_inbounds_route_when_full_is_empty():
    respx.get("https://r.example.com/api/inbounds/full").mock(return_value=httpx.Response(200, json={"items": []}))
    respx.get("https://r.example.com/api/inbounds").mock(return_value=httpx.Response(200, json={"items": [{"id": 1, "tag": "x", "protocol": "vless"}]}))
    d = RebeccaDriver("https://r.example.com", {"username": "a", "password": "rk_x"})
    assert [r["tag"] for r in await d.list_inbounds()] == ["x"]
