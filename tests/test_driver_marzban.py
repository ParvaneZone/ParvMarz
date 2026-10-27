import respx
import pytest
import httpx
from app.drivers.marzban import MarzbanDriver

class FakeClient:
    def __init__(self, *args, **kwargs): self.calls=[]
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return False
    async def post(self, url, data=None, **kwargs):
        self.calls.append(('POST',url))
        return httpx.Response(200,json={'access_token':'test-token'},request=httpx.Request('POST',url))
    async def request(self, method, url, **kwargs):
        self.calls.append((method,url))
        return httpx.Response(200,json={'version':'test'},request=httpx.Request(method,url))

@pytest.mark.asyncio
async def test_connection_logs_in_and_reads_system(monkeypatch):
    monkeypatch.setattr(httpx, 'AsyncClient', FakeClient)
    driver=MarzbanDriver('https://panel.example',{'username':'admin','password':'secret'})
    result=await driver.test_connection()
    assert result['ok'] is True
    assert result['system']['version']=='test'


@respx.mock
async def test_inbounds_flattened_with_protocol():
    respx.post("https://m.example.com/api/admin/token").mock(
        return_value=httpx.Response(200, json={"access_token": "t"}))
    respx.get("https://m.example.com/api/inbounds").mock(return_value=httpx.Response(
        200, json={"vless": [{"tag": "A", "network": "tcp"}], "trojan": [{"tag": "B"}]}))
    items = await MarzbanDriver("https://m.example.com", {"username": "a", "password": "b"}).list_inbounds()
    assert {(i["protocol"], i["tag"]) for i in items} == {("vless", "A"), ("trojan", "B")}


@respx.mock
async def test_user_lifecycle_usage_and_active_next():
    base = "https://m.example.com"
    respx.post(base + "/api/admin/token").mock(return_value=httpx.Response(200, json={"access_token": "t"}))
    create = respx.post(base + "/api/user").mock(return_value=httpx.Response(200, json={"username": "u1"}))
    modify = respx.put(base + "/api/user/u1").mock(return_value=httpx.Response(200, json={"username": "u1"}))
    delete = respx.delete(base + "/api/user/u1").mock(return_value=httpx.Response(204))
    respx.get(base + "/api/user/u1").mock(return_value=httpx.Response(200, json={"username": "u1", "links": ["vless://a"]}))
    respx.get(base + "/api/user/u1/usage").mock(return_value=httpx.Response(200, json={"used_traffic": 17}))
    next_route = respx.post(base + "/api/user/u1/active-next").mock(return_value=httpx.Response(200, json={"ok": True}))
    driver = MarzbanDriver(base, {"username": "a", "password": "b"})
    await driver.create_user({"username": "u1", "inbounds": {"vless": ["preexisting-tag"]}, "data_limit": 0})
    await driver.modify_user("u1", {"status": "disabled", "data_limit": 0})
    assert (await driver.get_usages(["u1"])) == {"u1": 17}
    assert await driver.get_sub_links("u1") == ["vless://a"]
    await driver.active_next("u1")
    await driver.delete_user("u1")
    assert create.called and modify.called and delete.called and next_route.called


@respx.mock
async def test_user_list_filters_and_bulk_dry_run_do_not_write():
    base = "https://m.example.com"
    respx.post(base + "/api/admin/token").mock(return_value=httpx.Response(200, json={"access_token": "t"}))
    route = respx.get(base + "/api/users").mock(return_value=httpx.Response(200, json={"total": 1, "users": [{"username": "u"}]}))
    driver = MarzbanDriver(base, {"username": "a", "password": "b"})
    result = await driver.list_users({"status": "active", "limit": 20, "untrusted": "ignored"})
    assert result["total"] == 1
    assert route.calls[0].request.url.params["status"] == "active"
    preview = await driver.bulk_action("disable_users", {"usernames": ["u"]}, dry_run=True)
    assert preview["dry_run"] is True and preview["count"] == 1
