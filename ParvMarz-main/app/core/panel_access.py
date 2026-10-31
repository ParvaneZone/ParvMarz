from sqlalchemy.orm import Session

from app.core.crypto import decrypt_secret
from app.db.models import Admin, AdminPanelAccess, Panel


def get_panel_credentials(db: Session, panel: Panel, admin_id: int | None = None) -> dict[str, str]:
    """Return encrypted, representative-scoped credentials when an owner is supplied.

    A non-sudo representative must have an explicit least-privilege upstream mapping;
    silently falling back to the panel's global credential would elevate their access.
    """
    if admin_id is not None:
        target = db.get(Admin, admin_id)
        access = db.query(AdminPanelAccess).filter_by(admin_id=admin_id, panel_id=panel.id).first()
        if access:
            raw = decrypt_secret(access.credentials_enc)
            username, _, password = raw.partition("\n")
            return {"username": username, "password": password}
        if target is not None and target.role != "sudo":
            raise RuntimeError("No encrypted upstream credential mapping is configured for this representative and panel")
        if target is None:
            raise RuntimeError("Panel task owner no longer exists; refusing to use global panel credentials")
    raw = decrypt_secret(panel.credentials_enc)
    username, _, password = raw.partition("\n")
    return {"username": username, "password": password}
