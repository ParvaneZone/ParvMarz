from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.security import current_admin, require_sudo
from sqlalchemy import func
from app.db.models import Admin, Service, ServiceItem, Panel, AuditLog, InboundAlias, PanelInbound, Setting, User, UserTemplate
from app.db.session import get_db
from app.schemas import ServiceOut, errs
router=APIRouter(prefix='/api/services',tags=['services'])
class ServiceIn(BaseModel):
 name:str=Field(min_length=1,max_length=120); display_name:str=Field(min_length=1,max_length=120); description:str=''; enabled:bool=True; sort_order:int=0; sub_remark_template:str='{service} | {server}'; inbound_mode:str=Field('all',pattern='^(all|rotate|random)$'); inbound_interval:int=Field(60,ge=1,le=100000); inbound_count:int=Field(1,ge=1,le=1000)
class ItemIn(BaseModel): panel_id:int; selected_items:list=[]; priority:int=0; enabled:bool=True
@router.get('',response_model=list[ServiceOut],response_model_exclude_unset=True,summary='لیست سرویس‌ها',description='نماینده فقط سرویس‌های فعالِ مجاز خودش را می‌بیند. برای ساخت کاربر از id سرویس استفاده کنید.',responses=errs(401))
def list_services(admin:Admin=Depends(current_admin),db:Session=Depends(get_db)):
 q=db.query(Service)
 if admin.role!='sudo': q=q.filter(Service.id.in_(admin.allowed_services or []),Service.enabled.is_(True))
 aliases={(a.panel_id,a.tag):a.display_name for a in db.query(InboundAlias).all()}
 ucount=dict(db.query(User.service_id,func.count(User.id)).group_by(User.service_id).all()) if admin.role=='sudo' else {}
 out=[]
 for s in q.order_by(Service.sort_order,Service.id).all():
  items=db.query(ServiceItem).filter(ServiceItem.service_id==s.id).all()
  d={'id':s.id,'name':s.name,'display_name':s.display_name,'description':s.description,'enabled':s.enabled,'sort_order':s.sort_order,'sub_remark_template':s.sub_remark_template,'inbound_mode':s.inbound_mode,'inbound_interval':s.inbound_interval,'inbound_count':s.inbound_count}
  if admin.role=='sudo':
   d['user_count']=ucount.get(s.id,0)
   gs=db.get(Setting,f'svc_groups:{s.id}'); d['group_ids']=[int(x) for x in (gs.value.get('ids') or [])] if gs and isinstance(gs.value,dict) else []
   d['items']=[{'id':i.id,'panel_id':i.panel_id,'selected_items':i.selected_items,'selected_names':[aliases.get((i.panel_id,str(t)),str(t)) for t in (i.selected_items or [])],'priority':i.priority,'enabled':i.enabled} for i in items]
  else:
   names=[]
   for i in items:
    if not i.enabled: continue
    tags=[str(x) for x in (i.selected_items or [])] or [x.tag for x in db.query(PanelInbound).filter_by(panel_id=i.panel_id,kind='inbound').all() if x.tag]
    names+=[aliases.get((i.panel_id,t),t) if (i.panel_id,t) in aliases else f'#{n+1}' for n,t in enumerate(tags)]
   d['items']=[]; d['inbound_names']=[n for n in names if not n.startswith('#')]
  out.append(d)
 return out
@router.post('')
def create_service(body:ServiceIn,actor:Admin=Depends(require_sudo),db:Session=Depends(get_db)):
 if db.query(Service).filter(Service.name==body.name).first(): raise HTTPException(409,detail={'detail':'نام سرویس تکراری است','code':'SERVICE_EXISTS'})
 s=Service(**body.model_dump()); db.add(s); db.flush(); db.add(AuditLog(actor_admin_id=actor.id,action='service.create',object_type='service',object_id=str(s.id),details={})); db.commit(); db.refresh(s); return {'id':s.id,'name':s.name}
@router.put('/{service_id}')
def update_service(service_id:int,body:ServiceIn,actor:Admin=Depends(require_sudo),db:Session=Depends(get_db)):
 s=db.get(Service,service_id)
 if not s: raise HTTPException(404,detail={'detail':'سرویس پیدا نشد','code':'SERVICE_NOT_FOUND'})
 for k,v in body.model_dump().items(): setattr(s,k,v)
 db.add(AuditLog(actor_admin_id=actor.id,action='service.update',object_type='service',object_id=str(s.id),details={})); db.commit(); return {'ok':True}
@router.delete('/{service_id}')
def delete_service(service_id:int,move_to:int|None=None,actor:Admin=Depends(require_sudo),db:Session=Depends(get_db)):
 from app.routers.users import move_user
 s=db.get(Service,service_id)
 if not s: raise HTTPException(404,detail={'detail':'سرویس پیدا نشد','code':'SERVICE_NOT_FOUND'})
 users=db.query(User).filter_by(service_id=service_id).all(); tpls=db.query(UserTemplate).filter_by(service_id=service_id).all()
 t=None
 if move_to is not None:
  t=db.get(Service,move_to)
  if not t or t.id==service_id: raise HTTPException(404,detail={'detail':'سرویس مقصد نامعتبر است','code':'SERVICE_NOT_FOUND'})
 if users and not t: raise HTTPException(409,detail={'detail':'سرویس مقصد برای انتقال کاربران را انتخاب کنید','code':'SERVICE_IN_USE','users':len(users)})
 for u in users: move_user(db,u,t)
 for x in tpls:
  if t: x.service_id=t.id
  else: db.delete(x)
 for a in db.query(Admin).all():
  ids=list(a.allowed_services or [])
  if service_id in ids:
   ids=[i for i in ids if i!=service_id]
   if t and t.id not in ids: ids.append(t.id)
   a.allowed_services=ids
 db.query(ServiceItem).filter_by(service_id=service_id).delete(); g=db.get(Setting,f'svc_groups:{service_id}')
 if g: db.delete(g)
 db.add(AuditLog(actor_admin_id=actor.id,action='service.delete',object_type='service',object_id=str(s.id),details={'moved_users':len(users),'move_to':move_to})); db.delete(s); db.commit(); return {'ok':True,'moved_users':len(users)}
@router.post('/{service_id}/clone')
def clone_service(service_id:int,actor:Admin=Depends(require_sudo),db:Session=Depends(get_db)):
 s=db.get(Service,service_id)
 if not s: raise HTTPException(404,detail={'detail':'سرویس پیدا نشد','code':'SERVICE_NOT_FOUND'})
 n=1
 while db.query(Service).filter_by(name=f'{s.name}-copy{n}').first(): n+=1
 c=Service(name=f'{s.name}-copy{n}',display_name=f'{s.display_name} (copy)',description=s.description,enabled=False,sort_order=s.sort_order,sub_remark_template=s.sub_remark_template,inbound_mode=s.inbound_mode,inbound_interval=s.inbound_interval,inbound_count=s.inbound_count)
 db.add(c); db.flush()
 for i in db.query(ServiceItem).filter_by(service_id=s.id).all(): db.add(ServiceItem(service_id=c.id,panel_id=i.panel_id,selected_items=list(i.selected_items or []),priority=i.priority,enabled=i.enabled))
 g=db.get(Setting,f'svc_groups:{s.id}')
 if g: db.add(Setting(key=f'svc_groups:{c.id}',value=dict(g.value)))
 db.add(AuditLog(actor_admin_id=actor.id,action='service.clone',object_type='service',object_id=str(c.id),details={'from':s.id})); db.commit(); return {'id':c.id}
class ItemPatch(BaseModel): selected_items:list|None=None; priority:int|None=None; enabled:bool|None=None
@router.put('/{service_id}/items/{item_id}')
def update_item(service_id:int,item_id:int,body:ItemPatch,_:Admin=Depends(require_sudo),db:Session=Depends(get_db)):
 i=db.query(ServiceItem).filter_by(id=item_id,service_id=service_id).first()
 if not i: raise HTTPException(404,detail={'detail':'آیتم پیدا نشد','code':'ITEM_NOT_FOUND'})
 for k,v in body.model_dump(exclude_unset=True).items():
  if v is not None: setattr(i,k,v)
 db.commit(); return {'ok':True}
@router.post('/{service_id}/items')
def add_item(service_id:int,body:ItemIn,actor:Admin=Depends(require_sudo),db:Session=Depends(get_db)):
 if not db.get(Service,service_id): raise HTTPException(404,detail={'detail':'سرویس پیدا نشد','code':'SERVICE_NOT_FOUND'})
 if not db.get(Panel,body.panel_id): raise HTTPException(404,detail={'detail':'پنل پیدا نشد','code':'PANEL_NOT_FOUND'})
 i=ServiceItem(service_id=service_id,**body.model_dump()); db.add(i); db.commit(); db.refresh(i); return {'id':i.id}
@router.delete('/{service_id}/items/{item_id}')
def delete_item(service_id:int,item_id:int,_:Admin=Depends(require_sudo),db:Session=Depends(get_db)):
 i=db.query(ServiceItem).filter_by(id=item_id,service_id=service_id).first()
 if not i: raise HTTPException(404,detail={'detail':'آیتم پیدا نشد','code':'ITEM_NOT_FOUND'})
 db.delete(i); db.commit(); return {'ok':True}

class GroupsIn(BaseModel): group_ids:list[int]=[]
@router.put('/{service_id}/groups')
def set_groups(service_id:int,body:GroupsIn,_:Admin=Depends(require_sudo),db:Session=Depends(get_db)):
 if not db.get(Service,service_id): raise HTTPException(404,detail={'detail':'سرویس پیدا نشد','code':'SERVICE_NOT_FOUND'})
 db.merge(Setting(key=f'svc_groups:{service_id}',value={'ids':body.group_ids})); db.commit(); return {'ok':True}
