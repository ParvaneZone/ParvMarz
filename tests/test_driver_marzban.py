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
