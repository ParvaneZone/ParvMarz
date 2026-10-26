from app.drivers.marzban import MarzbanDriver
from app.drivers.pasarguard import PasarGuardDriver
from app.drivers.rebecca import RebeccaDriver


def build_driver(panel_type: str, base_url: str, credentials: dict, verify_ssl: bool = True):
    if panel_type in {"marzban", "marzdar", "marzyar"}:
        return MarzbanDriver(base_url, credentials, verify_ssl)
    if panel_type == "pasarguard":
        return PasarGuardDriver(base_url, credentials, verify_ssl)
    if panel_type == "rebecca":
        return RebeccaDriver(base_url, credentials, verify_ssl)
    raise ValueError(f"Unsupported driver type: {panel_type}")
