from datetime import datetime, timezone, timedelta
import asyncio
from app.core.crypto import decrypt_secret
from app.db.models import Panel, User, UserPanelAccount, UsageLog, SyncTask
from app.core.panel_access import get_panel_credentials
from app.db.session import SessionLocal
from app.drivers.factory import build_driver

def traffic_delta(current:int, previous:int)->int:
    current=max(0,int(current)); previous=max(0,int(previous))
    return current-previous if current>=previous else 0

async def sync_usage()->dict:
 processed=0
 with SessionLocal() as db:
  panels=db.query(Panel).filter_by(enabled=True).all()
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
   except Exception:
    # An invalid scope/credential on one representative must not stop other panels or representatives.
    continue
   with SessionLocal() as db:
    for uid,_,remote,previous in owner_accounts:
     if remote not in usages: continue
     current=max(0,int(usages[remote])); delta=traffic_delta(current,previous)
     acc=db.query(UserPanelAccount).filter_by(user_id=uid,panel_id=pid).first(); user=db.get(User,uid)
     if not acc or not user: continue
     acc.last_remote_used_traffic=current; acc.last_synced_at=datetime.now(timezone.utc)
     if delta:
      user.used_traffic+=delta; user.online_at=datetime.now(timezone.utc); db.add(UsageLog(user_id=uid,delta=delta,total_after=user.used_traffic))
     reason=None
     if user.data_limit is not None and user.used_traffic>=user.data_limit: user.status='limited'; reason='traffic limit reached'
     elif user.expire and (user.expire.replace(tzinfo=timezone.utc) if user.expire.tzinfo is None else user.expire)<=datetime.now(timezone.utc): user.status='expired'; reason='expired'
     if reason:
      user.sub_token_version+=1
      for other in db.query(UserPanelAccount).filter_by(user_id=uid).all(): db.add(SyncTask(user_id=uid,panel_id=other.panel_id,action='set_status',payload={'username':other.remote_username,'enabled':False}))
     if user.status=='on_hold' and (current>0 or user.online_at):
      user.status='active'; user.expire=datetime.now(timezone.utc)+timedelta(seconds=user.on_hold_expire_duration or 2592000); user.sub_token_version+=1
      db.add(SyncTask(user_id=uid,panel_id=pid,action='modify',payload={'username':remote,'status':'active','expire':int(user.expire.timestamp()),'data_limit':user.data_limit}))
     processed+=1
    db.commit()
 return {'accounts_processed':processed}
