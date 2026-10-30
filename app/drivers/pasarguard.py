import asyncio
import base64
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from app.drivers.base import DEFAULT_CAPABILITIES, AccessPlan, PanelDriver, normalize_inbounds

_USER_KEYS = {
    "data_limit", "expire", "note", "status", "data_limit_reset_strategy", "on_hold_timeout",
    "on_hold_expire_duration", "auto_delete_in_days", "proxies", "flow", "ip_limit",
    "speed_limit_kbps", "credential_key",
}


def _iso(ts: Any) -> str | int | None:
    if ts is None or ts == "":
        return None
    try:
        value = int(ts)
        if value == 0:
            # PasarGuard-compatible user APIs use 0 to represent unlimited expiration.
            return 0
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
            return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (TypeError, ValueError):
            return None
    return datetime.fromtimestamp(value, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if value > 0 else None


class PasarGuardDriver(PanelDriver):
    """PasarGuard API adapter. Uses X-Api-Key/Authorization: apikey or admin JWT."""

    def __init__(self, base_url: str, credentials: dict[str, Any], verify_ssl: bool = True):
        super().__init__(base_url, credentials, verify_ssl)
        self._tok = ""
        self.capabilities = {
            **DEFAULT_CAPABILITIES,
            "inbounds.read": True, "groups.read": True, "templates.read": True,
            "templates.create_from": True, "users.create": True,
            "users.modify": True, "users.delete": True, "users.read": True,
            "users.list": True, "users.status": True, "users.reset_usage": True,
            "users.revoke_sub": True, "users.usage": True, "users.sub_links": True,
            "users.bulk": True, "templates.read": False, "templates.create_from": True,
            # System/admin stats routes vary by release and remain disabled until schema is confirmed.
        }

    def _api_key(self) -> str | None:
        explicit = self.credentials.get("api_key")
        if explicit:
            return str(explicit)
        text = str(self.credentials.get("password", ""))
        return text if text.startswith("pg_key_") else None

    def _is_key(self) -> bool:
        return self._api_key() is not None

    async def login(self) -> None:
        self._tok = await self._login()

    async def _login(self) -> str:
        credentials = {"username": self.credentials.get("username", ""),
                       "password": self.credentials.get("password", "")}
        last_response = None
        async with httpx.AsyncClient(verify=self.verify_ssl, timeout=8, follow_redirects=False) as client:
            for body in ({**credentials, "grant_type": "password"}, credentials):
                response = await client.post(self.base_url + "/api/admin/token", data=body)
                last_response = response
                if response.status_code not in (415, 422):
                    break
            if last_response is None:
                raise RuntimeError("PasarGuard login failed: no response")
            last_response.raise_for_status()
            token = last_response.json().get("access_token")
            if not token:
                raise RuntimeError("PasarGuard login did not return access_token")
            return str(token)

    def _headers(self) -> dict[str, str]:
        key = self._api_key()
        if key:
            if str(self.credentials.get("api_key_auth", "")).lower() == "authorization":
                return {"Authorization": f"apikey {key}"}
            return {"X-Api-Key": key}
        return {"Authorization": f"Bearer {self._tok}"}

    async def _request(self, method: str, path: str, **kwargs):
        url = self.base_url + path
        for attempt in range(2):
            if not self._is_key() and not self._tok:
                self._tok = await self._login()
            try:
                async with httpx.AsyncClient(verify=self.verify_ssl, timeout=8, follow_redirects=False) as client:
                    response = await client.request(method, url, headers=self._headers(), **kwargs)
                    if response.status_code == 401 and attempt == 0:
                        if not self._is_key():
                            self._tok = await self._login()
                            continue
                        if self.credentials.get("api_key_auth") != "authorization":
                            self.credentials["api_key_auth"] = "authorization"
                            continue
                    response.raise_for_status()
                    if not response.content:
                        return {}
                    try:
                        return response.json()
                    except ValueError:
                        return {}
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt == 0:
                    await asyncio.sleep(0.1)
                    continue
                raise RuntimeError(f"PasarGuard request failed after retry: {method} {path} ({type(exc).__name__})") from exc
        raise RuntimeError(f"PasarGuard request failed: {method} {path}")

    @staticmethod
    def _u(name: str) -> str:
        return quote(name, safe="")

    async def _user_call(self, method: str, name: str, sub: str = "", **kwargs):
        path = f"/api/user/{self._u(name)}{sub}"
        try:
            return await self._request(method, path, **kwargs)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in (404, 405, 410, 422):
                raise
            user_id = None
            for prefix in ("/api/user/by-username/", "/api/user/"):
                try:
                    found = await self._request("GET", prefix + self._u(name))
                    user_id = found.get("id") if isinstance(found, dict) else None
                    if user_id is not None:
                        break
                except httpx.HTTPStatusError:
                    continue
            if user_id is None:
                raise
            return await self._request(method, f"/api/user/by-id/{user_id}{sub}", **kwargs)

    async def test_connection(self) -> dict[str, Any]:
        return {"ok": True, "admin": await self._request("GET", "/api/admin")}

    async def list_inbounds(self) -> list[dict[str, Any]]:
        # PasarGuard answers with a plain list of inbound tags (strings); older builds return objects.
        rows = normalize_inbounds(await self._request("GET", "/api/inbounds"))
        if rows and any(not r.get("security") for r in rows):
            try:  # best effort: hosts carry the TLS/security setting per inbound tag
                hosts = await self._request("GET", "/api/hosts")
                hosts = hosts.get("hosts", []) if isinstance(hosts, dict) else hosts
                sec = {h.get("inbound_tag"): h.get("security") for h in (hosts or [])
                       if isinstance(h, dict) and h.get("inbound_tag") and h.get("security")}
                for r in rows:
                    if not r.get("security") and sec.get(r["tag"]):
                        r["security"] = sec[r["tag"]]
            except Exception:
                pass
        return rows

    async def list_hosts(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/api/hosts")

    async def list_groups(self) -> list[dict[str, Any]]:
        data = None
        for path in ("/api/groups/simple", "/api/groups"):
            try:
                data = await self._request("GET", path)
                break
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in (404, 405):
                    raise
        items = data.get("groups", []) if isinstance(data, dict) else (data or [])
        return [{"id": group["id"], "name": group.get("name") or f"group {group['id']}", **{
                    key: value for key, value in group.items() if key not in {"id", "name"}
                }} for group in items if isinstance(group, dict) and "id" in group]

    def _body(self, spec: dict[str, Any]) -> dict[str, Any]:
        out = {key: value for key, value in spec.items() if key in _USER_KEYS and value is not None}
        if "data_limit" in spec and spec["data_limit"] is None:
            out["data_limit"] = 0
        if "expire" in spec:
            out["expire"] = _iso(spec["expire"])
        plan_spec = spec.get("access_plan") if isinstance(spec.get("access_plan"), dict) else spec
        plan = AccessPlan.from_spec(plan_spec)
        if plan.group_ids is not None:
            out["group_ids"] = plan.group_ids
        elif spec.get("group_ids") is not None:
            out["group_ids"] = [int(x) for x in spec["group_ids"]]
        return out

    async def create_user(self, spec: dict[str, Any]) -> dict[str, Any]:
        if not spec.get("username"):
            raise ValueError("username is required to create a PasarGuard user")
        body = {"status": "active", "data_limit": 0, "data_limit_reset_strategy": "no_reset",
                **self._body(spec), "username": spec["username"]}
        body["status"] = spec.get("status") or "active"
        try:
            return await self._request("POST", "/api/user", json=body)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 409:
                existing = await self.get_user(str(spec["username"]))
                if existing is None:
                    raise
                body.pop("username", None)
                return await self.modify_user(str(spec["username"]), body)
            raise

    async def modify_user(self, remote_username: str, spec: dict[str, Any]) -> dict[str, Any]:
        return await self._user_call("PUT", remote_username, json=self._body(spec))

    async def delete_user(self, remote_username: str) -> None:
        try:
            await self._user_call("DELETE", remote_username)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise

    async def get_user(self, remote_username: str) -> dict[str, Any] | None:
        try:
            return await self._user_call("GET", remote_username)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return None
            raise

    async def list_users(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        allowed = {"offset", "limit", "username", "status", "admin", "group_id", "search", "sort", "order"}
        params = {key: value for key, value in (filters or {}).items() if key in allowed and value is not None}
        data = await self._request("GET", "/api/users", params=params)
        if isinstance(data, list):
            return {"total": len(data), "users": data}
        return data if isinstance(data, dict) else {"total": 0, "users": []}

    async def set_status(self, remote_username: str, enabled: bool) -> None:
        await self.modify_user(remote_username, {"status": "active" if enabled else "disabled"})

    async def reset_usage(self, remote_username: str) -> None:
        await self._user_call("POST", remote_username, "/reset")

    async def revoke_sub(self, remote_username: str) -> None:
        await self._user_call("POST", remote_username, "/revoke_sub")

    async def get_usages(self, remote_usernames: list[str]) -> dict[str, int]:
        wanted = {name.lower(): name for name in remote_usernames}
        result: dict[str, int] = {}
        for name in remote_usernames:
            try:
                data = await self._request("GET", "/api/users", params={"search": name, "limit": 50, "offset": 0})
                items = data.get("users", []) if isinstance(data, dict) else (data or [])
                for user in items:
                    original = wanted.get(str(user.get("username", "")).lower())
                    if original:
                        result[original] = int(user.get("used_traffic", 0) or 0)
            except Exception:
                # Keep successful usage reads when another user is missing or scope-restricted.
                continue
        return result

    async def get_sub_links(self, remote_username: str) -> list[str]:
        user = await self.get_user(remote_username)
        if not user:
            return []
        links = [link for link in (user.get("links") or []) if isinstance(link, str)]
        if links:
            return links
        subscription = str(user.get("subscription_url") or "")
        url = self.base_url + subscription if subscription.startswith("/") else subscription
        base_parts, target_parts = urlparse(self.base_url), urlparse(url)
        if (not url or target_parts.scheme not in {"http", "https"}
                or target_parts.scheme != base_parts.scheme or target_parts.netloc != base_parts.netloc):
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
        group_ops = {
            "add_groups": "/api/groups/bulk/add", "group_add": "/api/groups/bulk/add",
            "remove_groups": "/api/groups/bulk/remove", "group_remove": "/api/groups/bulk/remove",
        }
        if action in group_ops:
            body = {key: payload[key] for key in ("group_ids", "users", "admins", "has_group_ids") if key in payload}
            if not body.get("group_ids"):
                raise ValueError("PasarGuard group bulk actions require group_ids")
            if dry_run:
                return {"dry_run": True, "action": action, "filters": body}
            result = await self._request("POST", group_ops[action], json=body)
            return {"dry_run": False, "action": action, "result": result}
        if action in {
            "modify_users", "change_data_limit", "change_expire", "extend_expire",
            "reduce_expire", "increase_traffic", "decrease_traffic",
            "activate_users", "disable_users",
        }:
            usernames = payload.get("usernames") or payload.get("users")
            if not isinstance(usernames, list) or not all(isinstance(x, str) for x in usernames):
                raise ValueError("Per-user bulk changes require usernames as strings")
            amount = int(payload.get("amount", 0) or 0)
            if amount < 0:
                raise ValueError("amount must be non-negative")
            # Read and validate all targets before execution; dry-run never mutates the panel.
            prepared = []
            for username in usernames:
                user = await self.get_user(username)
                if user is None:
                    prepared.append((username, None, "user not found"))
                    continue
                spec = dict(payload.get("spec") or {})
                current = user.get("expire")
                if isinstance(current, str):
                    try:
                        current = int(datetime.fromisoformat(current.replace("Z", "+00:00")).timestamp())
                    except ValueError:
                        current = 0
                current = int(current or 0)
                now = int(datetime.now(timezone.utc).timestamp())
                if action == "change_data_limit":
                    spec["data_limit"] = amount
                elif action in {"increase_traffic", "decrease_traffic"}:
                    used_limit = int(user.get("data_limit", 0) or 0)
                    delta = amount
                    spec["data_limit"] = max(0, used_limit + (delta if action == "increase_traffic" else -delta))
                elif action == "change_expire":
                    spec["expire"] = amount
                elif action in {"extend_expire", "reduce_expire"}:
                    base = max(current, now) if action == "extend_expire" else current
                    spec["expire"] = max(now, base + (amount * 86400 if action == "extend_expire" else -amount * 86400))
                elif action == "activate_users":
                    spec["status"] = "active"
                elif action == "disable_users":
                    spec["status"] = "disabled"
                prepared.append((username, spec, None))
            if dry_run:
                return {"dry_run": True, "action": action, "count": len(usernames),
                        "valid": sum(1 for _, spec, error in prepared if spec is not None and not error),
                        "errors": [{"username": name, "error": error} for name, _, error in prepared if error]}
            results = []
            for username, spec, error in prepared:
                if error:
                    results.append({"username": username, "ok": False, "error": error})
                    continue
                try:
                    await self.modify_user(username, spec or {})
                    results.append({"username": username, "ok": True})
                except Exception as exc:
                    results.append({"username": username, "ok": False, "error": type(exc).__name__})
            return {"dry_run": False, "action": action, "results": results}
        raise ValueError(f"Unsupported PasarGuard bulk action: {action}")

    async def list_user_templates(self) -> list[dict[str, Any]]:
        # Marzdar-compatible collection route; PasarGuard releases may expose a different template API.
        data = await self._request("GET", "/api/user_template")
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("templates", "user_templates", "items", "data"):
                if isinstance(data.get(key), list):
                    return data[key]
        return []

    async def create_user_from_template(self, spec: dict[str, Any]) -> dict[str, Any]:
        if not spec.get("user_template_id") or not spec.get("username"):
            raise ValueError("user_template_id and username are required")
        # The published PasarGuard API documents applying templates through the bulk endpoint;
        # one-user creation is performed through the regular user endpoint with template fields.
        raise NotImplementedError("PasarGuard documentation does not define a single-user POST /api/user/from_template route; use create_users_from_template or create_user with explicit fields")

    async def modify_user_from_template(self, remote_username: str, spec: dict[str, Any]) -> dict[str, Any]:
        if not spec.get("user_template_id"):
            raise ValueError("user_template_id is required")
        return await self._request("PUT", f"/api/user/{self._u(remote_username)}/from_template", json=spec)

    async def create_users_from_template(self, spec: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", "/api/users/bulk/from_template", json=spec)
