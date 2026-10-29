from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.core.security import require_perm
from app.db.models import Admin, User, UserPanelAccount, SyncTask, AuditLog
from app.db.session import get_db
router=APIRouter(prefix='/api/bulk',tags=['bulk'])
class BulkIds(BaseModel): user_ids:list[int]=Field(min_length=1,max_length=1000)
class BulkAdjust(BulkIds): amount:int=Field(gt=0)

def _deny(msg,code='QUOTA_EXCEEDED'): return HTTPException(403,detail={'detail':msg,'code':code})
def _rows(db,actor,ids):
 q=db.query(User).filter(User.id.in_(ids))
 if actor.role!='sudo': q=q.filter(User.admin_id==actor.id)  # agents only touch their own users
 return q.all()
def _modify(db,u):
 for a in db.query(UserPanelAccount).filter_by(user_id=u.id).all():
  db.add(SyncTask(user_id=u.id,panel_id=a.panel_id,action='modify',payload={'username':a.remote_username,'data_limit':u.data_limit,'status':u.status,'expire':int(u.expire.timestamp()) if u.expire else 0}))
def _aware(d): return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

@router.post('/status')
def bulk_status(body:BulkIds,status:str,actor:Admin=Depends(require_perm('users.edit_status')),db:Session=Depends(get_db)):
 if status not in ('active','disabled','limited','expired','on_hold'): raise HTTPException(422,detail={'detail':'وضعیت نامعتبر است','code':'INVALID_STATUS'})
 rows=_rows(db,actor,body.user_ids)
 for u in rows:
  u.status=status
  for a in db.query(UserPanelAccount).filter_by(user_id=u.id).all(): db.add(SyncTask(user_id=u.id,panel_id=a.panel_id,action='set_status',payload={'username':a.remote_username,'enabled':status=='active'}))
 db.add(AuditLog(actor_admin_id=actor.id,action='bulk.status',object_type='users',object_id='bulk',details={'count':len(rows),'status':status})); db.commit(); return {'updated':len(rows)}
@router.post('/traffic')
def bulk_traffic(body:BulkAdjust,actor:Admin=Depends(require_perm('users.edit_traffic')),db:Session=Depends(get_db)):
 rows=[u for u in _rows(db,actor,body.user_ids) if u.data_limit is not None]
 if actor.role!='sudo':
  if actor.max_user_traffic is not None and any(u.data_limit+body.amount>actor.max_user_traffic for u in rows): raise _deny('حجم کاربر از سهمیه بیشتر می‌شود','QUOTA_USER_TRAFFIC')
  if actor.max_total_traffic is not None:
   total=db.query(func.coalesce(func.sum(User.data_limit),0)).filter(User.admin_id==actor.id).scalar() or 0
   if total+body.amount*len(rows)>actor.max_total_traffic: raise _deny('سهمیه مجموع حجم تمام می‌شود','QUOTA_TOTAL_TRAFFIC')
 for u in rows: u.data_limit+=body.amount; _modify(db,u)
 db.add(AuditLog(actor_admin_id=actor.id,action='bulk.traffic',object_type='users',object_id='bulk',details={'count':len(rows),'amount':body.amount})); db.commit(); return {'updated':len(rows)}
@router.post('/extend')
def bulk_extend(body:BulkAdjust,actor:Admin=Depends(require_perm('users.edit_expire')),db:Session=Depends(get_db)):
 rows=_rows(db,actor,body.user_ids); now=datetime.now(timezone.utc)
 new={u.id:max(_aware(u.expire) if u.expire else now,now)+timedelta(days=body.amount) for u in rows}
 if actor.role!='sudo' and actor.max_user_days is not None and any((e-now).total_seconds()>actor.max_user_days*86400 for e in new.values()): raise _deny('مدت کاربر از سهمیه بیشتر می‌شود','QUOTA_USER_DAYS')
 for u in rows: u.expire=new[u.id]; _modify(db,u)
 db.add(AuditLog(actor_admin_id=actor.id,action='bulk.extend',object_type='users',object_id='bulk',details={'count':len(rows),'days':body.amount})); db.commit(); return {'updated':len(rows)}
