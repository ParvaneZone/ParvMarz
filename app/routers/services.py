from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.security import current_admin, require_sudo
from app.db.models import Admin, Service, ServiceItem, Panel, AuditLog, InboundAlias, PanelInbound
from app.db.session import get_db
router=APIRouter(prefix='/api/services',tags=['services'])
class ServiceIn(BaseModel):
 name:str=Field(min_length=1,max_length=120); display_name:str=Field(min_length=1,max_length=120); description:str=''; enabled:bool=True; sort_order:int=0; sub_remark_template:str='{service} | {server}'
class ItemIn(BaseModel): panel_id:int; selected_items:list=[]; priority:int=0; enabled:bool=True
@router.get('')
def list_services(admin:Admin=Depends(current_admin),db:Session=Depends(get_db)):
 q=db.query(Service)
 if admin.role!='sudo': q=q.filter(Service.id.in_(admin.allowed_services or []),Service.enabled.is_(True))
 aliases={(a.panel_id,a.tag):a.display_name for a in db.query(InboundAlias).all()}
 out=[]
 for s in q.order_by(Service.sort_order,Service.id).all():
  items=db.query(ServiceItem).filter(ServiceItem.service_id==s.id).all()
  d={'id':s.id,'name':s.name,'display_name':s.display_name,'description':s.description,'enabled':s.enabled,'sort_order':s.sort_order,'sub_remark_template':s.sub_remark_template}
  if admin.role=='sudo': d['items']=[{'id':i.id,'panel_id':i.panel_id,'selected_items':i.selected_items,'priority':i.priority,'enabled':i.enabled} for i in items]
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
def delete_service(service_id:int,actor:Admin=Depends(require_sudo),db:Session=Depends(get_db)):
 s=db.get(Service,service_id)
 if not s: raise HTTPException(404,detail={'detail':'سرویس پیدا نشد','code':'SERVICE_NOT_FOUND'})
 if db.query(__import__('app.db.models',fromlist=['User']).User).filter_by(service_id=service_id).first(): raise HTTPException(409,detail={'detail':'ابتدا کاربران این سرویس را منتقل یا حذف کنید','code':'SERVICE_IN_USE'})
 db.query(ServiceItem).filter_by(service_id=service_id).delete()
 db.add(AuditLog(actor_admin_id=actor.id,action='service.delete',object_type='service',object_id=str(s.id),details={})); db.delete(s); db.commit(); return {'ok':True}
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
