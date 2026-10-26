from datetime import datetime, timezone, timedelta
import asyncio
from sqlalchemy.orm import Session
from app.config import settings
from app.core.crypto import decrypt_secret
from app.db.models import SyncTask, Panel, UserPanelAccount
from app.db.session import SessionLocal
from app.drivers.factory import build_driver

async def process_one(task_id:int)->bool:
 with SessionLocal() as db:
  task=db.get(SyncTask,task_id)
  if not task or task.state=='done': return True
  panel=db.get(Panel,task.panel_id)
  if not panel or not panel.enabled:
   task.state='pending'; task.attempts+=1; task.last_error='panel unavailable'; task.next_attempt_at=datetime.now(timezone.utc)+timedelta(seconds=min(3600,2**min(task.attempts,10))); db.commit(); return False
  try:
   raw=decrypt_secret(panel.credentials_enc); username,_,password=raw.partition('\n')
   driver=build_driver(panel.type,panel.base_url,{'username':username,'password':password},panel.verify_ssl)
   p=task.payload; remote=p.get('username') or db.query(UserPanelAccount).filter_by(user_id=task.user_id,panel_id=task.panel_id).with_entities(UserPanelAccount.remote_username).scalar()
   if task.action=='create': await driver.create_user({**p,'username':remote})
   elif task.action=='modify':
    spec={k:v for k,v in p.items() if k in {'data_limit','expire','status','note','service_id'}}
    await driver.modify_user(remote,spec)
   elif task.action=='delete': await driver.delete_user(remote)
   elif task.action=='reset_usage': await driver.reset_usage(remote)
   elif task.action=='set_status': await driver.set_status(remote,bool(p.get('enabled')))
   task.state='done'; task.last_error=None
   acc=db.query(UserPanelAccount).filter_by(user_id=task.user_id,panel_id=task.panel_id).first()
   if acc: acc.sync_state='synced'; acc.remote_status=p.get('status',acc.remote_status); acc.last_synced_at=datetime.now(timezone.utc)
   db.commit(); return True
  except Exception as exc:
   task.attempts+=1; task.state='pending'; task.last_error=type(exc).__name__; task.next_attempt_at=datetime.now(timezone.utc)+timedelta(seconds=min(3600,2**min(task.attempts,10))); db.commit(); return False

async def drain_outbox(batch_size:int=100)->dict:
 with SessionLocal() as db:
  now=datetime.now(timezone.utc)
  ids=[x[0] for x in db.query(SyncTask.id).filter(SyncTask.state=='pending',SyncTask.next_attempt_at<=now).order_by(SyncTask.id).limit(batch_size).all()]
 results=await asyncio.gather(*(process_one(i) for i in ids))
 return {'processed':len(ids),'succeeded':sum(results),'failed':len(results)-sum(results)}
