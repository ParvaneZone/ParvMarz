"""Shared recovery rule: a limited/expired user whose limits are fine again goes back to active (and panels are told)."""
from datetime import datetime, timezone
from app.db.models import SyncTask, User, UserPanelAccount


def restore_active(db, u: User, sync: bool = True) -> bool:
    """Flip limited/expired -> active when neither the traffic limit nor the expiry is still exceeded.

    Never touches disabled/on_hold/active users. With sync=True a status `modify` task is queued per panel account;
    pass sync=False when the caller already queues its own modify task that carries u.status.
    Returns True when the status changed."""
    if u.status not in ("limited", "expired"):
        return False
    if u.data_limit is not None and int(u.used_traffic or 0) >= int(u.data_limit):
        return False
    if u.expire is not None:
        exp = u.expire if u.expire.tzinfo else u.expire.replace(tzinfo=timezone.utc)
        if exp <= datetime.now(timezone.utc):
            return False
    u.status = "active"
    if sync:
        for a in db.query(UserPanelAccount).filter_by(user_id=u.id).all():
            db.add(SyncTask(user_id=u.id, panel_id=a.panel_id, action="modify",
                            payload={"username": a.remote_username, "status": "active"}))
    return True
