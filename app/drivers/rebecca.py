import asyncio
import base64
from urllib.parse import quote

import httpx

from app.drivers.base import PanelDriver

_USER_KEYS = {"data_limit", "expire", "status", "note", "data_limit_reset_strategy", "service_id"}


def _items(data, *keys) -> list:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in (*keys, "items", "data"):
            if isinstance(data.get(k), list):
                return data[k]
    return []


class RebeccaDriver(PanelDriver):
    """Rebecca driver for reseller/standard admin accounts (not sudo).

    Credentials: password starting with ``rk_`` is a personal API key (preferred, username ignored).
    Otherwise the legacy JWT endpoint POST /api/admin/token is used.
    Users are bound to a Rebecca *service* (service_id); inbounds are not visible to such admins,
    so services are exposed as groups.
    """

    def _is_key(self) -> bool:
        return str(self.credentials.get("password", "")).startswith("rk_")

    async def _token(self) -> str:
        if self._is_key():
            return self.credentials["password"]
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=8, follow_redirects=False) as c:
            r = await c.post(self.base_url + "/api/admin/token", data={
                "username": self.credentials.get("username", ""),
                "password": self.credentials.get("password", "")})
            r.raise_for_status()
            return r.json()["access_token"]

    async def _request(self, method: str, path: str, **kw):
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=8, follow_redirects=False) as c:
            for attempt in (0, 1):
                token = await self._token()
                r = await c.request(method, self.base_url + path,
                                    headers={"Authorization": f"Bearer {token}"}, **kw)
                if r.status_code == 401 and attempt == 0 and not self._is_key():
                    continue
                break
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

    async def test_connection(self) -> dict:
        return {"ok": True, "admin": await self._request("GET", "/api/admin")}

    async def list_groups(self) -> list[dict]:
        data = await self._request("GET", "/api/v2/services", params={"limit": 200})
        return [{"id": s.get("id"), "name": s.get("name") or s.get("display_name"),
                 "remark": s.get("display_name") or s.get("name")}
                for s in _items(data, "services") if s.get("id") is not None]

    @staticmethod
    def _spec(spec: dict, create: bool) -> dict:
        out = {k: v for k, v in spec.items() if k in _USER_KEYS and v is not None}
        if "expire" in out and not out["expire"]:
            out["expire"] = None if not create else 0
        if "data_limit" in out and out["data_limit"] == 0:
            out["data_limit"] = 0
        if "service_id" in out:
            out["service_id"] = int(out["service_id"])
        return out

    async def create_user(self, spec: dict) -> dict:
        body = self._spec(spec, True)
        body["username"] = spec["username"]
        if "service_id" not in body:
            raise ValueError("service_id is required for Rebecca users")
        body.setdefault("data_limit", spec.get("data_limit") or 0)
        try:
            return await self._request("POST", "/api/user", json=body)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 409:  # idempotent: already exists
                body.pop("username")
                return await self.modify_user(spec["username"], body)
            raise

    async def modify_user(self, remote_username: str, spec: dict) -> dict:
        return await self._request("PUT", f"/api/user/{self._u(remote_username)}",
                                   json=self._spec(spec, False))

    async def delete_user(self, remote_username: str) -> None:
        try:
            await self._request("DELETE", f"/api/user/{self._u(remote_username)}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise

    async def get_user(self, remote_username: str) -> dict | None:
        try:
            return await self._request("GET", f"/api/user/{self._u(remote_username)}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise

    async def set_status(self, remote_username: str, enabled: bool) -> None:
        await self.modify_user(remote_username, {"status": "active" if enabled else "disabled"})

    async def reset_usage(self, remote_username: str) -> None:
        await self._request("POST", f"/api/user/{self._u(remote_username)}/reset")

    async def revoke_sub(self, remote_username: str) -> None:
        await self._request("POST", f"/api/user/{self._u(remote_username)}/revoke_sub")

    async def get_usages(self, remote_usernames: list[str]) -> dict[str, int]:
        result: dict[str, int] = {}
        for i in range(0, len(remote_usernames), 100):
            chunk = remote_usernames[i:i + 100]
            data = await self._request("GET", "/api/users",
                                       params=[("username", n) for n in chunk] + [("limit", len(chunk))])
            for u in _items(data, "users"):
                name = u.get("username")
                if name is not None:
                    result[name] = int(u.get("used_traffic", 0) or 0)
            # case-insensitive match back to requested names
        lower = {k.lower(): v for k, v in result.items()}
        return {n: lower[n.lower()] for n in remote_usernames if n.lower() in lower}

    async def get_sub_links(self, remote_username: str) -> list[str]:
        user = await self.get_user(remote_username)
        if not user:
            return []
        links = [x for x in (user.get("links") or []) if isinstance(x, str)]
        if links:
            return links
        sub = user.get("subscription_url")
        if not sub:
            return []
        url = sub if sub.startswith("http") else self.base_url + sub
        if not url.startswith(self.base_url):
            return []  # never follow foreign hosts
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=8, follow_redirects=False) as c:
            r = await c.get(url.rstrip("/") + "/v2ray")
            r.raise_for_status()
            text = r.text.strip()
        if "://" not in text:
            try:
                text = base64.b64decode(text + "=" * (-len(text) % 4)).decode()
            except Exception:
                return []
        return [ln.strip() for ln in text.splitlines() if "://" in ln]
