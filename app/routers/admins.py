from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.security import require_sudo, hash_password
from app.db.models import Admin, User, AuditLog
from app.db.session import get_db

router = APIRouter(prefix='/api/admins', tags=['admins'])
class AdminCreate(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=12, max_length=200)
    role: str = 'admin'
    max_users: int | None = Field(default=None, ge=0)
    max_total_traffic: int | None = Field(default=None, ge=0)
    max_user_traffic: int | None = Field(default=None, ge=0)
    max_user_days: int | None = Field(default=None, ge=0)
    allowed_services: list[int] = []
    permissions: dict = {}

@router.get('')
def list_admins(_: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    return [{'id':a.id,'username':a.username,'role':a.role,'disabled':a.disabled,'max_users':a.max_users,'allowed_services':a.allowed_services,'created_at':a.created_at} for a in db.query(Admin).order_by(Admin.id).all()]

@router.post('')
def create_admin(body: AdminCreate, actor: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    if body.role not in ('admin','sudo'): raise HTTPException(422, detail={'detail':'نقش نامعتبر است','code':'INVALID_ROLE'})
    if db.query(Admin).filter(func.lower(Admin.username)==body.username.lower()).first(): raise HTTPException(409, detail={'detail':'نام کاربری تکراری است','code':'USERNAME_EXISTS'})
    a=Admin(username=body.username,password_hash=hash_password(body.password),role=body.role,max_users=body.max_users,max_total_traffic=body.max_total_traffic,max_user_traffic=body.max_user_traffic,max_user_days=body.max_user_days,allowed_services=body.allowed_services,permissions=body.permissions)
    db.add(a); db.flush(); db.add(AuditLog(actor_admin_id=actor.id,action='admin.create',object_type='admin',object_id=str(a.id),details={'username':a.username})); db.commit(); db.refresh(a)
    return {'id':a.id,'username':a.username,'role':a.role}

@router.patch('/{admin_id}')
def update_admin(admin_id:int, body:dict, actor:Admin=Depends(require_sudo), db:Session=Depends(get_db)):
    a=db.get(Admin,admin_id)
    if not a: raise HTTPException(404, detail={'detail':'ادمین پیدا نشد','code':'ADMIN_NOT_FOUND'})
    allowed={'disabled','max_users','max_total_traffic','max_user_traffic','max_user_days','allowed_services','permissions','expire','telegram_id'}
    for k,v in body.items():
        if k not in allowed: raise HTTPException(422,detail={'detail':f'فیلد مجاز نیست: {k}','code':'INVALID_FIELD'})
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
    for u in users: u.status=status; u.sub_token_version += 1
    db.add(AuditLog(actor_admin_id=actor.id,action='admin.users_status',object_type='admin',object_id=str(admin_id),details={'status':status,'count':len(users)})); db.commit()
    return {'updated':len(users)}

@router.post('/{admin_id}/reset-usage')
def reset_admin_usage(admin_id:int, actor:Admin=Depends(require_sudo), db:Session=Depends(get_db)):
    if not db.get(Admin,admin_id): raise HTTPException(404,detail={'detail':'ادمین پیدا نشد','code':'ADMIN_NOT_FOUND'})
    users=db.query(User).filter(User.admin_id==admin_id).all()
    for u in users: u.used_traffic=0
    db.add(AuditLog(actor_admin_id=actor.id,action='admin.reset_usage',object_type='admin',object_id=str(admin_id),details={'count':len(users)})); db.commit()
    return {'reset':len(users)}
