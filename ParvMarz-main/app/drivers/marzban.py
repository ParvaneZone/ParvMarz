import asyncio
import base64
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from app.drivers.base import DEFAULT_CAPABILITIES, AccessPlan, PanelDriver, normalize_inbounds

_USER_KEYS = {
    "username", "proxies", "inbounds", "data_limit", "expire", "data_limit_reset_strategy",
    "status", "on_hold_expire_duration", "on_hold_timeout", "auto_delete_in_days", "note",
    "next_plan",
}


class MarzbanDriver(PanelDriver):
    """Adapter for Marzban and API-compatible Marzdar/Marzyar deployments."""

    def __init__(self, base_url: str, credentials: dict[str, Any], verify_ssl: bool = True):
        super().__init__(base_url, credentials, verify_ssl)
        self._tok = ""
        self.variant = "marzban"
        self.capabilities = {
            **DEFAULT_CAPABILITIES,
            "inbounds.read": True, "users.create": True, "users.modify": True,
            "users.delete": True, "users.read": True, "users.list": True,
            "users.status": True, "users.reset_usage": True, "users.revoke_sub": True,
            "users.usage": True, "users.sub_links": True, "users.active_next": True,
            "users.bulk": True, "system.stats": True,
            "templates.read": self.variant == "marzdar",
            "admins.manage": False,
            "admins.usage": False,
            "admins.users_status": self.variant in {"marzdar", "marzyar"},
            "admins.remote_owner": self.variant in {"marzdar", "marzyar"},
            "users.expired.list": self.variant in {"marzdar", "marzyar"},
            "users.expired.delete": self.variant in {"marzdar", "marzyar"},
        }

    def set_variant(self, panel_type: str) -> None:
        self.variant = panel_type.lower()
        self.capabilities["templates.read"] = self.variant == "marzdar"
        self.capabilities["admins.manage"] = False
        # Admin-usage path varies and is not specified by the available API contract.
        self.capabilities["admins.usage"] = False
        self.capabilities["admins.users_status"] = self.variant in {"marzdar", "marzyar"}
        self.capabilities["admins.remote_owner"] = self.variant in {"marzdar", "marzyar"}
        self.capabilities["users.expired.list"] = self.variant in {"marzdar", "marzyar"}
        self.capabilities["users.expired.delete"] = self.variant in {"marzdar", "marzyar"}

    async def _token(self, force: bool = False) -> str:
        if self._tok and not force:
            return self._tok
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=8, follow_redirects=False) as client:
            response = await client.post(self.base_url + "/api/admin/token", data={
                "username": self.credentials.get("username", ""),
                "password": self.credentials.get("password", ""),
            })
            response.raise_for_status()
            token = response.json().get("access_token")
            if not token:
                raise RuntimeError("Panel authentication did not return access_token")
            self._tok = str(token)
            return self._tok

    async def _request(self, method: str, path: str, **kwargs):
        url = self.base_url + path
        last_error: Exception | None = None
        for attempt in range(2):
            token = await self._token(force=attempt > 0)
            try:
                async with httpx.AsyncClient(verify=self.verify_ssl, timeout=8, follow_redirects=False) as client:
                    response = await client.request(method, url, headers={"Authorization": f"Bearer {token}"}, **kwargs)
                    if response.status_code == 401 and attempt == 0:
                        self._tok = ""
                        continue
                    response.raise_for_status()
                    return response.json() if response.content else {}
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt == 0:
                    await asyncio.sleep(0.1)
                    continue
                raise RuntimeError(f"Panel request failed after retry: {method} {path} ({type(exc).__name__})") from exc
        if last_error:
            raise RuntimeError(f"Panel request failed: {method} {path} ({type(last_error).__name__})") from last_error
        raise RuntimeError(f"Panel request failed: {method} {path}")

    async def test_connection(self) -> dict[str, Any]:
        data = await self._request("GET", "/api/system")
        return {"ok": True, "system": data}

    async def system_stats(self) -> dict[str, Any] | None:
        return await self._request("GET", "/api/system")

    async def list_inbounds(self) -> list[dict[str, Any]]:
        return normalize_inbounds(await self._request("GET", "/api/inbounds"))

    async def list_hosts(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/api/hosts")

    async def list_groups(self) -> list[dict[str, Any]]:
        # Marzban access is selected with protocol -> inbound-tag mappings, not groups.
        return []

    @staticmethod
    def _user_spec(spec: dict[str, Any]) -> dict[str, Any]:
        clean = {key: value for key, value in spec.items() if key in _USER_KEYS and value is not None}
        if "data_limit" in spec and spec["data_limit"] is None:
            clean["data_limit"] = 0
        if "access_plan" in spec:
            clean.update(AccessPlan.from_spec(spec["access_plan"]).for_panel("marzban"))
        return clean

    async def create_user(self, spec: dict[str, Any]) -> dict[str, Any]:
        body = self._user_spec(spec)
        if not body.get("username"):
            raise ValueError("username is required to create a Marzban user")
        try:
            return await self._request("POST", "/api/user", json=body)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 409:
                existing = await self.get_user(str(body["username"]))
                if existing is None:
                    raise
                return await self.modify_user(str(body["username"]), {k: v for k, v in body.items() if k != "username"})
            raise

    async def modify_user(self, remote_username: str, spec: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PUT", f"/api/user/{quote(remote_username, safe='')}", json=self._user_spec(spec))

    async def delete_user(self, remote_username: str) -> None:
        try:
            await self._request("DELETE", f"/api/user/{quote(remote_username, safe='')}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise

    async def get_user(self, remote_username: str) -> dict[str, Any] | None:
        try:
            return await self._request("GET", f"/api/user/{quote(remote_username, safe='')}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise

    async def list_users(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        allowed = {"offset", "limit", "username", "status", "sort", "admin"}
        params = {k: v for k, v in (filters or {}).items() if k in allowed and v is not None}
        data = await self._request("GET", "/api/users", params=params)
        if isinstance(data, list):
            return {"total": len(data), "users": data}
        return data if isinstance(data, dict) else {"total": 0, "users": []}

    async def set_status(self, remote_username: str, enabled: bool) -> None:
        await self.modify_user(remote_username, {"status": "active" if enabled else "disabled"})

    async def reset_usage(self, remote_username: str) -> None:
        await self._request("POST", f"/api/user/{quote(remote_username, safe='')}/reset")

    async def revoke_sub(self, remote_username: str) -> None:
        await self._request("POST", f"/api/user/{quote(remote_username, safe='')}/revoke_sub")

    async def active_next(self, remote_username: str) -> dict[str, Any]:
        return await self._request("POST", f"/api/user/{quote(remote_username, safe='')}/active-next")

    async def list_expired_users(self) -> dict[str, Any]:
        if self.variant not in {"marzdar", "marzyar"}:
            raise NotImplementedError("Expired-user endpoints are only enabled for Marzdar/Marzyar adapters")
        data = await self._request("GET", "/api/users/expired")
        return data if isinstance(data, dict) else {"users": data or []}

    async def delete_expired_users(self, dry_run: bool = True) -> dict[str, Any]:
        if self.variant not in {"marzdar", "marzyar"}:
            raise NotImplementedError("Expired-user deletion is only enabled for Marzdar/Marzyar adapters")
        if dry_run:
            return await self._request("GET", "/api/users/expired")
        return await self._request("DELETE", "/api/users/expired")

    async def get_usages(self, remote_usernames: list[str]) -> dict[str, int]:
        async def fetch(name: str) -> tuple[str, int | None]:
            encoded = quote(name, safe="")
            try:
                try:
                    data = await self._request("GET", f"/api/user/{encoded}/usage")
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code != 404:
                        raise
                    # Older API-compatible deployments expose usage only in the user detail.
                    data = await self.get_user(name)
                if not isinstance(data, dict):
                    return name, None
                value = data.get("used_traffic", data.get("usage"))
                return name, int(value or 0) if value is not None else None
            except Exception:
                return name, None
        pairs = await asyncio.gather(*(fetch(name) for name in remote_usernames))
        return {name: usage for name, usage in pairs if usage is not None}

    async def get_sub_links(self, remote_username: str) -> list[str]:
        user = await self.get_user(remote_username)
        if not user:
            return []
        links = user.get("links", [])
        if isinstance(links, list) and any(isinstance(x, str) for x in links):
            return [link for link in links if isinstance(link, str)]
        # Some Marzban forks leave `links` empty; the panel's own subscription URL still has them.
        subscription = str(user.get("subscription_url") or "")
        url = self.base_url + subscription if subscription.startswith("/") else subscription
        bp, tp = urlparse(self.base_url), urlparse(url)
        if not url or tp.scheme not in {"http", "https"} or tp.netloc != bp.netloc:
            return []
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=8, follow_redirects=False) as client:
            response = await client.get(url, headers={"User-Agent": "v2rayN"})
            response.raise_for_status()
            text = response.text.strip()
        if "://" not in text:
            try:
                text = base64.b64decode(text + "=" * (-len(text) % 4)).decode()
            except Exception:
                return []
        return [line.strip() for line in text.splitlines() if "://" in line]

    async def bulk_action(self, action: str, payload: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
        names = payload.get("usernames") or payload.get("users") or []
        if not isinstance(names, list) or not names:
            raise ValueError("bulk action requires a non-empty usernames/users list")
        supported = {"activate_users", "disable_users", "delete_users", "reset_usage", "revoke_sub", "modify_users"}
        if action not in supported:
            raise ValueError(f"Unsupported Marzban bulk action: {action}")
        if dry_run:
            return {"dry_run": True, "action": action, "count": len(names), "usernames": names}
        results: list[dict[str, Any]] = []
        for name in names:
            try:
                if action == "activate_users": await self.set_status(str(name), True)
                elif action == "disable_users": await self.set_status(str(name), False)
                elif action == "delete_users": await self.delete_user(str(name))
                elif action == "reset_usage": await self.reset_usage(str(name))
                elif action == "revoke_sub": await self.revoke_sub(str(name))
                else: await self.modify_user(str(name), payload.get("spec", {}))
                results.append({"username": name, "ok": True})
            except Exception as exc:
                results.append({"username": name, "ok": False, "error": type(exc).__name__})
        return {"dry_run": False, "action": action, "count": len(results), "results": results}

    async def get_user_template(self) -> dict[str, Any] | list[dict[str, Any]]:
        if not self.capabilities.get("templates.read"):
            raise NotImplementedError("User templates are not confirmed for this Marzban variant")
        data = await self._request("GET", "/api/user_template")
        return data

    async def set_owner(self, remote_username: str, admin_username: str) -> dict[str, Any]:
        if self.variant not in {"marzdar", "marzyar"}:
            raise NotImplementedError("Remote owner assignment is only enabled for Marzdar/Marzyar")
        return await self._request("PUT", f"/api/user/{quote(remote_username, safe='')}/set-owner",
                                   params={"admin_username": admin_username})

    async def admin_usage(self, admin_username: str) -> dict[str, Any]:
        raise NotImplementedError("Remote admin usage endpoint is not verified; confirm the deployed Marzdar/Marzyar OpenAPI schema first")

    async def set_admin_users_status(self, admin_username: str, enabled: bool) -> dict[str, Any]:
        if self.variant not in {"marzdar", "marzyar"}:
            raise NotImplementedError("Remote admin user status actions are only enabled for Marzdar/Marzyar")
        action = "activate" if enabled else "disable"
        return await self._request("POST", f"/api/admin/{quote(admin_username, safe='')}/users/{action}")
