"""Pure-ASGI guards (no BaseHTTPMiddleware: lower memory, no body-streaming quirks)."""
import json
import re

MAX_BODY = 2 * 1024 * 1024
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_BLOCKED_EXT = (".db", ".sqlite", ".sqlite3", ".sql", ".bak", ".zip", ".gz", ".tar", ".env", ".json", ".py", ".pyc",
                ".log", ".txt", ".md", ".ini", ".toml", ".yml", ".yaml", ".pem", ".key", ".map", ".sh", ".lock")
_BLOCKED_SEG = ("/data", "/.", "/app/", "/cli/", "/backups", "/certs", "/secrets", "/alembic", "/node_modules", "/src/")


async def _plain(send, status: int, body: bytes = b"", ctype: bytes = b"text/plain"):
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", ctype), (b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})


def _hdr(scope, name: bytes) -> str:
    for k, v in scope.get("headers", ()):
        if k == name:
            return v.decode("latin-1")
    return ""


class HostGuard:
    """If a domain is configured the app answers only for that Host (everything else: empty 404)."""
    def __init__(self, app, domain: str = "", allow_paths: tuple[str, ...] = ("/health",)):
        self.app, self.domain, self.allow = app, domain.lower().strip(), allow_paths

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket") and self.domain and scope.get("path") not in self.allow:
            h = _hdr(scope, b"host").lower()
            host = h.rsplit(":", 1)[0] if ":" in h else h
            if host != self.domain:
                if scope["type"] == "http":
                    return await _plain(send, 404)
                return
        await self.app(scope, receive, send)


class BlockSensitive:
    """Defense in depth: never answer for database/backup/config/source-like paths, whatever is mounted."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "").lower()
            if ".." in path or "\\" in path or "%" in path or "\x00" in path:
                return await _plain(send, 404)
            if not path.startswith("/api/") and (path.endswith(_BLOCKED_EXT) or any(s in path for s in _BLOCKED_SEG)):
                if not path.startswith("/dashboard/assets/") or path.endswith((".map", ".json", ".md", ".py", ".txt")):
                    return await _plain(send, 404)
        await self.app(scope, receive, send)


def _bad(obj, depth: int = 0) -> bool:
    stack = [(obj, 0)]
    while stack:
        cur, d = stack.pop()
        if d > 12:
            return True
        if isinstance(cur, str):
            if _CTRL.search(cur):
                return True
        elif isinstance(cur, dict):
            for k, v in cur.items():
                if isinstance(k, str) and _CTRL.search(k):
                    return True
                stack.append((v, d + 1))
        elif isinstance(cur, list):
            stack.extend((v, d + 1) for v in cur)
    return False


class InputGuard:
    """Caps body size and rejects JSON with control/NUL characters or absurd nesting before any route sees it."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in ("POST", "PUT", "PATCH", "DELETE"):
            return await self.app(scope, receive, send)
        cl = _hdr(scope, b"content-length")
        if cl.isdigit() and int(cl) > MAX_BODY:
            return await _plain(send, 413)
        body, more = bytearray(), True
        while more:
            msg = await receive()
            if msg["type"] == "http.disconnect":
                return
            body += msg.get("body", b"")
            more = msg.get("more_body", False)
            if len(body) > MAX_BODY:
                return await _plain(send, 413)
        if body and "json" in _hdr(scope, b"content-type").lower():
            try:
                data = json.loads(body)
            except Exception:
                data = None  # let FastAPI answer with its normal JSON error
            if data is not None and _bad(data):
                out = json.dumps({"detail": {"detail": "ورودی نامعتبر است (کاراکتر غیرمجاز)", "code": "VALIDATION_ERROR"}}, ensure_ascii=False).encode()
                return await _plain(send, 422, out, b"application/json")
        sent = False

        async def replay():
            nonlocal sent
            if not sent:
                sent = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()
        await self.app(scope, replay, send)


class SecureHeaders:
    def __init__(self, app, csp: str = "", hsts: bool = False):
        self.app = app
        base = [(b"x-content-type-options", b"nosniff"), (b"x-frame-options", b"DENY"), (b"referrer-policy", b"no-referrer"),
                (b"cross-origin-opener-policy", b"same-origin"), (b"permissions-policy", b"camera=(), microphone=(), geolocation=()")]
        if hsts:
            base.append((b"strict-transport-security", b"max-age=31536000"))
        self.base, self.csp = base, csp.encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def wrap(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                have = {k.lower() for k, _ in headers}
                headers += [h for h in self.base if h[0] not in have]
                if self.csp and b"content-security-policy" not in have and scope.get("path", "").startswith("/dashboard"):
                    headers.append((b"content-security-policy", self.csp))
                message = {**message, "headers": headers}
            await send(message)
        await self.app(scope, receive, wrap)


DASH_CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self'; font-src 'self' data:; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
