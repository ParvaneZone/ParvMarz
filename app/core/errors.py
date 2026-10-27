"""Short, secret-free error text that is safe to store and show to admins."""
import httpx


def short_error(exc: BaseException) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code} {exc.request.url.path}"
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return f"{type(exc).__name__}: cannot reach panel"
    if isinstance(exc, (RuntimeError, ValueError, KeyError)):
        return f"{type(exc).__name__}: {str(exc)[:160]}"
    return type(exc).__name__
