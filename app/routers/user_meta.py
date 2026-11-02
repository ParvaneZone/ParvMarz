"""Small read-only helpers for the users list (last online time per user)."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.security import require_perm
from app.db.models import Admin, User
from app.db.session import get_db
from app.routers.users import user_scope

router = APIRouter(prefix="/api", tags=["users"])


@router.get("/users/online", summary="آخرین زمان آنلاین کاربران", description="نماینده فقط کاربران خودش را می‌بیند. کلید = شناسه کاربر؛ مقدار null یعنی هنوز متصل نشده.")
def users_online(admin: Admin = Depends(require_perm("users.view")), db: Session = Depends(get_db)):
    rows = user_scope(db, admin).with_entities(User.id, User.online_at).all()
    return {"items": {str(i): (o.isoformat() if o else None) for i, o in rows}}
