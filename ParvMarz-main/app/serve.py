"""Runs the panel (and, when SUB_PORT is set, the separate subscription app) in ONE process: shared caches, one scheduler."""
import asyncio
import contextlib
import logging
import signal
from pathlib import Path
import uvicorn
from app.config import settings

log = logging.getLogger("jinxdata.serve")
CERT_ROOT = Path("/etc/letsencrypt/live")


def _tls(domain: str) -> dict:
    if not domain:
        return {}
    cert, key = CERT_ROOT / domain / "fullchain.pem", CERT_ROOT / domain / "privkey.pem"
    if cert.is_file() and key.is_file():
        return {"ssl_certfile": str(cert), "ssl_keyfile": str(key)}
    log.warning("domain %s is set but no certificate found; serving plain HTTP until one is issued", domain)
    return {}


def _server(app, port: int, domain: str) -> uvicorn.Server:
    cfg = uvicorn.Config(app, host="0.0.0.0", port=port, log_level=settings.log_level.lower(), server_header=False,
                         proxy_headers=True, timeout_keep_alive=15, access_log=False, **_tls(domain))
    srv = uvicorn.Server(cfg)
    srv.install_signal_handlers = lambda: None            # older uvicorn
    srv.capture_signals = lambda: contextlib.nullcontext()  # newer uvicorn
    return srv


async def main() -> None:
    from app.main import app as panel
    servers = [_server(panel, settings.panel_listen_port, settings.panel_domain)]
    if settings.split_mode:
        from app.sub_main import sub_app
        servers.append(_server(sub_app, settings.sub_listen_port, settings.sub_domain))

    def stop(*_):
        for s in servers:
            s.should_exit = True
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop)
    await asyncio.gather(*(s.serve() for s in servers))


if __name__ == "__main__":
    asyncio.run(main())
