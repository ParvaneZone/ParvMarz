import logging
from datetime import datetime, timezone, timedelta
from calendar import monthrange
from app.core.status import restore_active
from app.db.models import User, UserPanelAccount, SyncTask
from app.db.session import SessionLocal
log=logging.getLogger('jinxdata.reset')

def _next_reset(now, strategy):
 if strategy=='day': return now+timedelta(days=1)
 if strategy=='week': return now+timedelta(days=7)
 if strategy=='month':
  year=now.year+(now.month==12); month=1 if now.month==12 else now.month+1
  return now.replace(year=year,month=month,day=min(now.day,monthrange(year,month)[1]))
 if strategy=='year':
  year=now.year+1  # Feb 29 -> Feb 28 in a non-leap year instead of raising
  return now.replace(year=year,day=min(now.day,monthrange(year,now.month)[1]))
 return None

def reset_usage_job()->dict:
 # next reset timestamps are persisted in Setting under user_reset:<id>.
 from app.db.models import Setting
 now=datetime.now(timezone.utc); count=0
 with SessionLocal() as db:
  for u in db.query(User).filter(User.data_limit_reset_strategy!='no_reset').all():
   uid=u.id
   try:  # one broken user must not stop the job for everyone else; each user is committed on its own
    key=f'user_reset:{uid}'; setting=db.get(Setting,key)
    if setting and setting.value.get('next') and setting.value['next']>now.timestamp(): continue
    if not setting:
     first=_next_reset(now,u.data_limit_reset_strategy)
     if first: db.add(Setting(key=key,value={'next':first.timestamp()})); db.commit()
     continue
    u.used_traffic=0
    for a in db.query(UserPanelAccount).filter_by(user_id=uid).all(): db.add(SyncTask(user_id=uid,panel_id=a.panel_id,action='reset_usage',payload={'username':a.remote_username}))
    restore_active(db,u)
    nxt=_next_reset(now,u.data_limit_reset_strategy)
    if nxt: db.merge(Setting(key=key,value={'next':nxt.timestamp()}))
    db.commit(); count+=1
   except Exception as exc:
    db.rollback(); log.warning('usage reset failed for user %s: %s',uid,exc)
 return {'users_reset':count}
