from datetime import datetime, timezone, timedelta
from calendar import monthrange
from app.db.models import User, UserPanelAccount, SyncTask
from app.db.session import SessionLocal

def _next_reset(now, strategy):
 if strategy=='day': return now+timedelta(days=1)
 if strategy=='week': return now+timedelta(days=7)
 if strategy=='month':
  year=now.year+(now.month==12); month=1 if now.month==12 else now.month+1
  return now.replace(year=year,month=month,day=min(now.day,monthrange(year,month)[1]))
 if strategy=='year': return now.replace(year=now.year+1)
 return None

def reset_usage_job()->dict:
 # next reset timestamps are persisted in Setting under user_reset:<id>.
 from app.db.models import Setting
 now=datetime.now(timezone.utc); count=0
 with SessionLocal() as db:
  for u in db.query(User).filter(User.data_limit_reset_strategy!='no_reset').all():
   key=f'user_reset:{u.id}'; setting=db.get(Setting,key)
   if setting and setting.value.get('next') and setting.value['next']>now.timestamp(): continue
   if not setting:
    first=_next_reset(now,u.data_limit_reset_strategy)
    if first: db.add(Setting(key=key,value={'next':first.timestamp()}))
    continue
   u.used_traffic=0
   for a in db.query(UserPanelAccount).filter_by(user_id=u.id).all(): db.add(SyncTask(user_id=u.id,panel_id=a.panel_id,action='reset_usage',payload={'username':a.remote_username}))
   nxt=_next_reset(now,u.data_limit_reset_strategy)
   if nxt: db.merge(Setting(key=key,value={'next':nxt.timestamp()}))
   count+=1
  db.commit()
 return {'users_reset':count}
