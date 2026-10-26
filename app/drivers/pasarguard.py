import base64
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from app.drivers.base import PanelDriver

_STATUS_KEYS = {"data_limit", "note", "status", "data_limit_reset_strategy"}


def _iso(ts) -> str | None:
    try:
        ts = int(ts or 0)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if ts > 0 else None


class PasarGuardDriver(PanelDriver):
    """PasarGuard driver. Password starting with ``pg_key_`` = API key (X-Api-Key); otherwise login."""

    _tok: str = ""

    def _is_key(self) -> bool:
        return str(self.credentials.get("password", "")).startswith("pg_key_")

    async def _login(self) -> str:
        cred = {"username": self.credentials.get("username", ""),
                "password": self.credentials.get("password", "")}
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=8, follow_redirects=False) as c:
            r = None
            for body in ({**cred, "grant_type": "password"}, cred):
                r = await c.post(self.base_url + "/api/admin/token", data=body)
                if r.status_code not in (415, 422):
                    break
            r.raise_for_status()
            return r.json()["access_token"]

    def _headers(self) -> dict:
        if self._is_key():
            return {"X-Api-Key": self.credentials["password"]}
        return {"Authorization": f"Bearer {self._tok}"}

    async def _request(self, method: str, path: str, **kw):
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=8, follow_redirects=False) as c:
            if not self._is_key() and not self._tok:
                self._tok = await self._login()
            r = await c.request(method, self.base_url + path, headers=self._headers(), **kw)
            if r.status_code == 401 and not self._is_key():
                self._tok = await self._login()
                r = await c.request(method, self.base_url + path, headers=self._headers(), **kw)
            r.raise_for_status()
            if not r.content:
                return {}
            try:
                return r.json()
            except ValueError:
                return {}

    @staticmethod
    def _u(name: str) -> str:
        return quote(name, safe="")

    async def _user_call(self, method: str, name: str, sub: str = "", **kw):
        """v5 compatibility: fall back to /api/user/by-id/{id} when username paths are refused."""
        try:
            return await self._request(method, f"/api/user/{self._u(name)}{sub}", **kw)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in (404, 405, 410, 422):
                raise
            uid = None
            for pre in ("/api/user/by-username/", "/api/user/"):
                try:
                    d = await self._request("GET", pre + self._u(name))
                    uid = d.get("id")
                    if uid is not None:
                        break
                except httpx.HTTPStatusError:
                    continue
            if uid is None:
                raise
            return await self._request(method, f"/api/user/by-id/{uid}{sub}", **kw)

    async def test_connection(self) -> dict:
        return {"ok": True, "admin": await self._request("GET", "/api/admin")}

    async def list_groups(self) -> list[dict]:
        data = None
        for path in ("/api/groups/simple", "/api/groups"):
            try:
                data = await self._request("GET", path)
                break
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in (401, 403, 404, 405):
                    raise
        items = data.get("groups", []) if isinstance(data, dict) else (data or [])
        return [{"id": g["id"], "name": g.get("name") or f"group {g['id']}"}
                for g in items if isinstance(g, dict) and "id" in g and not g.get("is_disabled")]

    def _body(self, spec: dict) -> dict:
        out = {k: v for k, v in spec.items() if k in _STATUS_KEYS and v is not None}
        if "expire" in spec:
            out["expire"] = _iso(spec["expire"])
        if spec.get("service_id"):
            out["group_ids"] = [int(spec["service_id"])]
        return out

    async def create_user(self, spec: dict) -> dict:
        body = {"status": "active", "data_limit": 0, "data_limit_reset_strategy": "no_reset",
                **self._body(spec), "username": spec["username"]}
        body["status"] = spec.get("status") or "active"
        try:
            return await self._request("POST", "/api/user", json=body)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 409:
                body.pop("username")
                return await self.modify_user(spec["username"], body)
            raise

    async def modify_user(self, remote_username: str, spec: dict) -> dict:
        return await self._user_call("PUT", remote_username, json=self._body(spec))

    async def delete_user(self, remote_username: str) -> None:
        try:
            await self._user_call("DELETE", remote_username)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise

    async def get_user(self, remote_username: str) -> dict | None:
        try:
            return await self._user_call("GET", remote_username)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise

    async def set_status(self, remote_username: str, enabled: bool) -> None:
        await self.modify_user(remote_username, {"status": "active" if enabled else "disabled"})

    async def reset_usage(self, remote_username: str) -> None:
        await self._user_call("POST", remote_username, "/reset")

    async def revoke_sub(self, remote_username: str) -> None:
        await self._user_call("POST", remote_username, "/revoke_sub")

    async def get_usages(self, remote_usernames: list[str]) -> dict[str, int]:
        wanted = {n.lower(): n for n in remote_usernames}
        result: dict[str, int] = {}
        for name in remote_usernames:
            if name in result:
                continue
            data = await self._request("GET", "/api/users",
                                       params={"search": name, "limit": 50, "offset": 0})
            users = data.get("users", []) if isinstance(data, dict) else (data or [])
            for u in users:
                orig = wanted.get(str(u.get("username", "")).lower())
                if orig:
                    result[orig] = int(u.get("used_traffic", 0) or 0)
        return result

    async def get_sub_links(self, remote_username: str) -> list[str]:
        user = await self.get_user(remote_username)
        if not user:
            return []
        links = [x for x in (user.get("links") or []) if isinstance(x, str)]
        if links:
            return links
        sub = str(user.get("subscription_url") or "")
        url = self.base_url + sub if sub.startswith("/") else sub
        if not url.startswith(self.base_url):
            return []
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=8, follow_redirects=False) as c:
            r = await c.get(url, headers={"User-Agent": "v2rayN"})
            r.raise_for_status()
            text = r.text.strip()
        if "://" not in text:
            try:
                text = base64.b64decode(text + "=" * (-len(text) % 4)).decode()
            except Exception:
                return []
        return [ln.strip() for ln in text.splitlines() if "://" in ln]
