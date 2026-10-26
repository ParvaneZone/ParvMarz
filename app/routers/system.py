from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.security import current_admin, require_sudo
from app.db.models import Admin, User, Panel, SyncTask
from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "subhub"}


@router.get("/system/stats")
def stats(_: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    counts = dict(db.query(User.status, func.count(User.id)).group_by(User.status).all())
    return {"users_by_status": counts, "total_users": sum(counts.values()),
            "panels": {"healthy": db.query(Panel).filter(Panel.status == "healthy").count(),
                       "total": db.query(Panel).count()},
            "pending_sync_tasks": db.query(SyncTask).filter(SyncTask.state == "pending").count()}


@router.get("/admin")
def admin_profile(admin: Admin = Depends(current_admin)):
    return {"id": admin.id, "username": admin.username, "role": admin.role}

@router.get('/system/audit')
def audit_logs(limit:int=100,offset:int=0,_:Admin=Depends(require_sudo),db:Session=Depends(get_db)):
    from app.db.models import AuditLog
    limit=max(1,min(limit,500)); offset=max(0,offset)
    rows=db.query(AuditLog).order_by(AuditLog.id.desc()).offset(offset).limit(limit).all()
    return {'items':[{'id':x.id,'actor_admin_id':x.actor_admin_id,'action':x.action,'object_type':x.object_type,'object_id':x.object_id,'details':x.details,'created_at':x.created_at} for x in rows]}

@router.get('/system/settings')
def get_settings(_:Admin=Depends(require_sudo),db:Session=Depends(get_db)):
    from app.db.models import Setting
    return {x.key:(x.value.get('value') if isinstance(x.value,dict) and 'value' in x.value else x.value) for x in db.query(Setting).all() if not x.key.startswith('subcache:')}

@router.put('/system/settings')
def put_settings(body:dict,actor:Admin=Depends(require_sudo),db:Session=Depends(get_db)):
    from app.db.models import Setting, AuditLog
    if len(body)>100: return {'detail':'Too many settings','code':'TOO_MANY_SETTINGS'}
    for key,value in body.items():
        if not isinstance(key,str) or not key or len(key)>120 or key.startswith('subcache:'):
            from fastapi import HTTPException
            raise HTTPException(422,detail={'detail':'کلید تنظیمات نامعتبر است','code':'INVALID_SETTING'})
        db.merge(Setting(key=key,value={'value':value}))
    db.add(AuditLog(actor_admin_id=actor.id,action='system.settings.update',object_type='settings',object_id='global',details={'keys':list(body)})); db.commit(); return {'ok':True}

@router.post('/system/backup')
def manual_backup(_:Admin=Depends(require_sudo)):
    from app.jobs.backup import backup_database
    try: return backup_database()
    except Exception as exc:
        from fastapi import HTTPException
        raise HTTPException(503,detail={'detail':'تهیه نسخه پشتیبان ناموفق بود','code':'BACKUP_FAILED'}) from exc
