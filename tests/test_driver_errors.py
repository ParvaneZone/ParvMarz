import httpx
import pytest
import respx

from app.drivers.base import RemoteOutcomeUnknown
from app.drivers.marzban import MarzbanDriver
from app.drivers.pasarguard import PasarGuardDriver
from app.drivers.rebecca import RebeccaDriver

M = "https://mz.example.com"
R = "https://rb.example.com"
P = "https://pg.example.com"


@respx.mock
async def test_marzban_token_is_renewed_after_401():
    token = respx.post(M + "/api/admin/token").mock(return_value=httpx.Response(200, json={"access_token": "t"}))
    route = respx.get(M + "/api/system").mock(side_effect=[httpx.Response(401), httpx.Response(200, json={"ok": 1})])
    d = MarzbanDriver(M, {"username": "a", "password": "b"})
    assert (await d.test_connection())["ok"] is True
    assert route.call_count == 2 and token.call_count == 2


@respx.mock
async def test_marzban_timeout_gives_clear_error_and_limited_retry():
    respx.post(M + "/api/admin/token").mock(return_value=httpx.Response(200, json={"access_token": "t"}))
    route = respx.get(M + "/api/system").mock(side_effect=httpx.ReadTimeout("slow"))
    d = MarzbanDriver(M, {"username": "a", "password": "b"})
    with pytest.raises(RuntimeError, match="failed after retry"):
        await d.test_connection()
    assert route.call_count == 2


@respx.mock
async def test_marzban_create_conflict_is_idempotent_and_delete_404_is_ignored():
    respx.post(M + "/api/admin/token").mock(return_value=httpx.Response(200, json={"access_token": "t"}))
    respx.post(M + "/api/user").mock(return_value=httpx.Response(409, json={"detail": "exists"}))
    respx.get(M + "/api/user/u").mock(return_value=httpx.Response(200, json={"username": "u"}))
    put = respx.put(M + "/api/user/u").mock(return_value=httpx.Response(200, json={"username": "u"}))
    respx.delete(M + "/api/user/gone").mock(return_value=httpx.Response(404))
    d = MarzbanDriver(M, {"username": "a", "password": "b"})
    assert (await d.create_user({"username": "u", "data_limit": 5}))["username"] == "u"
    assert put.called
    await d.delete_user("gone")


@respx.mock
async def test_rebecca_two_factor_login_gives_clear_message():
    respx.post(R + "/api/admin/token").mock(return_value=httpx.Response(428, json={"detail": "2FA code required"}))
    d = RebeccaDriver(R, {"username": "a", "password": "b"})
    with pytest.raises(RuntimeError, match="two-factor"):
        await d.test_connection()


@respx.mock
async def test_rebecca_real_bulk_is_never_retried_after_lost_response():
    route = respx.post(R + "/api/users/actions").mock(
        side_effect=[httpx.Response(200, json={"affected": 1}), httpx.ReadTimeout("lost")])
    d = RebeccaDriver(R, {"api_key": "rk_x"})
    with pytest.raises(RemoteOutcomeUnknown):
        await d.bulk_action("disable_users", {"usernames": ["u"]})
    assert route.call_count == 2


@respx.mock
async def test_pasarguard_api_key_falls_back_to_authorization_header():
    route = respx.get(P + "/api/admin").mock(side_effect=[httpx.Response(401), httpx.Response(200, json={"username": "a"})])
    d = PasarGuardDriver(P, {"api_key": "pg_key_a"})
    assert (await d.test_connection())["ok"] is True
    assert route.calls[0].request.headers["x-api-key"] == "pg_key_a"
    assert route.calls[1].request.headers["authorization"] == "apikey pg_key_a"
