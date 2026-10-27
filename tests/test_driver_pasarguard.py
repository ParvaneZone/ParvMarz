import httpx
import respx

from app.drivers.pasarguard import PasarGuardDriver

B = "https://pg.example.com"


@respx.mock
async def test_api_key_header_and_groups():
    route = respx.get(B + "/api/groups/simple").mock(
        return_value=httpx.Response(200, json={"groups": [{"id": 2, "name": "G"}, {"id": 3, "name": "off", "is_disabled": True}]}))
    d = PasarGuardDriver(B, {"username": "", "password": "pg_key_abc"})
    assert await d.list_groups() == [{"id": 2, "name": "G"}, {"id": 3, "name": "off", "is_disabled": True}]
    assert route.calls[0].request.headers["x-api-key"] == "pg_key_abc"


@respx.mock
async def test_create_uses_group_ids_and_iso_expire():
    route = respx.post(B + "/api/user").mock(return_value=httpx.Response(201, json={}))
    d = PasarGuardDriver(B, {"username": "", "password": "pg_key_abc"})
    await d.create_user({"username": "u", "service_id": 2, "data_limit": 10, "expire": 1700000000})
    import json
    body = json.loads(route.calls[0].request.content)
    assert body["group_ids"] == [2] and body["expire"] == "2023-11-14T22:13:20Z"


@respx.mock
async def test_inbounds_user_update_delete_and_group_bulk():
    respx.get(B + "/api/inbounds").mock(return_value=httpx.Response(200, json={"inbounds": [{"tag": "vless-a", "protocol": "vless"}]}))
    respx.post(B + "/api/user").mock(return_value=httpx.Response(201, json={"username": "u"}))
    respx.put(B + "/api/user/u").mock(return_value=httpx.Response(200, json={"username": "u"}))
    respx.delete(B + "/api/user/u").mock(return_value=httpx.Response(204))
    add = respx.post(B + "/api/groups/bulk/add").mock(return_value=httpx.Response(200, json={"updated": 1}))
    d = PasarGuardDriver(B, {"username": "", "password": "pg_key_abc"})
    assert (await d.list_inbounds())[0]["tag"] == "vless-a"
    await d.create_user({"username": "u", "group_ids": [2], "data_limit": None})
    await d.modify_user("u", {"status": "disabled", "group_ids": [2]})
    await d.delete_user("u")
    await d.bulk_action("add_groups", {"group_ids": [2], "users": [10], "has_group_ids": [1]})
    import json
    assert json.loads(add.calls[0].request.content) == {"group_ids": [2], "users": [10], "has_group_ids": [1]}


@respx.mock
async def test_list_users_and_bulk_preview():
    respx.get(B + "/api/users").mock(return_value=httpx.Response(200, json={"users": [{"username": "u"}], "total": 1}))
    d = PasarGuardDriver(B, {"username": "", "password": "pg_key_abc"})
    assert (await d.list_users({"status": "active"}))["total"] == 1
    preview = await d.bulk_action("add_groups", {"group_ids": [4]}, dry_run=True)
    assert preview["dry_run"] is True



def test_pasarguard_unlimited_expire_is_zero():
    from app.drivers.pasarguard import _iso
    assert _iso(0) == 0
    assert _iso(None) is None


@respx.mock
async def test_template_bulk_route_and_dry_run_does_not_mutate():
    route = respx.post(B + "/api/users/bulk/from_template").mock(
        return_value=httpx.Response(200, json={"created": 2, "subscription_urls": []}))
    d = PasarGuardDriver(B, {"api_key": "pg_key_abc"})
    result = await d.create_users_from_template({
        "user_template_id": 1, "count": 2, "strategy": "sequence", "username": "u"
    })
    assert result["created"] == 2
    assert route.called
    preview = await d.bulk_action("add_groups", {"group_ids": [1], "users": [10]}, dry_run=True)
    assert preview["dry_run"] is True
