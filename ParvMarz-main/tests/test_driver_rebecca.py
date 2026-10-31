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


@respx.mock
async def test_v2_user_routes_bulk_dry_run_and_service_limits():
    respx.post(B + "/api/user").mock(return_value=httpx.Response(404, json={"detail": "legacy missing"}))
    created = respx.post(B + "/api/v2/users").mock(return_value=httpx.Response(201, json={"username": "u2"}))
    respx.put(B + "/api/user/u2").mock(return_value=httpx.Response(404))
    modified = respx.put(B + "/api/v2/users/u2").mock(return_value=httpx.Response(200, json={"username": "u2"}))
    actions = respx.post(B + "/api/users/actions").mock(side_effect=[
        httpx.Response(200, json={"matched": 1}), httpx.Response(200, json={"changed": 1})
    ])
    limits = respx.put(B + "/api/v2/services/3/admins/9/limits").mock(return_value=httpx.Response(200, json={"ok": True}))
    d = _d()
    await d.create_user({"username": "u2", "service_id": 3, "ip_limit": 2, "speed_limit_kbps": 1000,
                         "flow": "xtls-rprx-vision", "credential_key": "opaque", "next_plans": []})
    await d.modify_user("u2", {"ip_limit": 3})
    result = await d.bulk_action("disable_users", {"usernames": ["u2"]}, dry_run=False)
    await d.set_admin_service_limits(3, 9, {"max_users": 5})
    import json
    assert created.called and modified.called and limits.called
    assert [json.loads(call.request.content)["dry_run"] for call in actions.calls] == [True, False]
    assert result["preview"]["matched"] == 1


@respx.mock
async def test_rebecca_inbounds_hosts_and_groups_are_read_only():
    respx.get(B + "/api/inbounds/full").mock(return_value=httpx.Response(200, json={"inbounds": [{"tag": "existing", "protocol": "vless"}]}))
    respx.get(B + "/api/hosts").mock(return_value=httpx.Response(200, json={"hosts": [{"id": 4, "name": "existing host"}]}))
    respx.get(B + "/api/v2/services").mock(return_value=httpx.Response(200, json=[{"id": 3, "name": "Gold"}]))
    d = _d()
    assert (await d.list_inbounds())[0]["tag"] == "existing"
    assert (await d.list_hosts())[0]["id"] == 4
    assert (await d.list_groups())[0]["id"] == 3


@respx.mock
async def test_rebecca_admin_management_usage_and_user_controls():
    create = respx.post(B + "/api/admin").mock(return_value=httpx.Response(201, json={"username": "agent1", "role": "reseller"}))
    listed = respx.get(B + "/api/admins").mock(return_value=httpx.Response(200, json={"admins": [{"username": "agent1"}]}))
    usage = respx.get(B + "/api/admin/usage/agent1").mock(return_value=httpx.Response(200, json=3000))
    modify = respx.put(B + "/api/admin/agent1").mock(return_value=httpx.Response(200, json={"username": "agent1"}))
    admin_disable = respx.post(B + "/api/admin/agent1/disable").mock(return_value=httpx.Response(200, json={"ok": True}))
    user_disable = respx.post(B + "/api/admin/agent1/users/disable").mock(return_value=httpx.Response(200, json={"ok": True}))
    delete = respx.delete(B + "/api/admin/agent1").mock(return_value=httpx.Response(204))
    d = _d()
    await d.create_admin({"username": "agent1", "password": "secret123", "role": "reseller", "permissions": {"users": True}})
    assert (await d.list_admins())[0]["username"] == "agent1"
    assert await d.admin_usage("agent1") == {"usage": 3000}
    await d.modify_admin("agent1", {"role": "standard", "permissions": {"users": False}})
    await d.set_admin_status("agent1", False)
    await d.set_admin_users_status("agent1", False)
    await d.delete_admin("agent1")
    assert all(route.called for route in (create, listed, usage, modify, admin_disable, user_disable, delete))
    assert d.capabilities["admins.manage"] and d.capabilities["admins.usage"]


def test_rebecca_admin_roles_are_validated_locally():
    import pytest
    with pytest.raises(ValueError):
        import asyncio
        asyncio.run(_d().create_admin({"username": "agent1", "password": "secret123", "role": "root"}))
