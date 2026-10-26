import httpx
import respx

from app.drivers.pasarguard import PasarGuardDriver

B = "https://pg.example.com"


@respx.mock
async def test_api_key_header_and_groups():
    route = respx.get(B + "/api/groups/simple").mock(
        return_value=httpx.Response(200, json={"groups": [{"id": 2, "name": "G"}, {"id": 3, "name": "off", "is_disabled": True}]}))
    d = PasarGuardDriver(B, {"username": "", "password": "pg_key_abc"})
    assert await d.list_groups() == [{"id": 2, "name": "G"}]
    assert route.calls[0].request.headers["x-api-key"] == "pg_key_abc"


@respx.mock
async def test_create_uses_group_ids_and_iso_expire():
    route = respx.post(B + "/api/user").mock(return_value=httpx.Response(201, json={}))
    d = PasarGuardDriver(B, {"username": "", "password": "pg_key_abc"})
    await d.create_user({"username": "u", "service_id": 2, "data_limit": 10, "expire": 1700000000})
    import json
    body = json.loads(route.calls[0].request.content)
    assert body["group_ids"] == [2] and body["expire"] == "2023-11-14T22:13:20Z"
