from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AccessPlan:
    """Panel-neutral access plan; it only selects already-existing access objects."""

    inbounds: dict[str, list[str]] | None = None
    service_id: int | None = None
    group_ids: list[int] | None = None

    @classmethod
    def from_spec(cls, spec: dict[str, Any]) -> "AccessPlan":
        inbounds = spec.get("inbounds")
        service_id = spec.get("service_id")
        group_ids = spec.get("group_ids")
        return cls(
            inbounds=inbounds if isinstance(inbounds, dict) else None,
            service_id=int(service_id) if service_id is not None else None,
            group_ids=[int(v) for v in group_ids] if isinstance(group_ids, (list, tuple)) else None,
        )

    def for_panel(self, panel_type: str) -> dict[str, Any]:
        kind = panel_type.lower()
        if kind in {"marzban", "marzdar", "marzyar"}:
            return {"inbounds": self.inbounds or {}}
        if kind == "rebecca":
            if self.service_id is None:
                raise ValueError("Rebecca access plan requires service_id")
            return {"service_id": self.service_id}
        if kind == "pasarguard":
            if self.group_ids is None:
                raise ValueError("PasarGuard access plan requires group_ids")
            return {"group_ids": self.group_ids}
        raise ValueError(f"Unsupported panel type for access plan: {panel_type}")


DEFAULT_CAPABILITIES: dict[str, bool] = {
    "inbounds.read": False,
    "groups.read": False,
    "users.create": False,
    "users.modify": False,
    "users.delete": False,
    "users.read": False,
    "users.list": False,
    "users.status": False,
    "users.reset_usage": False,
    "users.revoke_sub": False,
    "users.usage": False,
    "users.sub_links": False,
    "users.active_next": False,
    "users.bulk": False,
    "templates.read": False,
    "templates.create_from": False,
    "system.stats": False,
    "admins.manage": False,
    "admins.usage": False,
    "admins.users_status": False,
    "admins.remote_owner": False,
    "admins.service_limits": False,
    "users.expired.list": False,
    "users.expired.delete": False,
}


_LIST_KEYS = ("inbounds", "items", "data", "results")

def normalize_hosts(data: Any) -> list[dict[str, Any]]:
    """Panel hosts -> [{tag, remark, address}]. Marzban answers {tag: [host, ...]}, others a list / {hosts: [...]}."""
    out: list[dict[str, Any]] = []

    def add(h: Any, tag: Any = None) -> None:
        if not isinstance(h, dict):
            return
        tag = tag or h.get("inbound_tag") or h.get("tag") or h.get("inbound")
        if isinstance(tag, dict):
            tag = tag.get("tag")
        remark = h.get("remark") or h.get("name")
        if tag and remark:
            addr = h.get("address")
            out.append({"tag": str(tag), "remark": str(remark),
                        "address": (", ".join(map(str, addr)) if isinstance(addr, list) else str(addr or ""))})

    if isinstance(data, dict) and isinstance(data.get("hosts"), list):
        data = data["hosts"]
    if isinstance(data, dict):
        for tag, hosts in data.items():
            for h in (hosts if isinstance(hosts, list) else []):
                add(h, tag)
    elif isinstance(data, list):
        for h in data:
            add(h)
    return out


def normalize_inbounds(data: Any, default_protocol: str | None = None) -> list[dict[str, Any]]:
    """Turn whatever a panel returns for "list inbounds" into [{tag, protocol, network, security, ...}].

    Panels disagree on the shape: Marzban returns {protocol: [inbound, ...]}, Marzneshin/Rebecca a
    list or {items: [...]} of objects, PasarGuard a plain list of tag *strings*. Only real inbounds
    come out of here - never services or groups.
    """
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(item: Any, protocol: str | None) -> None:
        if isinstance(item, (str, int)) and not isinstance(item, bool):
            item = {"tag": str(item)}
        if not isinstance(item, dict):
            return
        tag = item.get("tag") or item.get("name") or item.get("remark")
        if tag is None and item.get("id") is None:
            return
        row = dict(item)
        if tag is not None:
            row["tag"] = str(tag)
        row["protocol"] = item.get("protocol") or protocol
        security = item.get("security")
        if security is None and "tls" in item:
            tls = item.get("tls")
            security = tls if isinstance(tls, str) and tls else ("tls" if tls else "none")
        if security is not None:
            row["security"] = security
        key = row.get("tag") or f"id:{row.get('id')}"
        if key in seen:
            return
        seen.add(key)
        out.append(row)

    def walk(node: Any, protocol: str | None) -> None:
        if isinstance(node, list):
            for item in node:
                add(item, protocol)
        elif isinstance(node, dict):
            for key in _LIST_KEYS:
                if isinstance(node.get(key), (list, dict)):
                    walk(node[key], protocol)
                    return
            for proto, items in node.items():  # Marzban: {"vless": [...], "vmess": [...]}
                if isinstance(items, list):
                    walk(items, str(proto))

    walk(data, default_protocol)
    return out


class RemoteOutcomeUnknown(RuntimeError):
    """A mutating upstream request may have succeeded despite a lost response."""


class PanelDriver(ABC):
    """Contract for upstream panel integrations. Drivers only assign existing resources."""

    capabilities: dict[str, bool] = DEFAULT_CAPABILITIES.copy()

    def __init__(self, base_url: str, credentials: dict[str, Any], verify_ssl: bool = True):
        self.base_url = base_url.rstrip("/")
        self.credentials = credentials
        self.verify_ssl = verify_ssl

    @abstractmethod
    async def test_connection(self) -> dict[str, Any]: ...

    async def login(self) -> None:
        return None

    async def list_inbounds(self) -> list[dict[str, Any]]:
        raise NotImplementedError(f"{type(self).__name__} does not support inbound listing")

    async def list_hosts(self) -> list[dict[str, Any]]:
        raise NotImplementedError(f"{type(self).__name__} does not support host listing")

    async def list_groups(self) -> list[dict[str, Any]]:
        raise NotImplementedError(f"{type(self).__name__} does not support group listing")

    async def create_user(self, spec: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    async def modify_user(self, remote_username: str, spec: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    async def delete_user(self, remote_username: str) -> None:
        raise NotImplementedError

    async def get_user(self, remote_username: str) -> dict[str, Any] | None:
        raise NotImplementedError

    async def list_users(self, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        raise NotImplementedError(f"{type(self).__name__} does not support user listing")

    async def set_status(self, remote_username: str, enabled: bool) -> None:
        raise NotImplementedError

    async def reset_usage(self, remote_username: str) -> None:
        raise NotImplementedError

    async def revoke_sub(self, remote_username: str) -> None:
        raise NotImplementedError

    async def get_usages(self, remote_usernames: list[str]) -> dict[str, int]:
        raise NotImplementedError

    async def get_sub_links(self, remote_username: str) -> list[str]:
        raise NotImplementedError

    async def active_next(self, remote_username: str) -> dict[str, Any]:
        raise NotImplementedError(f"{type(self).__name__} does not support active-next")

    async def bulk_action(self, action: str, payload: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
        raise NotImplementedError(f"{type(self).__name__} does not support bulk action {action!r}")

    async def system_stats(self) -> dict[str, Any] | None:
        raise NotImplementedError(f"{type(self).__name__} does not expose system statistics")
