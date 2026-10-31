import random
import time


def pick_links(parsed: list[dict], mode: str, interval_min: int, count: int, seed: int = 0) -> list[dict]:
    """all = everything; rotate = a window of `count` links that advances every `interval_min` minutes; random = `count` random links."""
    n = len(parsed)
    if mode not in ("rotate", "random") or n <= 1:
        return parsed
    count = min(max(1, int(count or 1)), n)
    if count >= n:
        return parsed
    if mode == "random":
        return random.sample(parsed, count)
    items = sorted(parsed, key=lambda p: (p.get("name", ""), p.get("server", ""), p.get("port", 0)))
    start = (int(time.time() // (max(1, int(interval_min or 60)) * 60)) + seed) % n
    return [items[(start + i) % n] for i in range(count)]


def pick_from_groups(parsed: list[dict], gmap: dict, groups: list[str], mode: str, interval_min: int, count: int, seed: int = 0) -> list[dict]:
    """Each attached group contributes ONE of its links per fetch (rotate = by time window, else random); other links stay."""
    if not groups: return pick_links(parsed, mode, interval_min, count, seed)
    buckets: dict[str, list[dict]] = {}
    rest = []
    for x in parsed:
        g = next((g for g in groups if g in (gmap.get(x["raw"]) or [])), None)
        (buckets.setdefault(g, []) if g else rest).append(x)
    keep = {id(y) for g, xs in buckets.items() for y in pick_links(xs, "rotate" if mode == "rotate" else "random", interval_min, 1, seed + sum(map(ord, g)))}
    keep |= {id(y) for y in pick_links(rest, mode, interval_min, count, seed)}
    return [x for x in parsed if id(x) in keep]
