import re
from datetime import datetime, timezone
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.security import require_sudo, hash_password, admin_state
from app.core.crypto import encrypt_secret
from app.db.models import AdminPanelAccess, Panel
from app.db.models import Admin, User, AuditLog, Service
from app.core.permissions import CATALOG, KEYS
from app.db.session import get_db

router = APIRouter(prefix='/api/admins', tags=['admins'])
class AdminCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.@-]+$")
    password: str = Field(min_length=12, max_length=72)
    role: str = 'admin'
    max_users: int | None = Field(default=None, ge=0)
    max_total_traffic: int | None = Field(default=None, ge=0)
    max_user_traffic: int | None = Field(default=None, ge=0)
    max_user_days: int | None = Field(default=None, ge=0)
    allowed_services: list[int] = []
    permissions: dict = {}

def _clean_perms(p):
    if not isinstance(p,dict): raise HTTPException(422, detail={'detail':'فیلد permissions باید شیء {کلید: true/false} باشد','code':'INVALID_PERMISSION','field':'permissions'})
    bad=[k for k in p if k not in KEYS]
    if bad: raise HTTPException(422, detail={'detail':f'کلید دسترسی نامعتبر: {", ".join(map(str,bad))}','code':'INVALID_PERMISSION','field':'permissions','invalid_keys':bad})
    return {k:bool(v) for k,v in p.items()}

@router.get('/permissions')
def permissions_catalog(_: Admin = Depends(require_sudo)):
    return [{'group':g,'items':[{'key':k,'label':l} for k,l in items]} for g,items in CATALOG]

@router.get('')
def list_admins(_: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    return [{'id':a.id,'username':a.username,'role':a.role,'disabled':a.disabled,'max_users':a.max_users,'max_total_traffic':a.max_total_traffic,'max_user_traffic':a.max_user_traffic,'max_user_days':a.max_user_days,'permissions':a.permissions or {},'allowed_services':a.allowed_services,'created_at':a.created_at,'totp_enabled':bool(a.totp_enabled),'expire':a.expire,'state':admin_state(a,db),'used_traffic':int(db.query(func.coalesce(func.sum(User.used_traffic),0)).filter(User.admin_id==a.id).scalar() or 0)} for a in db.query(Admin).order_by(Admin.id).all()]

@router.post('')
def create_admin(body: AdminCreate, actor: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    if body.role not in ('admin','sudo'): raise HTTPException(422, detail={'detail':f'نقش «{body.role}» نامعتبر است؛ فقط admin یا sudo','code':'INVALID_ROLE','field':'role'})
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', body.username): raise HTTPException(422, detail={'detail':'نام کاربری فقط می‌تواند شامل حروف انگلیسی، عدد و _ . - باشد','code':'INVALID_USERNAME','field':'username'})
    missing=[i for i in body.allowed_services if not db.get(Service,i)]
    if missing: raise HTTPException(422, detail={'detail':f'سرویس با این شناسه وجود ندارد: {missing}','code':'SERVICE_NOT_FOUND','field':'allowed_services'})
    if db.query(Admin).filter(func.lower(Admin.username)==body.username.lower()).first(): raise HTTPException(409, detail={'detail':'نام کاربری تکراری است','code':'USERNAME_EXISTS'})
    a=Admin(username=body.username,password_hash=hash_password(body.password),role=body.role,max_users=body.max_users,max_total_traffic=body.max_total_traffic,max_user_traffic=body.max_user_traffic,max_user_days=body.max_user_days,allowed_services=body.allowed_services,permissions=_clean_perms(body.permissions))
    db.add(a); db.flush(); db.add(AuditLog(actor_admin_id=actor.id,action='admin.create',object_type='admin',object_id=str(a.id),details={'username':a.username})); db.commit(); db.refresh(a)
    warnings=[]
    if a.role=='admin':
        if not any(a.permissions.values()): warnings.append('هیچ دسترسی‌ای فعال نیست؛ این ادمین نمی‌تواند کاری انجام دهد')
        if not a.allowed_services: warnings.append('هیچ سرویسی انتخاب نشده؛ این ادمین نمی‌تواند کاربر بسازد')
    return {'id':a.id,'username':a.username,'role':a.role,'permissions_enabled':sum(1 for v in a.permissions.values() if v),'allowed_services':a.allowed_services,'warnings':warnings}

@router.patch('/{admin_id}')
def update_admin(admin_id:int, body:dict, actor:Admin=Depends(require_sudo), db:Session=Depends(get_db)):
    a=db.get(Admin,admin_id)
    if not a: raise HTTPException(404, detail={'detail':'ادمین پیدا نشد','code':'ADMIN_NOT_FOUND'})
    allowed={'disabled','max_users','max_total_traffic','max_user_traffic','max_user_days','allowed_services','permissions','expire','telegram_id'}
    for k,v in body.items():
        if k not in allowed: raise HTTPException(422,detail={'detail':f'فیلد مجاز نیست: {k}','code':'INVALID_FIELD'})
        if k=='permissions': v=_clean_perms(v)
        if k=='expire' and v:
            try: v=datetime.fromisoformat(str(v).replace('Z','+00:00'))
            except ValueError: raise HTTPException(422,detail={'detail':'تاریخ نامعتبر است','code':'INVALID_FIELD'})
            if v.tzinfo is None: v=v.replace(tzinfo=timezone.utc)
        elif k=='expire': v=None
        setattr(a,k,v)
    db.add(AuditLog(actor_admin_id=actor.id,action='admin.update',object_type='admin',object_id=str(a.id),details={'fields':list(body)})); db.commit()
    return {'ok':True}

@router.post('/{admin_id}/users-status')
def admin_users_status(admin_id:int, body:dict, actor:Admin=Depends(require_sudo), db:Session=Depends(get_db)):
    a=db.get(Admin,admin_id)
    if not a: raise HTTPException(404,detail={'detail':'ادمین پیدا نشد','code':'ADMIN_NOT_FOUND'})
    status=body.get('status')
    if status not in ('active','disabled','limited','on_hold'): raise HTTPException(422,detail={'detail':'وضعیت نامعتبر است','code':'INVALID_STATUS'})
    users=db.query(User).filter(User.admin_id==admin_id).all()
    for u in users: u.status=status
    db.add(AuditLog(actor_admin_id=actor.id,action='admin.users_status',object_type='admin',object_id=str(admin_id),details={'status':status,'count':len(users)})); db.commit()
    return {'updated':len(users)}

@router.post('/{admin_id}/reset-2fa')
def reset_admin_2fa(admin_id:int, actor:Admin=Depends(require_sudo), db:Session=Depends(get_db)):
    a=db.get(Admin,admin_id)
    if not a: raise HTTPException(404,detail={'detail':'ادمین پیدا نشد','code':'ADMIN_NOT_FOUND'})
    a.totp_enabled=False; a.totp_secret_enc=None; a.totp_last_step=None; a.recovery_codes=[]
    db.add(AuditLog(actor_admin_id=actor.id,action='admin.2fa.reset',object_type='admin',object_id=str(admin_id),details={})); db.commit()
    return {'ok':True}

@router.post('/{admin_id}/reset-usage')
def reset_admin_usage(admin_id:int, actor:Admin=Depends(require_sudo), db:Session=Depends(get_db)):
    if not db.get(Admin,admin_id): raise HTTPException(404,detail={'detail':'ادمین پیدا نشد','code':'ADMIN_NOT_FOUND'})
    users=db.query(User).filter(User.admin_id==admin_id).all()
    for u in users: u.used_traffic=0
    db.add(AuditLog(actor_admin_id=actor.id,action='admin.reset_usage',object_type='admin',object_id=str(admin_id),details={'count':len(users)})); db.commit()
    return {'reset':len(users)}


class PanelAccessCreate(BaseModel):
    panel_id: int = Field(gt=0)
    remote_username: str = Field(default="", max_length=120)
    password: str = Field(min_length=1, max_length=500)


@router.get('/{admin_id}/panel-access')
def list_admin_panel_access(admin_id: int, _: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    if not db.get(Admin, admin_id):
        raise HTTPException(404, detail={'detail': 'ادمین پیدا نشد', 'code': 'ADMIN_NOT_FOUND'})
    rows = db.query(AdminPanelAccess, Panel).join(Panel, Panel.id == AdminPanelAccess.panel_id).filter(
        AdminPanelAccess.admin_id == admin_id).order_by(Panel.id).all()
    return [{'panel_id': access.panel_id, 'panel_name': panel.name,
             'remote_username': access.remote_username, 'credential_configured': True,
             'created_at': access.created_at} for access, panel in rows]


@router.put('/{admin_id}/panel-access')
def set_admin_panel_access(admin_id: int, body: PanelAccessCreate,
                           actor: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    target = db.get(Admin, admin_id)
    panel = db.get(Panel, body.panel_id)
    if not target:
        raise HTTPException(404, detail={'detail': 'ادمین پیدا نشد', 'code': 'ADMIN_NOT_FOUND'})
    if target.role == 'sudo':
        raise HTTPException(422, detail={'detail': 'برای sudo نگاشت اعتبارنامه نمایندگی لازم نیست', 'code': 'SUDO_PANEL_ACCESS'})
    if not panel:
        raise HTTPException(404, detail={'detail': 'پنل پیدا نشد', 'code': 'PANEL_NOT_FOUND'})
    try:
        encrypted = encrypt_secret(body.remote_username + '\n' + body.password)
    except RuntimeError as exc:
        raise HTTPException(503, detail={'detail': str(exc), 'code': 'CRYPTO_NOT_CONFIGURED'}) from exc
    access = db.query(AdminPanelAccess).filter_by(admin_id=admin_id, panel_id=body.panel_id).first()
    if access is None:
        access = AdminPanelAccess(admin_id=admin_id, panel_id=body.panel_id,
                                  remote_username=body.remote_username, credentials_enc=encrypted)
        db.add(access)
    else:
        access.remote_username = body.remote_username
        access.credentials_enc = encrypted
    db.add(AuditLog(actor_admin_id=actor.id, action='admin.panel_access.set', object_type='admin',
                    object_id=str(admin_id), details={'panel_id': body.panel_id}))
    db.commit()
    return {'ok': True, 'admin_id': admin_id, 'panel_id': body.panel_id, 'credential_configured': True}


@router.delete('/{admin_id}/panel-access/{panel_id}')
def delete_admin_panel_access(admin_id: int, panel_id: int,
                              actor: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    access = db.query(AdminPanelAccess).filter_by(admin_id=admin_id, panel_id=panel_id).first()
    if access is None:
        raise HTTPException(404, detail={'detail': 'نگاشت اعتبارنامه پیدا نشد', 'code': 'PANEL_ACCESS_NOT_FOUND'})
    db.delete(access)
    db.add(AuditLog(actor_admin_id=actor.id, action='admin.panel_access.delete', object_type='admin',
                    object_id=str(admin_id), details={'panel_id': panel_id}))
    db.commit()
    return {'ok': True}


class Recharge(BaseModel):
    add_days: int = Field(default=0, ge=0, le=36500)
    add_traffic: int = Field(default=0, ge=0)
    reset_usage: bool = False


@router.post('/{admin_id}/recharge')
def recharge_admin(admin_id:int, body:Recharge, actor:Admin=Depends(require_sudo), db:Session=Depends(get_db)):
    a=db.get(Admin,admin_id)
    if not a: raise HTTPException(404,detail={'detail':'ادمین پیدا نشد','code':'ADMIN_NOT_FOUND'})
    now=datetime.now(timezone.utc)
    if body.add_days:
        cur=a.expire or now
        if cur.tzinfo is None: cur=cur.replace(tzinfo=timezone.utc)
        a.expire=max(cur,now)+timedelta(days=body.add_days)
    if body.add_traffic and a.max_total_traffic is not None: a.max_total_traffic+=body.add_traffic
    if body.reset_usage:
        for u in db.query(User).filter(User.admin_id==admin_id).all(): u.used_traffic=0
    db.add(AuditLog(actor_admin_id=actor.id,action='admin.recharge',object_type='admin',object_id=str(admin_id),details=body.model_dump())); db.commit()
    return {'ok':True,'state':admin_state(a,db),'expire':a.expire,'max_total_traffic':a.max_total_traffic}
