import asyncio
import base64
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import httpx

from app.drivers.base import DEFAULT_CAPABILITIES, AccessPlan, PanelDriver, RemoteOutcomeUnknown, normalize_inbounds

_USER_KEYS = {
    "data_limit", "expire", "status", "note", "data_limit_reset_strategy", "service_id",
    "ip_limit", "speed_limit_kbps", "flow", "credential_key", "next_plans",
    "on_hold_expire_duration", "on_hold_timeout", "auto_delete_in_days",
}
_BULK_ACTIONS = {
    "extend_expire", "reduce_expire", "increase_traffic", "decrease_traffic", "cleanup_status",
    "activate_users", "disable_users", "change_service", "delete_users",
}


def _items(data: Any, *keys: str) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        for key in (*keys, "items", "data"):
            if isinstance(data.get(key), list):
                return [item for item in data[key] if isinstance(item, dict)]
    return []


class RebeccaDriver(PanelDriver):
    """Rebecca v2 adapter. Service assignment is used instead of inbound mutation."""

    def __init__(self, base_url: str, credentials: dict[str, Any], verify_ssl: bool = True):
        super().__init__(base_url, credentials, verify_ssl)
        self._cached_token = ""
        self.capabilities = {
            **DEFAULT_CAPABILITIES,
            "inbounds.read": True, "groups.read": True, "users.create": True,
            "users.modify": True, "users.delete": True, "users.read": True,
            "users.list": True, "users.status": True, "users.reset_usage": True,
            "users.revoke_sub": True, "users.usage": True, "users.sub_links": True,
            "users.active_next": True, "users.bulk": True, "system.stats": False,
            "admins.manage": True, "admins.usage": True, "admins.users_status": True,
            "admins.service_limits": True,
        }

    def _api_key(self) -> str | None:
        explicit = self.credentials.get("api_key") or self.credentials.get("token")
        if explicit:
            return str(explicit)
        text = str(self.credentials.get("password", ""))
        return text if text.startswith("rk_") else None

    def _is_key(self) -> bool:
        return self._api_key() is not None

    async def _token(self, force: bool = False) -> str:
        key = self._api_key()
        if key:
            return key
        if self._cached_token and not force:
            return self._cached_token
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=8, follow_redirects=False) as client:
            try:
                response = await client.post(self.base_url + "/api/admin/token", data={
                    "username": self.credentials.get("username", ""),
                    "password": self.credentials.get("password", ""),
                })
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                message = ""
                try:
                    message = str(exc.response.json().get("detail", ""))
                except Exception:
                    pass
                if any(term in message.lower() for term in ("2fa", "two.factor", "otp", "totp", "verification code")) or exc.response.status_code == 428:
                    raise RuntimeError("Rebecca requires two-factor authentication; configure an API key or non-2FA service account") from exc
                if exc.response.status_code in (401, 403):
                    raise RuntimeError("Rebecca authentication failed; verify credentials or use an API key") from exc
                raise
            token = response.json().get("access_token")
            if not token:
                raise RuntimeError("Rebecca authentication did not return access_token")
            self._cached_token = str(token)
            return self._cached_token

    async def login(self) -> None:
        await self._token(force=True)

    async def _request(self, method: str, path: str, **kwargs):
        url = self.base_url + path
        for attempt in range(2):
            token = await self._token(force=attempt > 0)
            try:
                async with httpx.AsyncClient(verify=self.verify_ssl, timeout=8, follow_redirects=False) as client:
                    response = await client.request(method, url, headers={"Authorization": f"Bearer {token}"}, **kwargs)
                    if response.status_code == 401 and attempt == 0 and not self._is_key():
                        self._cached_token = ""
                        continue
                    bulk_body = kwargs.get("json") or {}
                    if (path == "/api/users/actions" and not bool(bulk_body.get("dry_run", True))
                            and response.status_code >= 500):
                        raise RemoteOutcomeUnknown("Rebecca bulk action returned a server error; verify remote state before retrying")
                    response.raise_for_status()
                    if not response.content:
                        return {}
                    try:
                        return response.json()
                    except ValueError:
                        return {}
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                bulk_body = kwargs.get("json") or {}
                no_retry = path == "/api/users/actions" and not bool(bulk_body.get("dry_run", True))
                if attempt == 0 and not no_retry:
                    await asyncio.sleep(0.1)
                    continue
                if no_retry:
                    raise RemoteOutcomeUnknown("Rebecca bulk action outcome is unknown; verify remote state before retrying") from exc
                raise RuntimeError(f"Rebecca request failed after retry: {method} {path} ({type(exc).__name__})") from exc
        raise RuntimeError(f"Rebecca request failed: {method} {path}")

    async def _request_any(self, method: str, paths: list[str], **kwargs):
        last: Exception | None = None
        for path in paths:
            try:
                return await self._request(method, path, **kwargs)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in (404, 405, 410, 422):
                    raise
                last = exc
        if last:
            raise last
        raise RuntimeError(f"No API paths configured for {method}")

    @staticmethod
    def _u(name: str) -> str:
        return quote(name, safe="")

    async def test_connection(self) -> dict[str, Any]:
        return {"ok": True, "admin": await self._request("GET", "/api/admin")}

    async def list_inbounds(self) -> list[dict[str, Any]]:
        # Try each route and keep the first one that really yields inbounds (shape differs by version).
        last: Exception | None = None
        for path in ("/api/inbounds/full", "/api/inbounds"):
            try:
                rows = normalize_inbounds(await self._request("GET", path))
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in (404, 405, 410, 422):
                    raise
                last = exc
                continue
            if rows:
                return rows
        if last:
            raise last
        return []

    async def list_hosts(self) -> list[dict[str, Any]]:
        return _items(await self._request("GET", "/api/hosts"), "hosts")

    async def list_groups(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/api/v2/services", params={"limit": 200})
        return [{"id": service.get("id"), "name": service.get("name") or service.get("display_name"),
                 "remark": service.get("display_name") or service.get("name"),
                 **{k: service[k] for k in ("inbounds", "inbound_tags", "inbound_ids") if k in service}}
                for service in _items(data, "services") if service.get("id") is not None]

    @staticmethod
    def _spec(spec: dict[str, Any], create: bool = False) -> dict[str, Any]:
        out = {key: value for key, value in spec.items() if key in _USER_KEYS and value is not None}
        if "data_limit" in spec and spec["data_limit"] is None:
            out["data_limit"] = 0
        plan_spec = spec.get("access_plan") if isinstance(spec.get("access_plan"), dict) else spec
        if "service_id" not in out and plan_spec.get("service_id") is not None:
            out["service_id"] = int(plan_spec["service_id"])
        if "expire" in out and not out["expire"]:
            out["expire"] = 0 if create else None
        if "service_id" in out:
            out["service_id"] = int(out["service_id"])
        return out

    async def create_user(self, spec: dict[str, Any]) -> dict[str, Any]:
        if not spec.get("username"):
            raise ValueError("username is required to create a Rebecca user")
        body = self._spec(spec, True)
        body["username"] = spec["username"]
        if "service_id" not in body:
            raise ValueError("service_id is required for Rebecca users")
        body.setdefault("data_limit", spec.get("data_limit") or 0)
        try:
            return await self._request_any("POST", ["/api/user", "/api/v2/users"], json=body)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 409:
                body.pop("username", None)
                return await self.modify_user(str(spec["username"]), body)
            raise

    async def modify_user(self, remote_username: str, spec: dict[str, Any]) -> dict[str, Any]:
        return await self._request_any("PUT", [f"/api/user/{self._u(remote_username)}", f"/api/v2/users/{self._u(remote_username)}"],
                                       json=self._spec(spec, False))

    async def delete_user(self, remote_username: str) -> None:
        try:
            await self._request_any("DELETE", [f"/api/user/{self._u(remote_username)}", f"/api/v2/users/{self._u(remote_username)}"])
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise

    async def get_user(self, remote_username: str) -> dict[str, Any] | None:
        try:
            data = await self._request_any("GET", [f"/api/user/{self._u(remote_username)}", f"/api/v2/users/{self._u(remote_username)}"])
            return data if isinstance(data, dict) else None
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise

    async def list_users(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        allowed = {"offset", "limit", "username", "status", "service_id", "admin_id", "search"}
        params = {key: value for key, value in (filters or {}).items() if key in allowed and value is not None}
        data = await self._request_any("GET", ["/api/users", "/api/v2/users"], params=params)
        if isinstance(data, list):
            return {"total": len(data), "users": data}
        return data if isinstance(data, dict) else {"total": 0, "users": []}

    async def set_status(self, remote_username: str, enabled: bool) -> None:
        await self.modify_user(remote_username, {"status": "active" if enabled else "disabled"})

    async def reset_usage(self, remote_username: str) -> None:
        await self._request_any("POST", [f"/api/user/{self._u(remote_username)}/reset", f"/api/v2/users/{self._u(remote_username)}/reset"])

    async def revoke_sub(self, remote_username: str) -> None:
        await self._request_any("POST", [f"/api/user/{self._u(remote_username)}/revoke_sub", f"/api/v2/users/{self._u(remote_username)}/revoke_sub"])

    async def active_next(self, remote_username: str) -> dict[str, Any]:
        return await self._request_any("POST", [f"/api/user/{self._u(remote_username)}/active-next", f"/api/v2/users/{self._u(remote_username)}/active-next"])

    async def get_usages(self, remote_usernames: list[str]) -> dict[str, int]:
        if not remote_usernames:
            return {}
        requested = {name.lower(): name for name in remote_usernames}
        result: dict[str, int] = {}
        try:
            data = await self._request_any("GET", ["/api/users", "/api/v2/users"],
                                           params=[("username", name) for name in remote_usernames] + [("limit", len(remote_usernames))])
            for user in _items(data, "users"):
                original = requested.get(str(user.get("username", "")).lower())
                if original is not None and any(key in user for key in ("used_traffic", "traffic", "used")):
                    result[original] = int(user.get("used_traffic", user.get("traffic", user.get("used", 0))) or 0)
        except Exception:
            # Fall through to per-user reads; a single list route/version mismatch is not fatal.
            pass

        role = None
        if any(result.get(name) == 0 for name in remote_usernames):
            try:
                admin_info = await self._request("GET", "/api/admin")
                role = str(admin_info.get("role", "")).lower() if isinstance(admin_info, dict) else None
            except Exception:
                role = None

        for name in remote_usernames:
            if name in result and result[name] > 0:
                continue
            try:
                detail = await self.get_user(name)
                if detail is None:
                    result.pop(name, None)
                    continue
                amount = int(detail.get("used_traffic", detail.get("traffic", 0)) or 0)
                if amount > 0:
                    result[name] = amount
                    continue
                try:
                    usage = await self._request_any("GET", [
                        f"/api/v2/users/{self._u(name)}/usage", f"/api/user/{self._u(name)}/usage"])
                    if isinstance(usage, dict):
                        amount = int(usage.get("used_traffic", usage.get("traffic", usage.get("used", 0))) or 0)
                    else:
                        amount = int(usage or 0)
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code not in (404, 405):
                        raise
                if amount > 0:
                    result[name] = amount
                elif role in {"standard", "reseller"}:
                    result.pop(name, None)
                else:
                    result[name] = 0
                # Rebecca may mask usage as zero for standard/reseller admins. Omit it so
                # usage_sync does not overwrite its remote baseline and later double-count traffic.
            except Exception:
                continue
        return result

    async def get_sub_links(self, remote_username: str) -> list[str]:
        user = await self.get_user(remote_username)
        if not user:
            return []
        links = [link for link in (user.get("links") or []) if isinstance(link, str)]
        if links:
            return links
        subscription = user.get("subscription_url")
        if not subscription:
            return []
        url = urljoin(self.base_url + "/", str(subscription))
        if urlparse(url).netloc != urlparse(self.base_url).netloc:
            return []
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=8, follow_redirects=False) as client:
            response = await client.get(url.rstrip("/") + "/v2ray")
            response.raise_for_status()
            text = response.text.strip()
        if "://" not in text:
            try:
                text = base64.b64decode(text + "=" * (-len(text) % 4)).decode()
            except Exception:
                return []
        return [line.strip() for line in text.splitlines() if "://" in line]

    async def bulk_action(self, action: str, payload: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
        if action not in _BULK_ACTIONS:
            raise ValueError(f"Unsupported Rebecca bulk action: {action}")
        body = {**payload, "action": action, "dry_run": True}
        preview = await self._request("POST", "/api/users/actions", json=body)
        if dry_run:
            return {"dry_run": True, "action": action, "preview": preview}
        body["dry_run"] = False
        result = await self._request("POST", "/api/users/actions", json=body)
        return {"dry_run": False, "action": action, "preview": preview, "result": result}

    async def list_admins(self) -> list[dict[str, Any]]:
        data = await self._request("GET", "/api/admins")
        return _items(data, "admins")

    async def admin_usage(self, admin_username: int | str) -> dict[str, Any]:
        data = await self._request("GET", f"/api/admin/usage/{self._u(str(admin_username))}")
        return data if isinstance(data, dict) else {"usage": data}

    async def create_admin(self, spec: dict[str, Any]) -> dict[str, Any]:
        allowed = {"username", "password", "role", "permissions", "data_limit", "traffic_limit_mode",
                   "show_user_traffic", "use_service_traffic_limits", "delete_user_usage_limit_enabled",
                   "delete_user_usage_limit", "expire", "users_limit", "services", "service_limits", "require_2fa"}
        body = {key: value for key, value in spec.items() if key in allowed and value is not None}
        if not body.get("username") or not body.get("password"):
            raise ValueError("username and password are required to create a Rebecca admin")
        if len(str(body["password"])) < 6:
            raise ValueError("Rebecca admin password must contain at least 6 characters")
        if body.get("role") is not None and body["role"] not in {"standard", "reseller", "sudo", "full_access"}:
            raise ValueError("Unsupported Rebecca admin role")
        data = await self._request("POST", "/api/admin", json=body)
        return data if isinstance(data, dict) else {"result": data}

    async def modify_admin(self, admin_username: str, spec: dict[str, Any]) -> dict[str, Any]:
        allowed = {"password", "role", "permissions", "data_limit", "traffic_limit_mode", "show_user_traffic",
                   "use_service_traffic_limits", "delete_user_usage_limit_enabled", "delete_user_usage_limit",
                   "expire", "users_limit", "services", "service_limits", "require_2fa"}
        body = {key: value for key, value in spec.items() if key in allowed and value is not None}
        if body.get("role") is not None and body["role"] not in {"standard", "reseller", "sudo", "full_access"}:
            raise ValueError("Unsupported Rebecca admin role")
        if body.get("password") is not None and len(str(body["password"])) < 6:
            raise ValueError("Rebecca admin password must contain at least 6 characters")
        data = await self._request("PUT", f"/api/admin/{self._u(admin_username)}", json=body)
        return data if isinstance(data, dict) else {"result": data}

    async def delete_admin(self, admin_username: str) -> None:
        try:
            await self._request("DELETE", f"/api/admin/{self._u(admin_username)}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise

    async def set_admin_status(self, admin_username: str, enabled: bool) -> None:
        action = "enable" if enabled else "disable"
        try:
            await self._request("POST", f"/api/admin/{self._u(admin_username)}/{action}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise

    async def set_admin_users_status(self, admin_username: str, enabled: bool) -> None:
        action = "activate" if enabled else "disable"
        try:
            await self._request("POST", f"/api/admin/{self._u(admin_username)}/users/{action}")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise

    async def set_admin_service_limits(self, service_id: int, admin_id: int, limits: dict[str, Any]) -> dict[str, Any]:
        data = await self._request("PUT", f"/api/v2/services/{int(service_id)}/admins/{int(admin_id)}/limits", json=limits)
        return data if isinstance(data, dict) else {"result": data}
