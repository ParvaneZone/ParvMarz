from abc import ABC, abstractmethod
from typing import Any


class PanelDriver(ABC):
    """Contract for upstream panel integrations. Implementations must be idempotent."""

    def __init__(self, base_url: str, credentials: dict[str, Any], verify_ssl: bool = True):
        self.base_url = base_url.rstrip("/")
        self.credentials = credentials
        self.verify_ssl = verify_ssl

    @abstractmethod
    async def test_connection(self) -> dict[str, Any]: ...

    async def login(self) -> None:
        return None

    async def list_inbounds(self) -> list[dict[str, Any]]:
        return []

    async def list_groups(self) -> list[dict[str, Any]]:
        return []

    async def create_user(self, spec: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    async def modify_user(self, remote_username: str, spec: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    async def delete_user(self, remote_username: str) -> None:
        raise NotImplementedError

    async def get_user(self, remote_username: str) -> dict[str, Any] | None:
        raise NotImplementedError

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

    async def system_stats(self) -> dict[str, Any] | None:
        return None
