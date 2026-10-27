import asyncio, base64, json, time
from urllib.parse import quote
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import func
from app.core.subtokens import verify_subscription_token
from app.core.crypto import decrypt_secret
from app.db.models import User, UserPanelAccount, Panel, Service, ServiceItem, Setting, InboundAlias, PanelInbound, Admin
from app.db.session import SessionLocal
from app.drivers.factory import build_driver
from app.subscription.merge import deduplicate_links, apply_aliases, to_clash, to_singbox, to_v2ray_json
router=APIRouter(tags=['subscription'])
_cache:dict[str,tuple[float,list[str]]]={}
async def _remote_links(user_id:int, token_version:int)->list[str]:
 with SessionLocal() as db:
  user=db.get(User,user_id)
  if not user or user.sub_token_version!=token_version: raise HTTPException(404,'Subscription not found')
  accounts=db.query(UserPanelAccount,Panel).join(Panel,Panel.id==UserPanelAccount.panel_id).filter(UserPanelAccount.user_id==user_id,Panel.enabled.is_(True)).all()
  snapshot=[(a.panel_id,a.remote_username,p.type,p.base_url,p.credentials_enc,p.verify_ssl) for a,p in accounts]
  amap={}
  for pid_ in {a[0] for a in snapshot}:
   al={x.tag:x.display_name for x in db.query(InboundAlias).filter_by(panel_id=pid_).all()}
   if al: amap[pid_]=(al,[(x.tag,x.protocol,x.network,x.security) for x in db.query(PanelInbound).filter_by(panel_id=pid_,kind='inbound').all()])
  setting=db.get(Setting,f'subcache:{user_id}:{token_version}')
  persisted=setting.value if setting and isinstance(setting.value,dict) else None
 cache_key=f'{user_id}:{token_version}'; now=time.time()
 if cache_key in _cache and _cache[cache_key][0]>time.monotonic(): return _cache[cache_key][1]
 if persisted and isinstance(persisted.get('links'),list):
  _cache[cache_key]=(time.monotonic()+max(0,persisted.get('expires',0)-now),persisted['links'])
 async def one(row):
  pid,remote,ptype,url,enc,ssl=row
  try:
   username,_,password=decrypt_secret(enc).partition('\n'); driver=build_driver(ptype,url,{'username':username,'password':password},ssl)
   got=await asyncio.wait_for(driver.get_sub_links(remote),timeout=8)
   if pid in amap: got=apply_aliases(got,amap[pid][1],amap[pid][0])
   return True, got
  except Exception:return False, []
 results=await asyncio.gather(*(one(r) for r in snapshot))
 if any(not ok for ok,_ in results):
  if persisted and isinstance(persisted.get('links'),list): return persisted['links']
  if cache_key in _cache: return _cache[cache_key][1]
 links=[link for _,group in results for link in group]
 if links or not snapshot:
  _cache[cache_key]=(time.monotonic()+30,links)
  with SessionLocal() as db:
   db.merge(Setting(key=f'subcache:{user_id}:{token_version}',value={'links':links,'expires':now+30}))
   db.commit()
 return links

def _load_user(token:str):
 claims=verify_subscription_token(token)
 if not claims: raise HTTPException(404,'Subscription not found')
 with SessionLocal() as db:
  user=db.query(User).filter(func.lower(User.username)==claims['u'].lower()).first()
  if not user or user.sub_token_version!=claims['v']: raise HTTPException(404,'Subscription not found')
  return {'id':user.id,'username':user.username,'version':user.sub_token_version,'status':user.status,'used':user.used_traffic,'limit':user.data_limit,'expire':int(user.expire.timestamp()) if user.expire else 0,'created':int(user.created_at.timestamp()),'service_id':user.service_id,'admin_id':user.admin_id}
_OFF_DEFAULT={'expired':'زمان اشتراک شما تمام شده','limited':'حجم اشتراک شما تمام شده','disabled':'اشتراک شما غیرفعال است'}
def _off_links(u)->list[str]:
 """اینباند خاموش: فقط برای کاربران ادمینی که مدیر اصلی دسترسی sub.off_inbound را برایش فعال کرده."""
 from app.core.permissions import has_perm
 now=int(time.time())
 if u['status']=='expired' or (u['expire'] and u['expire']<=now): reason='expired'
 elif u['status']=='limited' or (u['limit'] is not None and u['used']>=u['limit']): reason='limited'
 elif u['status']=='disabled': reason='disabled'
 else: return []
 with SessionLocal() as db:
  admin=db.get(Admin,u['admin_id'])
  if not admin or not has_perm(admin,'sub.off_inbound'): return []
  st=db.get(Setting,f'off_name_{reason}'); name=(st.value.get('value') if st and isinstance(st.value,dict) else '') or _OFF_DEFAULT[reason]
 return [f'vless://00000000-0000-0000-0000-000000000000@127.0.0.1:{i+1}?security=none&type=tcp#'+quote(n.strip()) for i,n in enumerate(str(name).split('|')) if n.strip()]
@router.get('/sub/{token}/info')
def sub_info(token:str):
 u=_load_user(token); return {'username':u['username'],'status':u['status']}
@router.get('/sub/{token}/usage')
def sub_usage(token:str):
 u=_load_user(token); return {'used_traffic':u['used'],'data_limit':u['limit'],'expire':u['expire']}
@router.get('/sub/{token}')
@router.get('/sub/{token}/{client_type}')
async def subscription(token:str,request:Request,client_type:str='v2ray'):
 u=_load_user(token)
 if client_type not in {'v2ray','clash','clash-meta','sing-box','v2ray-json'}: raise HTTPException(404,'Unsupported client type')
 links=[] if u['status']!='active' or (u['expire'] and u['expire']<=int(time.time())) or (u['limit'] is not None and u['used']>=u['limit']) else await _remote_links(u['id'],u['version'])
 parsed=deduplicate_links(links)
 if not links:
  off=_off_links(u)
  if off: parsed=deduplicate_links(off)
 if not parsed: body='vless://invalid@127.0.0.1:443#%E2%9B%94%20%D8%B3%D8%B1%D9%88%DB%8C%D8%B3%20%D9%81%D8%B9%D8%A7%D9%84%20%D9%86%DB%8C%D8%B3%D8%AA'
 elif client_type in {'clash','clash-meta'}:
  try: body=to_clash(parsed)
  except ImportError: body=json.dumps({'proxies':parsed},ensure_ascii=False)
 elif client_type=='sing-box': body=to_singbox(parsed)
 elif client_type=='v2ray-json': body=to_v2ray_json(parsed)
 else: body='\n'.join(p['raw'] for p in parsed); body=base64.b64encode(body.encode()).decode()
 headers={'subscription-userinfo':f"upload=0; download={u['used']}; total={u['limit'] or 0}; expire={u['expire']}",'profile-update-interval':'6','profile-title':base64.b64encode(u['username'].encode()).decode(),'content-disposition':'inline; filename="subscription.txt"','x-content-type-options':'nosniff'}
 return PlainTextResponse(body,headers=headers)
