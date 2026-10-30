from datetime import datetime, timezone, timedelta
import asyncio
from app.db.models import SyncTask, Panel, UserPanelAccount, User
from app.core.panel_access import get_panel_credentials
from app.db.session import SessionLocal
from app.drivers.factory import build_driver
from app.drivers.base import RemoteOutcomeUnknown
from app.core.errors import short_error
import logging
log=logging.getLogger('jinxdata.outbox')

async def process_one(task_id:int)->bool:
 with SessionLocal() as db:
  task=db.get(SyncTask,task_id)
  if not task or task.state=='done': return True
  panel=db.get(Panel,task.panel_id)
  if not panel or not panel.enabled:
   task.attempts += 1
   task.last_error = 'panel unavailable'
   if task.attempts >= 8:
    task.state = 'failed'
   else:
    task.state = 'pending'
    task.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=min(3600, 2 ** min(task.attempts, 10)))
   db.commit(); return False
  try:
   p=task.payload
   owner = db.get(User, task.user_id) if task.user_id is not None else None
   admin_id = owner.admin_id if owner is not None else p.get('admin_id')
   credentials = get_panel_credentials(db, panel, int(admin_id) if admin_id is not None else None)
   driver=build_driver(panel.type,panel.base_url,credentials,panel.verify_ssl)
   remote=p.get('username') or db.query(UserPanelAccount).filter_by(user_id=task.user_id,panel_id=task.panel_id).with_entities(UserPanelAccount.remote_username).scalar()
   if task.action=='create': await driver.create_user({**p,'username':remote})
   elif task.action=='modify':
    spec={k:v for k,v in p.items() if k in {'data_limit','expire','status','note','service_id','group_ids','inbounds','proxies','data_limit_reset_strategy','on_hold_expire_duration','on_hold_timeout','auto_delete_in_days','next_plan','access_plan','ip_limit','speed_limit_kbps','flow','credential_key','next_plans'}}
    await driver.modify_user(remote,spec)
   elif task.action=='active_next': await driver.active_next(remote)
   elif task.action=='bulk_action': await driver.bulk_action(p.get('bulk_action',''),p.get('arguments',{}),bool(p.get('dry_run',False)))
   elif task.action=='delete': await driver.delete_user(remote)
   elif task.action=='reset_usage': await driver.reset_usage(remote)
   elif task.action=='set_status': await driver.set_status(remote,bool(p.get('enabled')))
   task.state='done'; task.last_error=None
   acc=db.query(UserPanelAccount).filter_by(user_id=task.user_id,panel_id=task.panel_id).first() if task.user_id is not None else None
   if acc: acc.sync_state='synced'; acc.remote_status=p.get('status',acc.remote_status); acc.last_synced_at=datetime.now(timezone.utc)
   db.commit(); return True
  except RemoteOutcomeUnknown:
   task.attempts += 1
   task.state = 'failed'
   task.last_error = 'remote outcome unknown; verify upstream panel before retrying'
   db.commit()
   return False
  except Exception as exc:
   task.attempts += 1
   task.last_error = short_error(exc)
   log.warning('sync task %s (%s, panel %s) failed: %s',task.id,task.action,task.panel_id,task.last_error)
   if task.attempts >= 8:
    task.state = 'failed'
   else:
    task.state = 'pending'
    task.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=min(3600, 2 ** min(task.attempts, 10)))
   db.commit(); return False

async def drain_outbox(batch_size:int=100)->dict:
 with SessionLocal() as db:
  now=datetime.now(timezone.utc)
  ids=[x[0] for x in db.query(SyncTask.id).filter(SyncTask.state=='pending',SyncTask.next_attempt_at<=now).order_by(SyncTask.id).limit(batch_size).all()]
 results=await asyncio.gather(*(process_one(i) for i in ids))
 return {'processed':len(ids),'succeeded':sum(results),'failed':len(results)-sum(results)}
