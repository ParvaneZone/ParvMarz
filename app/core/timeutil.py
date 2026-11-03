from datetime import timezone


def utc_ts(v) -> int:
    """Unix timestamp of a datetime; a naive value is UTC (never the server's local timezone)."""
    return int((v if v.tzinfo else v.replace(tzinfo=timezone.utc)).timestamp())
