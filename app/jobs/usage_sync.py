from datetime import datetime, timezone, timedelta
from app.db.models import Panel, User, UserPanelAccount, UsageLog, SyncTask
from app.core.panel_access import get_panel_credentials
from app.db.session import SessionLocal
from app.drivers.factory import build_driver
from app.core.errors import short_error
from app.core.notify import notify_event
import logging
log=logging.getLogger('jinxdata.usage')

def traffic_delta(current:int, previous:int)->int:
    current=max(0,int(current)); previous=max(0,int(previous))
    return current-previous if current>=previous else 0

_last_run:dict={}
async def sync_usage()->dict:
 processed=0; touched=set(); now_m=datetime.now(timezone.utc)
 with SessionLocal() as db:
  panels=[x for x in db.query(Panel).filter_by(enabled=True).all() if (now_m-_last_run.get(x.id,datetime.min.replace(tzinfo=timezone.utc))).total_seconds()>=max(15,(x.sync_interval or 60))-1]
  for x in panels: _last_run[x.id]=now_m
  snapshots=[]
  for panel in panels:
   accounts=(db.query(UserPanelAccount, User.admin_id)
             .join(User, User.id==UserPanelAccount.user_id)
             .filter(UserPanelAccount.panel_id==panel.id).all())
   snapshots.append((panel.id,panel.type,panel.base_url,panel.credentials_enc,panel.verify_ssl,
                     [(account.user_id,admin_id,account.remote_username,account.last_remote_used_traffic)
                      for account,admin_id in accounts]))
 for pid,ptype,url,enc,ssl,accounts in snapshots:
  if not accounts: continue
  groups={}
  for record in accounts: groups.setdefault(record[1],[]).append(record)
  for admin_id, owner_accounts in groups.items():
   try:
    with SessionLocal() as db:
     panel=db.get(Panel,pid)
     if not panel: continue
     credentials=get_panel_credentials(db,panel,admin_id)
    driver=build_driver(ptype,url,credentials,ssl)
    usages=await driver.get_usages([a[2] for a in owner_accounts])
   except Exception as exc:
    log.warning('usage sync failed (panel %s, admin %s): %s',pid,admin_id,short_error(exc))
    # An invalid scope/credential on one representative must not stop other panels or representatives.
    continue
   with SessionLocal() as db:
    for uid,_,remote,previous in owner_accounts:
     if remote not in usages: continue
     current=max(0,int(usages[remote]))
     acc=db.query(UserPanelAccount).filter_by(user_id=uid,panel_id=pid).first(); user=db.get(User,uid)
     if not acc or not user: continue
     delta=traffic_delta(current,acc.last_remote_used_traffic)
     acc.last_remote_used_traffic=current; acc.last_synced_at=datetime.now(timezone.utc)
     if delta:
      touched.add(uid); user.used_traffic+=delta; user.online_at=datetime.now(timezone.utc); db.add(UsageLog(user_id=uid,delta=delta,total_after=user.used_traffic,admin_id=user.admin_id,panel_id=pid,service_id=user.service_id))
     reason=None
     if user.status!='active': pass
     elif user.data_limit is not None and user.used_traffic>=user.data_limit: user.status='limited'; reason='traffic limit reached'
     elif user.expire and (user.expire.replace(tzinfo=timezone.utc) if user.expire.tzinfo is None else user.expire)<=datetime.now(timezone.utc): user.status='expired'; reason='expired'
     if reason:
      notify_event('user.'+user.status,{'username':user.username,'reason':reason,'admin_id':user.admin_id})
      for other in db.query(UserPanelAccount).filter_by(user_id=uid).all(): db.add(SyncTask(user_id=uid,panel_id=other.panel_id,action='set_status',payload={'username':other.remote_username,'enabled':False}))
     if user.status=='on_hold' and (current>0 or user.online_at):
      user.status='active'; user.expire=datetime.now(timezone.utc)+timedelta(seconds=user.on_hold_expire_duration or 2592000)
      for other in db.query(UserPanelAccount).filter_by(user_id=uid).all(): db.add(SyncTask(user_id=uid,panel_id=other.panel_id,action='modify',payload={'username':other.remote_username,'status':'active','expire':int(user.expire.timestamp()),'data_limit':user.data_limit}))
     processed+=1
    db.commit()
 if touched:
  with SessionLocal() as db:
   for uid in touched:
    user=db.get(User,uid)
    if not user or user.status!='active' or user.data_limit is None: continue
    accs=db.query(UserPanelAccount).filter_by(user_id=uid).all()
    if len(accs)<2: continue
    left=max(0,user.data_limit-user.used_traffic)
    for a in accs:
     if db.query(SyncTask).filter_by(user_id=uid,panel_id=a.panel_id,action='modify',state='pending').first(): continue
     db.add(SyncTask(user_id=uid,panel_id=a.panel_id,action='modify',payload={'username':a.remote_username,'data_limit':a.last_remote_used_traffic+left}))
   db.commit()
 return {'accounts_processed':processed}
