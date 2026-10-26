from datetime import datetime, timezone
from app.db.models import Panel, User, UserPanelAccount, SyncTask
from app.db.session import SessionLocal

def reconcile()->dict:
 queued=0
 with SessionLocal() as db:
  for user in db.query(User).filter(User.status.in_(['active','on_hold','disabled','limited','expired'])).all():
   accounts=db.query(UserPanelAccount).filter_by(user_id=user.id).all()
   for acc in accounts:
    if acc.sync_state!='synced':
     pending=db.query(SyncTask).filter_by(user_id=user.id,panel_id=acc.panel_id,state='pending').first()
     if not pending:
      db.add(SyncTask(user_id=user.id,panel_id=acc.panel_id,action='modify',payload={'username':acc.remote_username,'status':user.status,'data_limit':user.data_limit,'expire':int(user.expire.timestamp()) if user.expire else 0})); queued+=1
  db.commit()
 return {'tasks_queued':queued}
