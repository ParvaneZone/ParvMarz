"""Helpers for resolving the upstream access object (Rebecca service / PasarGuard group)
that must accompany user creation, while the admin only ever picks *inbounds*."""
from typing import Any


def tags_from_group(item: dict[str, Any]) -> list[str]:
    """Best-effort extraction of the inbound tags a group/service contains."""
    for key in ("inbound_tags", "inbounds", "inbound_ids"):
        value = item.get(key)
        if isinstance(value, dict):  # Marzban-style {protocol: [tags]}
            value = [t for tags in value.values() if isinstance(tags, list) for t in tags]
        if isinstance(value, list):
            out = []
            for v in value:
                tag = v.get("tag") if isinstance(v, dict) else v
                if tag is not None:
                    out.append(str(tag))
            if out:
                return out
    return []


def pick_group(groups: list[Any], chosen_tags: set[str]) -> Any | None:
    """Pick the group whose inbound tags cover the chosen inbounds (tightest cover first),
    then the best partial overlap, then the first group. `groups` need `.extra`."""
    if not groups:
        return None
    def tags(g): return set((getattr(g, "extra", None) or {}).get("inbound_tags") or [])
    if chosen_tags:
        covering = [g for g in groups if tags(g) and chosen_tags <= tags(g)]
        if covering:
            return min(covering, key=lambda g: len(tags(g)))
        best = max(groups, key=lambda g: len(chosen_tags & tags(g)))
        if chosen_tags & tags(best):
            return best
    return groups[0]
