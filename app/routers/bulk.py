from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.security import require_sudo
from app.db.models import Admin, User, UserPanelAccount, SyncTask, AuditLog
from app.db.session import get_db
router=APIRouter(prefix='/api/bulk',tags=['bulk'])
class BulkIds(BaseModel): user_ids:list[int]=Field(min_length=1,max_length=1000)
class BulkAdjust(BulkIds): amount:int=Field(gt=0)
@router.post('/status')
def bulk_status(body:BulkIds,status:str,actor:Admin=Depends(require_sudo),db:Session=Depends(get_db)):
 if status not in ('active','disabled','limited','expired','on_hold'): raise HTTPException(422,detail={'detail':'وضعیت نامعتبر است','code':'INVALID_STATUS'})
 rows=db.query(User).filter(User.id.in_(body.user_ids)).all()
 for u in rows:
  u.status=status; u.sub_token_version+=1
  for a in db.query(UserPanelAccount).filter_by(user_id=u.id).all(): db.add(SyncTask(user_id=u.id,panel_id=a.panel_id,action='set_status',payload={'username':a.remote_username,'enabled':status=='active'}))
 db.add(AuditLog(actor_admin_id=actor.id,action='bulk.status',object_type='users',object_id='bulk',details={'count':len(rows),'status':status})); db.commit(); return {'updated':len(rows)}
@router.post('/traffic')
def bulk_traffic(body:BulkAdjust,actor:Admin=Depends(require_sudo),db:Session=Depends(get_db)):
 rows=db.query(User).filter(User.id.in_(body.user_ids)).all()
 for u in rows:
  if u.data_limit is not None: u.data_limit+=body.amount
  for a in db.query(UserPanelAccount).filter_by(user_id=u.id).all(): db.add(SyncTask(user_id=u.id,panel_id=a.panel_id,action='modify',payload={'username':a.remote_username,'data_limit':u.data_limit,'status':u.status,'expire':int(u.expire.timestamp()) if u.expire else 0}))
 db.add(AuditLog(actor_admin_id=actor.id,action='bulk.traffic',object_type='users',object_id='bulk',details={'count':len(rows),'amount':body.amount})); db.commit(); return {'updated':len(rows)}
@router.post('/extend')
def bulk_extend(body:BulkAdjust,actor:Admin=Depends(require_sudo),db:Session=Depends(get_db)):
 rows=db.query(User).filter(User.id.in_(body.user_ids)).all()
 for u in rows:
  current=u.expire or datetime.now(timezone.utc)
  if current.tzinfo is None: current=current.replace(tzinfo=timezone.utc)
  u.expire=max(current,datetime.now(timezone.utc))+timedelta(days=body.amount)
  for a in db.query(UserPanelAccount).filter_by(user_id=u.id).all(): db.add(SyncTask(user_id=u.id,panel_id=a.panel_id,action='modify',payload={'username':a.remote_username,'data_limit':u.data_limit,'status':u.status,'expire':int(u.expire.timestamp())}))
 db.add(AuditLog(actor_admin_id=actor.id,action='bulk.extend',object_type='users',object_id='bulk',details={'count':len(rows),'days':body.amount})); db.commit(); return {'updated':len(rows)}
