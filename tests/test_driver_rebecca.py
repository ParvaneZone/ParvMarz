import httpx
import respx

from app.drivers.rebecca import RebeccaDriver

B = "https://r.example.com"


def _d():
    return RebeccaDriver(B, {"username": "x", "password": "rk_test"})


@respx.mock
async def test_groups_are_services_and_key_auth():
    route = respx.get(B + "/api/v2/services").mock(
        return_value=httpx.Response(200, json=[{"id": 3, "display_name": "Gold"}]))
    groups = await _d().list_groups()
    assert groups[0]["id"] == 3
    assert route.calls[0].request.headers["authorization"] == "Bearer rk_test"


@respx.mock
async def test_create_strips_inbounds_and_is_idempotent():
    respx.post(B + "/api/user").mock(return_value=httpx.Response(409, json={"detail": "exists"}))
    put = respx.put(B + "/api/user/u1").mock(return_value=httpx.Response(200, json={}))
    await _d().create_user({"username": "u1", "service_id": 3, "data_limit": 5, "expire": 0,
                            "inbounds": {"vless": ["a"]}, "proxies": {"vless": {}}})
    assert b"inbounds" not in put.calls[0].request.content


@respx.mock
async def test_usages_batch():
    respx.get(B + "/api/users").mock(return_value=httpx.Response(
        200, json={"users": [{"username": "U1", "used_traffic": 9}], "total": 1}))
    assert await _d().get_usages(["u1", "u2"]) == {"u1": 9}
