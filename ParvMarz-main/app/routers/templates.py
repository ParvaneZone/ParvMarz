from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.security import current_admin, require_sudo
from app.core.permissions import has_perm
from app.db.models import Admin, UserTemplate, Service
from app.db.session import get_db
from app.schemas import TemplateOut, errs
router=APIRouter(prefix='/api/templates',tags=['templates'])
class TemplateIn(BaseModel):
 name:str=Field(min_length=1,max_length=120); service_id:int; data_limit:int|None=None; duration:int|None=30; username_prefix:str=''; username_suffix:str=''; reset_strategy:str='no_reset'; add_remaining_traffic:bool=False
@router.get('',response_model=list[TemplateOut],summary='لیست قالب‌های کاربر',description='نیازمند دسترسی templates.view.',responses=errs(401,403))
def list_templates(admin:Admin=Depends(current_admin),db:Session=Depends(get_db)):
 if not has_perm(admin,'templates.view'): raise HTTPException(403,detail={'detail':'این دسترسی برای شما فعال نیست','code':'PERMISSION_DENIED'})
 q=db.query(UserTemplate)
 if admin.role!='sudo': q=q.filter(UserTemplate.service_id.in_(admin.allowed_services or []))
 return [{'id':t.id,'name':t.name,'service_id':t.service_id,'data_limit':t.data_limit,'duration':t.duration,'username_prefix':t.username_prefix,'username_suffix':t.username_suffix,'reset_strategy':t.reset_strategy,'add_remaining_traffic':t.add_remaining_traffic} for t in q.all()]
@router.post('')
def create_template(body:TemplateIn,admin:Admin=Depends(require_sudo),db:Session=Depends(get_db)):
 if not db.get(Service,body.service_id): raise HTTPException(404,detail={'detail':'سرویس پیدا نشد','code':'SERVICE_NOT_FOUND'})
 t=UserTemplate(**body.model_dump()); db.add(t); db.commit(); db.refresh(t); return {'id':t.id}
@router.put('/{template_id}')
def update_template(template_id:int,body:TemplateIn,admin:Admin=Depends(require_sudo),db:Session=Depends(get_db)):
 t=db.get(UserTemplate,template_id)
 if not t: raise HTTPException(404,detail={'detail':'قالب پیدا نشد','code':'TEMPLATE_NOT_FOUND'})
 for k,v in body.model_dump().items(): setattr(t,k,v)
 db.commit(); return {'ok':True}
@router.delete('/{template_id}')
def delete_template(template_id:int,admin:Admin=Depends(require_sudo),db:Session=Depends(get_db)):
 t=db.get(UserTemplate,template_id)
 if not t: raise HTTPException(404,detail={'detail':'قالب پیدا نشد','code':'TEMPLATE_NOT_FOUND'})
 db.delete(t); db.commit(); return {'ok':True}
