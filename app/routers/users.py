from app.config import settings
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, StringConstraints
from typing import Annotated
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.security import require_sudo, require_perm
from app.core.subtokens import issue_subscription_token
from app.db.models import Admin, User, Service, ServiceItem, Panel, PanelInbound, UserPanelAccount, SyncTask, AuditLog, UsageLog
from app.db.session import get_db
from app.core.plans import apply_next_plan
from app.core.access import pick_group
from app.core.permissions import has_perm
from app.schemas import BulkCreateOut, OkOut, SyncStatusOut, UserListOut, UserOut, UserUpdate, UserUsageOut, errs
router=APIRouter(prefix='/api',tags=['users'])
Username = Annotated[str, StringConstraints(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.-]+$")]
class UserIn(BaseModel):
 username:Username; service_id:int; data_limit:int|None=Field(default=None,ge=0); duration_days:int|None=Field(default=30,ge=1,le=36500); expire:datetime|None=None; status:str='active'; on_hold:bool=False; data_limit_reset_strategy:str='no_reset'; note:str=''; next_plan:dict|None=None
 model_config={'json_schema_extra':{'example':{'username':'ali_01','service_id':1,'data_limit':32212254720,'duration_days':30,'note':''}}}

def allowed(admin:Admin, service_id:int):
 if admin.role!='sudo' and service_id not in (admin.allowed_services or []): raise HTTPException(403,detail={'detail':'به این سرویس دسترسی ندارید','code':'SERVICE_FORBIDDEN'})
def user_scope(db,admin):
 q=db.query(User)
 if admin.role!='sudo': q=q.filter(User.admin_id==admin.id)
 return q
@router.get('/users',response_model=UserListOut,summary='لیست کاربران',description='نماینده فقط کاربران خودش را می‌بیند. limit حداکثر ۲۰۰. نیازمند دسترسی users.view.',responses=errs(401,403))
def list_users(q:str|None=None,status:str|None=None,admin_id:int|None=None,service_id:int|None=None,expiring_in_days:int|None=Query(None,ge=0,le=3650),near_limit_percent:int|None=Query(None,ge=1,le=100),sort:str=Query('-id',pattern='^-?(id|username|used_traffic|expire|created_at)$'),limit:int=Query(50,ge=1,le=200),offset:int=Query(0,ge=0),admin:Admin=Depends(require_perm('users.view')),db:Session=Depends(get_db)):
 query=user_scope(db,admin)
 if q: query=query.filter(User.username.ilike(f'%{q}%'))
 if status: query=query.filter(User.status==status)
 if admin.role=='sudo' and admin_id is not None: query=query.filter(User.admin_id==admin_id)
 if service_id is not None: query=query.filter(User.service_id==service_id)
 if expiring_in_days is not None:
  now=datetime.now(timezone.utc); query=query.filter(User.expire.is_not(None),User.expire>now,User.expire<=now+timedelta(days=expiring_in_days))
 if near_limit_percent is not None: query=query.filter(User.data_limit.is_not(None),User.data_limit>0,User.used_traffic*100>=User.data_limit*near_limit_percent)
 col=getattr(User,sort.lstrip('-')); order=col.desc() if sort.startswith('-') else col.asc()
 total=query.count(); rows=query.order_by(order,User.id.desc()).offset(offset).limit(limit).all()
 show=has_perm(admin,'users.view_sub')
 return {'total':total,'items':[serialize_user(u,show) for u in rows]}
def serialize_user(u,show_sub=True):
 token=issue_subscription_token(u.username,int(u.created_at.timestamp()),u.sub_token_version,user_id=u.id)
 return {'id':u.id,'username':u.username,'admin_id':u.admin_id,'service_id':u.service_id,'status':u.status,'data_limit':u.data_limit,'used_traffic':u.used_traffic,'expire':u.expire,'note':u.note,'created_at':u.created_at,'subscription_url':(f'{settings.sub_base_url}/sub/{token}' if settings.split_mode else f'/sub/{token}') if show_sub else None}
@router.post('/user',response_model=UserOut,summary='ساخت کاربر',description='حجم به بایت است. سرویس باید در allowed_services نماینده باشد و سهمیه‌ها (تعداد/حجم/مدت) بررسی می‌شود. ساخت روی پنل‌ها غیرهمزمان انجام می‌شود (sync-status را ببینید).',responses=errs(401,403,404,409))
def create_user(body:UserIn,admin:Admin=Depends(require_perm('users.create')),db:Session=Depends(get_db)):
 allowed(admin,body.service_id)
 def deny():
  return HTTPException(403,detail={'detail':'این دسترسی برای شما فعال نیست','code':'PERMISSION_DENIED'})
 if body.note and not has_perm(admin,'users.create_note'): raise deny()
 if body.data_limit_reset_strategy!='no_reset' and not has_perm(admin,'users.create_reset_strategy'): raise deny()
 if body.expire and not has_perm(admin,'users.create_expire_date'): raise deny()
 if body.next_plan and not has_perm(admin,'users.create_next_plan'): raise deny()
 if body.on_hold and not has_perm(admin,'users.on_hold'): raise HTTPException(403,detail={'detail':'این دسترسی برای شما فعال نیست','code':'PERMISSION_DENIED'})
 if body.data_limit is None and not has_perm(admin,'users.unlimited_traffic'): raise HTTPException(403,detail={'detail':'حجم نامحدود برای شما مجاز نیست','code':'PERMISSION_DENIED'})
 if body.duration_days is None and not body.expire and not has_perm(admin,'users.unlimited_days'): raise HTTPException(403,detail={'detail':'مدت نامحدود برای شما مجاز نیست','code':'PERMISSION_DENIED'})
 service=db.get(Service,body.service_id)
 if not service or not service.enabled: raise HTTPException(404,detail={'detail':'سرویس فعال پیدا نشد','code':'SERVICE_NOT_FOUND'})
 if db.query(User).filter(func.lower(User.username)==body.username.lower()).first(): raise HTTPException(409,detail={'detail':'نام کاربری تکراری است','code':'USERNAME_EXISTS'})
 if body.status not in ('active','disabled','limited','expired','on_hold'): raise HTTPException(422,detail={'detail':'وضعیت نامعتبر است','code':'INVALID_STATUS'})
 if admin.role!='sudo':
  count=db.query(User).filter_by(admin_id=admin.id).count()
  total=db.query(func.coalesce(func.sum(User.data_limit),0)).filter_by(admin_id=admin.id).scalar() or 0
  if admin.max_users is not None and count>=admin.max_users: raise HTTPException(403,detail={'detail':'سهمیه تعداد کاربران تمام شده','code':'QUOTA_USERS'})
  if admin.max_user_traffic is not None and (body.data_limit is None or body.data_limit>admin.max_user_traffic): raise HTTPException(403,detail={'detail':'حجم نامحدود یا بیش از سهمیه مجاز نیست','code':'QUOTA_USER_TRAFFIC'})
  if admin.max_total_traffic is not None and (body.data_limit is None or total+body.data_limit>admin.max_total_traffic): raise HTTPException(403,detail={'detail':'سهمیه مجموع حجم تمام شده یا حجم نامحدود مجاز نیست','code':'QUOTA_TOTAL_TRAFFIC'})
  if admin.max_user_days is not None and (body.duration_days is None or body.duration_days>admin.max_user_days): raise HTTPException(403,detail={'detail':'مدت نامحدود یا بیشتر از سهمیه مجاز نیست','code':'QUOTA_USER_DAYS'})
 exp=None if body.on_hold else (body.expire or ((datetime.now(timezone.utc)+timedelta(days=body.duration_days)) if body.duration_days else None))
 if admin.role!='sudo' and admin.max_user_days is not None and not body.on_hold:
  now=datetime.now(timezone.utc)
  if exp is None or ((exp.replace(tzinfo=timezone.utc) if exp.tzinfo is None else exp)-now).total_seconds()>admin.max_user_days*86400:
   raise HTTPException(403,detail={'detail':'مدت کاربر از سهمیه بیشتر است یا انقضای نامحدود مجاز نیست','code':'QUOTA_USER_DAYS'})
 u=User(username=body.username,admin_id=admin.id,service_id=body.service_id,data_limit=body.data_limit,expire=exp,on_hold_expire_duration=(body.duration_days*86400 if body.on_hold and body.duration_days else None),status='on_hold' if body.on_hold else body.status,data_limit_reset_strategy=body.data_limit_reset_strategy,note=body.note,next_plan=body.next_plan)
 db.add(u); db.flush()
 items=db.query(ServiceItem).filter_by(service_id=service.id,enabled=True).all()
 if not items: raise HTTPException(409,detail={'detail':'برای این سرویس پنل یا اینباندی تعریف نشده است','code':'SERVICE_EMPTY'})
 seen=set()
 for item in sorted(items,key=lambda x:x.priority):
  p=db.get(Panel,item.panel_id)
  if not p or not p.enabled or p.id in seen: continue
  seen.add(p.id); remote=f'{p.username_prefix}{u.username}'
  db.add(UserPanelAccount(user_id=u.id,panel_id=p.id,remote_username=remote,sync_state='pending'))
  cached=db.query(PanelInbound).filter_by(panel_id=p.id).all()
  inbound_rows=[x for x in cached if x.kind=='inbound']; group_rows=[x for x in cached if x.kind=='group']
  selected=set(str(x) for x in (item.selected_items or []))
  def match(x): return str(x.id) in selected or str(x.remote_id) in selected or bool(x.tag and x.tag in selected)
  chosen=[x for x in inbound_rows if match(x)] if selected else inbound_rows
  if p.type in ('rebecca','pasarguard'):
   # Admins pick inbounds; the upstream still needs a service/group, resolved here from the chosen inbounds.
   legacy=[g for g in group_rows if match(g)] if selected else []
   group=legacy[0] if legacy else pick_group(group_rows,{x.tag for x in chosen if x.tag})
   if not group: raise HTTPException(409,detail={'detail':f'برای پنل {p.name} سرویس/گروهی پیدا نشد؛ پنل را همگام‌سازی کنید','code':'PANEL_SERVICE_REQUIRED'})
   payload={'username':remote,'data_limit':u.data_limit,'expire':int(exp.timestamp()) if exp else 0,'status':u.status,'note':u.note}
   if p.type=='rebecca': payload['service_id']=int(group.remote_id)
   else: payload['group_ids']=[int(group.remote_id)]
  else:
   if not chosen: raise HTTPException(409,detail={'detail':f'برای پنل {p.name} اینباندی در کش نیست؛ ابتدا همگام‌سازی کنید','code':'PANEL_INBOUNDS_EMPTY'})
   inbound_map={}
   protocols=set()
   for inbound in chosen:
    protocol=(inbound.protocol or 'vless').lower()
    protocols.add(protocol)
    if inbound.tag: inbound_map.setdefault(protocol,[]).append(inbound.tag)
   proxies={protocol:{} for protocol in (protocols or {'vless'})}
   payload={'username':remote,'data_limit':u.data_limit,'expire':int(exp.timestamp()) if exp else 0,'status':u.status,'note':u.note,'inbounds':inbound_map,'proxies':proxies}
  db.add(SyncTask(user_id=u.id,panel_id=p.id,action='create',payload=payload))
 db.add(AuditLog(actor_admin_id=admin.id,action='user.create',object_type='user',object_id=str(u.id),details={'username':u.username,'service_id':service.id})); db.commit(); db.refresh(u); return serialize_user(u,has_perm(admin,'users.view_sub'))
class BulkCreate(BaseModel):
 prefix:Annotated[str,StringConstraints(min_length=1,max_length=100,pattern=r'^[A-Za-z0-9_.-]+$')]; count:int=Field(ge=1,le=100); start:int=Field(default=1,ge=0)
 service_id:int; data_limit:int|None=Field(default=None,ge=0); duration_days:int|None=Field(default=30,ge=1,le=36500); on_hold:bool=False; note:str=''
@router.post('/users/bulk-create',response_model=BulkCreateOut,response_model_exclude_unset=True,summary='ساخت گروهی کاربر',description='نام‌ها = prefix + شماره از start. با اولین خطا متوقف می‌شود و failed_at و error برمی‌گردد. نیازمند users.create_bulk.',responses=errs(401,403))
def bulk_create(body:BulkCreate,admin:Admin=Depends(require_perm('users.create_bulk')),db:Session=Depends(get_db)):
 created=[]
 for i in range(body.start,body.start+body.count):
  try: r=create_user(UserIn(username=f'{body.prefix}{i}',service_id=body.service_id,data_limit=body.data_limit,duration_days=body.duration_days,on_hold=body.on_hold,note=body.note),admin,db)
  except HTTPException as e:
   db.rollback(); return {'created':created,'failed_at':f'{body.prefix}{i}','error':e.detail}
  created.append({'username':r['username'],'subscription_url':r['subscription_url']})
 return {'created':created}
@router.get('/user/{username}',response_model=UserOut,summary='دریافت یک کاربر',responses=errs(401,403,404))
def get_user(username:str,admin:Admin=Depends(require_perm('users.view')),db:Session=Depends(get_db)):
 u=user_scope(db,admin).filter(func.lower(User.username)==username.lower()).first()
 if not u: raise HTTPException(404,detail={'detail':'کاربر پیدا نشد','code':'USER_NOT_FOUND'})
 return serialize_user(u,has_perm(admin,'users.view_sub'))
@router.put('/user/{username}',response_model=UserOut,summary='ویرایش کاربر',description='فقط فیلدهای ارسال‌شده تغییر می‌کنند. هر فیلد دسترسی جدا دارد (users.edit_status/edit_traffic/edit_expire/edit_note).',responses=errs(401,403,404))
def update_user(username:str,body:UserUpdate,admin:Admin=Depends(require_perm('users.edit')),db:Session=Depends(get_db)):
 body=body.model_dump(exclude_unset=True)
 u=user_scope(db,admin).filter(func.lower(User.username)==username.lower()).first()
 if not u: raise HTTPException(404,detail={'detail':'کاربر پیدا نشد','code':'USER_NOT_FOUND'})
 fields={'status','data_limit','expire','note','data_limit_reset_strategy','next_plan','on_hold_expire_duration','on_hold_timeout'}
 need={'status':'users.edit_status','data_limit':'users.edit_traffic','expire':'users.edit_expire','note':'users.edit_note'}
 for k in body:
  if k in need and not has_perm(admin,need[k]): raise HTTPException(403,detail={'detail':'این دسترسی برای شما فعال نیست','code':'PERMISSION_DENIED'})
  if k=='data_limit' and body[k] is None and not has_perm(admin,'users.unlimited_traffic'): raise HTTPException(403,detail={'detail':'حجم نامحدود برای شما مجاز نیست','code':'PERMISSION_DENIED'})
  if k=='expire' and body[k] is None and not has_perm(admin,'users.unlimited_days'): raise HTTPException(403,detail={'detail':'مدت نامحدود برای شما مجاز نیست','code':'PERMISSION_DENIED'})
 if admin.role!='sudo' and 'data_limit' in body:
  new_limit=body['data_limit']
  if admin.max_user_traffic is not None and (new_limit is None or int(new_limit)>admin.max_user_traffic): raise HTTPException(403,detail={'detail':'حجم کاربر از سهمیه بیشتر است','code':'QUOTA_USER_TRAFFIC'})
  if admin.max_total_traffic is not None:
   current_total=db.query(func.coalesce(func.sum(User.data_limit),0)).filter(User.admin_id==admin.id,User.id!=u.id).scalar() or 0
   if new_limit is None or current_total+int(new_limit)>admin.max_total_traffic: raise HTTPException(403,detail={'detail':'سهمیه مجموع حجم تمام شده','code':'QUOTA_TOTAL_TRAFFIC'})
 if admin.role!='sudo' and 'expire' in body and admin.max_user_days is not None:
  requested_expire=body['expire']
  if requested_expire is None:
   raise HTTPException(403,detail={'detail':'انقضای نامحدود مجاز نیست','code':'QUOTA_USER_DAYS'})
  parsed=requested_expire if isinstance(requested_expire,datetime) else datetime.fromisoformat(str(requested_expire).replace('Z','+00:00'))
  if parsed.tzinfo is None: parsed=parsed.replace(tzinfo=timezone.utc)
  if (parsed-datetime.now(timezone.utc)).total_seconds()>admin.max_user_days*86400:
   raise HTTPException(403,detail={'detail':'مدت کاربر از سهمیه بیشتر است','code':'QUOTA_USER_DAYS'})
 for k,v in body.items():
  if k not in fields: raise HTTPException(422,detail={'detail':f'فیلد مجاز نیست: {k}','code':'INVALID_FIELD'})
  if k=='status' and v not in ('active','disabled','limited','expired','on_hold'): raise HTTPException(422,detail={'detail':'وضعیت نامعتبر است','code':'INVALID_STATUS'})
  setattr(u,k,v)
 if 'status' in body or 'data_limit' in body or 'expire' in body:
  for a in db.query(UserPanelAccount).filter_by(user_id=u.id).all(): db.add(SyncTask(user_id=u.id,panel_id=a.panel_id,action='modify',payload={'username':a.remote_username,'status':u.status,'data_limit':u.data_limit,'expire':int(u.expire.timestamp()) if u.expire else 0}))
 if 'data_limit_reset_strategy' in body:
  from app.db.models import Setting
  s=db.get(Setting,f'user_reset:{u.id}')
  if s: db.delete(s)
 db.add(AuditLog(actor_admin_id=admin.id,action='user.update',object_type='user',object_id=str(u.id),details={'fields':list(body)})); db.commit(); return serialize_user(u,has_perm(admin,'users.view_sub'))
@router.delete('/user/{username}',response_model=OkOut,summary='حذف کاربر',responses=errs(401,403,404))
def delete_user(username:str,admin:Admin=Depends(require_perm('users.delete')),db:Session=Depends(get_db)):
 u=user_scope(db,admin).filter(func.lower(User.username)==username.lower()).first()
 if not u: raise HTTPException(404,detail={'detail':'کاربر پیدا نشد','code':'USER_NOT_FOUND'})
 accounts=db.query(UserPanelAccount).filter_by(user_id=u.id).all()
 for a in accounts: db.add(SyncTask(user_id=None,panel_id=a.panel_id,action='delete',payload={'username':a.remote_username,'admin_id':u.admin_id}))
 for a in accounts: db.delete(a)
 db.add(AuditLog(actor_admin_id=admin.id,action='user.delete',object_type='user',object_id=str(u.id),details={'username':u.username})); db.delete(u); db.commit(); return {'ok':True}
@router.get('/user/{username}/sync-status',response_model=SyncStatusOut,summary='وضعیت همگام‌سازی کاربر با پنل‌ها',responses=errs(401,403,404))
def user_sync_status(username:str,admin:Admin=Depends(require_perm('users.view')),db:Session=Depends(get_db)):
 """Why does this user have no configs? Per-panel sync state plus the last task error."""
 u=user_scope(db,admin).filter(func.lower(User.username)==username.lower()).first()
 if not u: raise HTTPException(404,detail={'detail':'کاربر پیدا نشد','code':'USER_NOT_FOUND'})
 out=[]
 for a in db.query(UserPanelAccount).filter_by(user_id=u.id).all():
  p=db.get(Panel,a.panel_id); t=db.query(SyncTask).filter_by(user_id=u.id,panel_id=a.panel_id).order_by(SyncTask.id.desc()).first()
  out.append({'panel':p.name if p else a.panel_id,'panel_status':p.status if p else None,'remote_username':a.remote_username,'sync_state':a.sync_state,
   'last_task':{'action':t.action,'state':t.state,'attempts':t.attempts,'error':t.last_error} if t else None})
 return {'username':u.username,'status':u.status,'accounts':out}
@router.post('/user/{username}/reset',response_model=OkOut,summary='ریست مصرف کاربر',responses=errs(401,403,404))
def reset_user(username:str,admin:Admin=Depends(require_perm('users.reset')),db:Session=Depends(get_db)):
 u=user_scope(db,admin).filter(func.lower(User.username)==username.lower()).first()
 if not u: raise HTTPException(404,detail={'detail':'کاربر پیدا نشد','code':'USER_NOT_FOUND'})
 u.used_traffic=0
 for a in db.query(UserPanelAccount).filter_by(user_id=u.id).all(): db.add(SyncTask(user_id=u.id,panel_id=a.panel_id,action='reset_usage',payload={'username':a.remote_username}))
 db.add(AuditLog(actor_admin_id=admin.id,action='user.reset_usage',object_type='user',object_id=str(u.id),details={})); db.commit(); return {'ok':True}
@router.post('/user/{username}/revoke_sub',response_model=OkOut,summary='ابطال و ساخت مجدد لینک اشتراک',responses=errs(401,403,404))
def revoke_sub(username:str,admin:Admin=Depends(require_perm('users.revoke_sub')),db:Session=Depends(get_db)):
 u=user_scope(db,admin).filter(func.lower(User.username)==username.lower()).first()
 if not u: raise HTTPException(404,detail={'detail':'کاربر پیدا نشد','code':'USER_NOT_FOUND'})
 u.sub_token_version+=1; u.sub_revoked_at=datetime.now(timezone.utc)
 db.add(AuditLog(actor_admin_id=admin.id,action='user.revoke_sub',object_type='user',object_id=str(u.id),details={})); db.commit(); return {'ok':True}
@router.get('/user/{username}/usage',response_model=UserUsageOut,summary='تاریخچه مصرف کاربر (۱۰۰ مورد آخر)',responses=errs(401,403,404))
def user_usage(username:str,admin:Admin=Depends(require_perm('users.usage_logs')),db:Session=Depends(get_db)):
 u=user_scope(db,admin).filter(func.lower(User.username)==username.lower()).first()
 if not u: raise HTTPException(404,detail={'detail':'کاربر پیدا نشد','code':'USER_NOT_FOUND'})
 logs=db.query(UsageLog).filter_by(user_id=u.id).order_by(UsageLog.id.desc()).limit(100).all()
 return {'used_traffic':u.used_traffic,'data_limit':u.data_limit,'logs':[{'delta':x.delta,'total_after':x.total_after,'recorded_at':x.recorded_at} for x in logs]}
@router.post('/user/{username}/active-next',response_model=UserOut,summary='فعال‌سازی پلن بعدی',responses=errs(401,403,404,409))
def activate_next(username:str,admin:Admin=Depends(require_perm('users.next_plan')),db:Session=Depends(get_db)):
 u=user_scope(db,admin).filter(func.lower(User.username)==username.lower()).first()
 if not u: raise HTTPException(404,detail={'detail':'کاربر پیدا نشد','code':'USER_NOT_FOUND'})
 if not u.next_plan: raise HTTPException(409,detail={'detail':'پلن بعدی تعریف نشده','code':'NO_NEXT_PLAN'})
 plan=u.next_plan
 try: new_limit,new_expire,remaining_added=apply_next_plan(u.data_limit,u.used_traffic,plan)
 except (ValueError,TypeError): raise HTTPException(422,detail={'detail':'تعریف پلن بعدی نامعتبر است','code':'INVALID_NEXT_PLAN'})
 u.data_limit=new_limit; u.used_traffic=0; u.expire=new_expire; u.status='active'; u.next_plan=None
 for a in db.query(UserPanelAccount).filter_by(user_id=u.id).all(): db.add(SyncTask(user_id=u.id,panel_id=a.panel_id,action='modify',payload={'username':a.remote_username,'data_limit':u.data_limit,'expire':int(u.expire.timestamp()),'status':'active'}))
 db.add(AuditLog(actor_admin_id=admin.id,action='user.active_next',object_type='user',object_id=str(u.id),details={'remaining_added':remaining_added})); db.commit(); return serialize_user(u,has_perm(admin,'users.view_sub'))
@router.post('/user/{username}/set-owner')
def set_owner(username:str,body:dict,actor:Admin=Depends(require_sudo),db:Session=Depends(get_db)):
 u=db.query(User).filter(func.lower(User.username)==username.lower()).first(); target=db.get(Admin,int(body.get('admin_id',0)))
 if not u or not target: raise HTTPException(404,detail={'detail':'کاربر یا ادمین پیدا نشد','code':'NOT_FOUND'})
 if target.role!='sudo' and u.service_id not in (target.allowed_services or []): raise HTTPException(403,detail={'detail':'ادمین مقصد به سرویس این کاربر دسترسی ندارد','code':'SERVICE_FORBIDDEN'})
 u.admin_id=target.id; u.sub_token_version+=1; db.add(AuditLog(actor_admin_id=actor.id,action='user.set_owner',object_type='user',object_id=str(u.id),details={'admin_id':target.id})); db.commit(); return {'ok':True}
@router.get('/users/expired')
def expired_users(dry_run:bool=True,admin:Admin=Depends(require_sudo),db:Session=Depends(get_db)):
 rows=db.query(User).filter(User.expire.is_not(None),User.expire<=datetime.now(timezone.utc)).all()
 return {'dry_run':dry_run,'count':len(rows),'users':[u.username for u in rows]}
@router.delete('/users/expired')
def delete_expired(dry_run:bool=True,admin:Admin=Depends(require_sudo),db:Session=Depends(get_db)):
 rows=db.query(User).filter(User.expire.is_not(None),User.expire<=datetime.now(timezone.utc)).all(); names=[u.username for u in rows]
 if not dry_run:
  for u in rows:
   accounts=db.query(UserPanelAccount).filter_by(user_id=u.id).all()
   for a in accounts: db.add(SyncTask(user_id=None,panel_id=a.panel_id,action='delete',payload={'username':a.remote_username,'admin_id':u.admin_id}))
   for a in accounts: db.delete(a)
   db.delete(u)
  db.add(AuditLog(actor_admin_id=admin.id,action='users.delete_expired',object_type='users',object_id='bulk',details={'count':len(rows)})); db.commit()
 return {'dry_run':dry_run,'count':len(rows),'users':names}
