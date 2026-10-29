import random, time


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
