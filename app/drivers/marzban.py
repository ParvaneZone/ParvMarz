import asyncio
from urllib.parse import quote
import httpx
from app.drivers.base import PanelDriver


class MarzbanDriver(PanelDriver):
    """Marzban-compatible API adapter. Auth endpoint and routes follow public Marzban API."""

    async def _token(self) -> str:
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=8, follow_redirects=False) as client:
            response = await client.post(self.base_url + "/api/admin/token", data={
                "username": self.credentials.get("username", ""),
                "password": self.credentials.get("password", ""),
            })
            response.raise_for_status()
            return response.json()["access_token"]

    async def _request(self, method: str, path: str, **kwargs):
        token = await self._token()
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=8, follow_redirects=False) as client:
            response = await client.request(method, self.base_url + path,
                headers={"Authorization": f"Bearer {token}"}, **kwargs)
            if response.status_code == 401:
                token = await self._token()
                response = await client.request(method, self.base_url + path,
                    headers={"Authorization": f"Bearer {token}"}, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else {}

    async def test_connection(self) -> dict:
        data = await self._request("GET", "/api/system")
        return {"ok": True, "system": data}

    async def list_inbounds(self) -> list[dict]:
        """Marzban/Marzdar/Marzyar return {protocol: [inbound, ...]}; flatten with the protocol set."""
        data = await self._request("GET", "/api/inbounds")
        out: list[dict] = []
        if isinstance(data, dict):
            for proto, items in data.items():
                if isinstance(items, list):
                    out += [{**i, "protocol": i.get("protocol") or proto} for i in items if isinstance(i, dict)]
        elif isinstance(data, list):
            out = [i for i in data if isinstance(i, dict)]
        return out

    async def create_user(self, spec: dict) -> dict:
        return await self._request("POST", "/api/user", json=spec)

    async def modify_user(self, remote_username: str, spec: dict) -> dict:
        return await self._request("PUT", f"/api/user/{quote(remote_username, safe='')}", json=spec)

    async def delete_user(self, remote_username: str) -> None:
        await self._request("DELETE", f"/api/user/{quote(remote_username, safe='')}")

    async def get_user(self, remote_username: str) -> dict | None:
        try:
            return await self._request("GET", f"/api/user/{quote(remote_username, safe='')}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise

    async def set_status(self, remote_username: str, enabled: bool) -> None:
        await self._request("PUT", f"/api/user/{quote(remote_username, safe='')}", json={"status": "active" if enabled else "disabled"})

    async def reset_usage(self, remote_username: str) -> None:
        await self._request("POST", f"/api/user/{quote(remote_username, safe='')}/reset")

    async def revoke_sub(self, remote_username: str) -> None:
        await self._request("POST", f"/api/user/{quote(remote_username, safe='')}/revoke_sub")

    async def get_usages(self, remote_usernames: list[str]) -> dict[str, int]:
        async def fetch(name: str):
            try:
                user = await self.get_user(name)
                return name, int(user.get("used_traffic", 0) or 0) if user else None
            except Exception:
                return name, None
        pairs = await asyncio.gather(*(fetch(name) for name in remote_usernames))
        return {name: usage for name, usage in pairs if usage is not None}

    async def get_sub_links(self, remote_username: str) -> list[str]:
        user = await self.get_user(remote_username)
        if not user:
            return []
        links = user.get("links", [])
        return [link for link in links if isinstance(link, str)]
