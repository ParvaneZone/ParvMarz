from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.core.security import require_sudo
from app.db.models import Admin, InboundAlias, Panel, PanelInbound, AuditLog, UserPanelAccount
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
    hosts: dict = {}
    for h in db.query(PanelInbound).filter_by(kind="host").all():
        hosts.setdefault((h.panel_id, h.tag), []).append({"remark": h.remark, "address": (h.extra or {}).get("address", "")})
    rows = db.query(PanelInbound).filter_by(kind="inbound").order_by(PanelInbound.panel_id, PanelInbound.id).all()
    return [{"panel_id": x.panel_id, "panel_name": panels.get(x.panel_id), "tag": x.tag, "protocol": x.protocol,
             "network": x.network, "security": x.security, "remark": x.remark,
             "display_name": aliases.get((x.panel_id, x.tag), ""),
             "hosts": hosts.get((x.panel_id, x.tag), [])} for x in rows if x.tag]


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


class ConfigNameIn(BaseModel):
    panel_id: int
    name: str = Field(min_length=1, max_length=170)
    display_name: str = Field(default="", max_length=180)


@router.get("/configs")
async def list_configs(_: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    """The config names users actually see (taken from a real user's subscription links per panel)."""
    import asyncio
    from app.drivers.factory import build_driver
    from app.routers.panels import _credentials
    from app.subscription.merge import parse_link
    names = {(a.panel_id, a.tag[4:]): a.display_name for a in db.query(InboundAlias).filter(InboundAlias.tag.like("cfg:%")).all()}
    jobs = []
    for p in db.query(Panel).filter_by(enabled=True).order_by(Panel.id).all():
        accs = db.query(UserPanelAccount).filter_by(panel_id=p.id).order_by(UserPanelAccount.id.desc()).limit(3).all()
        jobs.append((p.id, p.name, [a.remote_username for a in accs], p.type, p.base_url, _credentials(p), p.verify_ssl))

    async def one(job):
        pid, pname, users, ptype, url, cred, ssl = job
        seen, rows, note = set(), [], ""
        if not users:
            return [], f"{pname}: کاربری روی این پنل ندارید؛ یک کاربر بسازید"
        try:
            driver = build_driver(ptype, url, cred, ssl)
            for u in users:
                for link in await asyncio.wait_for(driver.get_sub_links(u), timeout=10):
                    x = parse_link(link)
                    if not x or not x.get("name") or x["name"] in seen:
                        continue
                    seen.add(x["name"])
                    rows.append({"panel_id": pid, "panel_name": pname, "name": x["name"], "server": x.get("server", ""),
                                 "port": x.get("port", ""), "type": x.get("type", ""), "network": x.get("network", ""),
                                 "display_name": names.get((pid, x["name"]), "")})
        except Exception as exc:
            note = f"{pname}: {str(exc)[:120]}"
        return rows, note

    res = await asyncio.gather(*(one(j) for j in jobs))
    return {"items": [r for rows, _ in res for r in rows], "notes": [n for _, n in res if n]}


@router.put("/config")
def set_config_name(body: ConfigNameIn, actor: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    tag = f"cfg:{body.name}"[:180]
    row = db.query(InboundAlias).filter_by(panel_id=body.panel_id, tag=tag).first()
    name = body.display_name.strip()
    if not name:
        if row: db.delete(row)
    elif row: row.display_name = name
    else: db.add(InboundAlias(panel_id=body.panel_id, tag=tag, display_name=name))
    db.add(AuditLog(actor_admin_id=actor.id, action="config.rename", object_type="config",
                    object_id=f"{body.panel_id}:{body.name}", details={"name": name}))
    db.commit()
    return {"ok": True}
