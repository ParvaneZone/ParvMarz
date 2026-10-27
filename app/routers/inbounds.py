from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.security import require_sudo
from app.db.models import Admin, InboundAlias, Panel, PanelInbound, AuditLog
from app.db.session import get_db

router = APIRouter(prefix="/api/inbounds", tags=["inbounds"])


class AliasIn(BaseModel):
    panel_id: int
    tag: str = Field(min_length=1, max_length=180)
    display_name: str = Field(default="", max_length=180)


@router.get("")
def list_inbounds(_: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    aliases = {(a.panel_id, a.tag): a.display_name for a in db.query(InboundAlias).all()}
    panels = {p.id: p.name for p in db.query(Panel).all()}
    rows = db.query(PanelInbound).filter_by(kind="inbound").order_by(PanelInbound.panel_id, PanelInbound.id).all()
    return [{"panel_id": x.panel_id, "panel_name": panels.get(x.panel_id), "tag": x.tag, "protocol": x.protocol,
             "network": x.network, "security": x.security, "remark": x.remark,
             "display_name": aliases.get((x.panel_id, x.tag), "")} for x in rows if x.tag]


@router.put("")
def set_alias(body: AliasIn, actor: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    if not db.query(PanelInbound).filter_by(panel_id=body.panel_id, tag=body.tag, kind="inbound").first():
        raise HTTPException(404, detail={"detail": "اینباند پیدا نشد", "code": "INBOUND_NOT_FOUND"})
    row = db.query(InboundAlias).filter_by(panel_id=body.panel_id, tag=body.tag).first()
    name = body.display_name.strip()
    if not name:
        if row: db.delete(row)
    elif row: row.display_name = name
    else: db.add(InboundAlias(panel_id=body.panel_id, tag=body.tag, display_name=name))
    db.add(AuditLog(actor_admin_id=actor.id, action="inbound.alias", object_type="inbound",
                    object_id=f"{body.panel_id}:{body.tag}", details={"name": name}))
    db.commit()
    return {"ok": True}
