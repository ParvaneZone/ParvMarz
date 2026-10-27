import asyncio, base64, json, secrets, time
from urllib.parse import quote
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from app.config import settings
from sqlalchemy import func
from app.core.subtokens import verify_subscription_token
from app.core.crypto import decrypt_secret
from app.db.models import SyncTask, User, UserPanelAccount, Panel, Service, ServiceItem, Setting, InboundAlias, PanelInbound, Admin
from app.db.session import SessionLocal
from app.drivers.factory import build_driver
from app.core.errors import short_error
import logging
log=logging.getLogger('jinxdata.sub')
_fetch_err:dict[int,str]={}
from app.subscription.merge import deduplicate_links, apply_aliases, to_clash, to_singbox, to_v2ray_json
from app.subscription.page import render_subscription_page
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
  except Exception as exc:
   _fetch_err[user_id]=short_error(exc); log.warning('sub links fetch failed (user %s, panel %s): %s',user_id,pid,_fetch_err[user_id]); return False, []
 _fetch_err.pop(user_id,None)
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

def _ts(v): return int(v.timestamp()) if v else None
def _load_user(token:str):
 claims=verify_subscription_token(token)
 if not claims: raise HTTPException(404,'Subscription not found')
 with SessionLocal() as db:
  if 'id' in claims: user=db.get(User,claims['id'])  # compact token (user id inside)
  else: user=db.query(User).filter(func.lower(User.username)==claims['u'].lower()).first()  # legacy token
  if not user or user.sub_token_version!=claims['v']: raise HTTPException(404,'Subscription not found')
  svc=db.get(Service,user.service_id)
  return {'id':user.id,'username':user.username,'version':user.sub_token_version,'status':user.status,'used':user.used_traffic,'limit':user.data_limit,'expire':_ts(user.expire) or 0,'created':_ts(user.created_at) or 0,'service_id':user.service_id,'service_name':(svc.display_name or svc.name) if svc else '','admin_id':user.admin_id,'online_at':_ts(user.online_at),'reset':user.data_limit_reset_strategy,'on_hold_days':(user.on_hold_expire_duration or 0)//86400 or None}
def _inactive(u)->bool:
 return u['status']!='active' or bool(u['expire'] and u['expire']<=int(time.time())) or (u['limit'] is not None and u['used']>=u['limit'])
def _page_state(u)->str:
 if u['status']=='active':
  if u['expire'] and u['expire']<=int(time.time()): return 'expired'
  if u['limit'] is not None and u['used']>=u['limit']: return 'limited'
 return u['status']
_APP_UA=('v2ray','hiddify','streisand','shadowrocket','clash','mihomo','sing-box','singbox','nekobox','nekoray','v2box','foxray','happ','karing','husi','exclave','stash','loon','surge','quantumult','okhttp','dalvik','curl','wget','python','go-http','flclash')
def _wants_page(request:Request)->bool:
 """Browsers get the pretty page; VPN apps (and ?format=raw) get the raw subscription."""
 if request.query_params.get('format')=='raw': return False
 ua=(request.headers.get('user-agent') or '').lower()
 return 'text/html' in (request.headers.get('accept') or '').lower() and ua.startswith('mozilla') and not any(k in ua for k in _APP_UA)
def _public_base(request:Request)->str:
 base=(settings.public_base_url or '').rstrip('/')
 return base if base and 'localhost' not in base and '127.0.0.1' not in base else str(request.base_url).rstrip('/')
def _qr_svg(text:str)->str:
 try:
  import segno
  return segno.make(text,error='m').svg_inline(scale=4,border=1,dark='#000',light='#fff',omitsize=True)
 except Exception: return ''
# Always a *valid* config (proper UUID) so apps can import the subscription and show the reason as its name,
# instead of failing the whole import with an "invalid config" error.
def _placeholder(name:str)->list[str]: return [f'vless://00000000-0000-0000-0000-000000000000@127.0.0.1:1?security=none&type=tcp#'+quote(name)]
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
def _why_empty(u)->str:
 """Tell the admin why an ACTIVE user got no configs (shown as the placeholder's name)."""
 with SessionLocal() as db:
  accs=db.query(UserPanelAccount).filter_by(user_id=u['id']).all()
  if not accs: return 'این سرویس پنلی ندارد'
  if any(a.sync_state!='synced' for a in accs):
   failed=db.query(SyncTask).filter(SyncTask.user_id==u['id'],SyncTask.state=='failed').first()
   if failed: return 'ساخت کاربر روی پنل ناموفق بود'
   return 'کاربر در حال ساخت روی پنل است؛ چند لحظه بعد دوباره امتحان کنید'
 if u['id'] in _fetch_err: return 'اتصال به پنل ناموفق بود'
 return 'پنل برای این کاربر کانفیگی برنگرداند'
@router.get('/sub/{token}/info')
def sub_info(token:str):
 u=_load_user(token); return {'username':u['username'],'status':u['status']}
@router.get('/sub/{token}/usage')
def sub_usage(token:str):
 u=_load_user(token); return {'used_traffic':u['used'],'data_limit':u['limit'],'expire':u['expire']}
@router.api_route('/sub/{token}',methods=['GET','HEAD'])
@router.api_route('/sub/{token}/{client_type}',methods=['GET','HEAD'])
async def subscription(token:str,request:Request,client_type:str='v2ray'):
 u=_load_user(token)
 if client_type not in {'v2ray','clash','clash-meta','sing-box','v2ray-json'}: raise HTTPException(404,'Unsupported client type')
 inactive=_inactive(u)
 links=[] if inactive else await _remote_links(u['id'],u['version'])
 parsed=deduplicate_links(links)
 if client_type=='v2ray' and _wants_page(request):
  nonce=secrets.token_urlsafe(16); sub_url=f"{_public_base(request)}/sub/{token}"
  body=render_subscription_page(nonce=nonce,brand="Link Sub",username=u['username'],state=_page_state(u),used=u['used'],limit=u['limit'],expire=u['expire'],created=u['created'],now=int(time.time()),online_at=u['online_at'],service=u['service_name'],reset=u['reset'],on_hold_days=u['on_hold_days'],links=parsed,sub_url=sub_url,qr_svg=_qr_svg(sub_url))
  return HTMLResponse(body,headers={'Cache-Control':'no-store','X-Robots-Tag':'noindex, nofollow','Content-Security-Policy':f"default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-{nonce}'; img-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"})
 if not links:
  off=_off_links(u)
  if off: parsed=deduplicate_links(off)
 if not parsed:
  name='سرویس فعال نیست' if inactive else _why_empty(u)
  parsed=deduplicate_links(_placeholder(name))
 if client_type in {'clash','clash-meta'}:
  try: body=to_clash(parsed)
  except ImportError: body=json.dumps({'proxies':parsed},ensure_ascii=False)
 elif client_type=='sing-box': body=to_singbox(parsed)
 elif client_type=='v2ray-json': body=to_v2ray_json(parsed)
 else: body='\n'.join(p['raw'] for p in parsed); body=base64.b64encode(body.encode()).decode()
 headers={'subscription-userinfo':f"upload=0; download={u['used']}; total={u['limit'] or 0}; expire={u['expire']}",'profile-update-interval':'6','profile-title':u['username'],'profile-web-page-url':f"{_public_base(request)}/sub/{token}",'content-disposition':'inline; filename="subscription.txt"','x-content-type-options':'nosniff','cache-control':'no-store'}
 return PlainTextResponse(body,headers=headers)
