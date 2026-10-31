import json
from app.core.hardening import BlockSensitive, HostGuard, InputGuard


async def _app(scope, receive, send):
    while (await receive()).get("more_body"):
        pass
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"ok"})


async def _call(app, method="GET", path="/", headers=(), body=b""):
    out, sent = [], [False]

    async def receive():
        if sent[0]:
            return {"type": "http.disconnect"}
        sent[0] = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(m):
        out.append(m)
    await app({"type": "http", "method": method, "path": path, "headers": [(k.encode(), v.encode()) for k, v in headers]}, receive, send)
    return out[0]["status"]


async def test_host_lock_and_sensitive_paths():
    app = HostGuard(BlockSensitive(_app), domain="p.example.com")
    ok = [("host", "p.example.com:8443")]
    assert await _call(app, headers=ok) == 200
    assert await _call(app, headers=[("host", "1.2.3.4:8443")]) == 404
    assert await _call(app, path="/health", headers=[("host", "1.2.3.4")]) == 200
    for path in ("/data/subhub.db", "/.env", "/backup.zip", "/dashboard/assets/x.js.map"):
        assert await _call(app, path=path, headers=ok) == 404
    assert await _call(app, path="/dashboard/assets/x.js", headers=ok) == 200


async def test_input_guard():
    app = InputGuard(_app)
    h = [("content-type", "application/json")]
    assert await _call(app, "POST", "/api/x", h, json.dumps({"a": "b"}).encode()) == 200
    assert await _call(app, "POST", "/api/x", h, json.dumps({"a": "b\x00c"}).encode()) == 422
    assert await _call(app, "POST", "/api/x", h, b"[" * 30 + b"]" * 30) == 422
    assert await _call(app, "POST", "/api/x", [("content-length", str(5 * 1024 * 1024))]) == 413
