from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.security import require_sudo
from app.db.models import Admin, Service, SubAccess, User
from app.db.session import get_db

router = APIRouter(prefix="/api/geo", tags=["geo"])


@router.get("", summary="موقعیت کاربران بر اساس IP دریافت سابسکریپشن (فقط مدیر اصلی)")
def geo(limit: int = Query(200, ge=1, le=1000), _: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    rows = (db.query(SubAccess, User.username, Service.display_name)
            .join(User, User.id == SubAccess.user_id).join(Service, Service.id == User.service_id)
            .order_by(SubAccess.last_seen.desc()).limit(limit).all())
    return [{"username": u, "service": s, "ip": a.ip, "inbounds": a.inbounds, "country": a.country, "region": a.region,
             "city": a.city, "isp": a.isp, "hits": a.hits, "last_seen": a.last_seen} for a, u, s in rows]
