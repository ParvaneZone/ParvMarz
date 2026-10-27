from urllib.parse import urlparse
import ipaddress
import socket
from app.config import settings
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.orm import Session
from app.core.crypto import encrypt_secret, decrypt_secret
from app.core.security import require_sudo
from app.db.models import Admin, Panel
from app.db.session import get_db
from app.drivers.factory import build_driver

router = APIRouter(prefix="/api/panels", tags=["panels"])


class PanelInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    type: str
    base_url: HttpUrl
    username: str
    password: str
    verify_ssl: bool = True
    enabled: bool = True
    username_prefix: str = ""
    sync_interval: int = Field(default=60, ge=15, le=86400)



def _validate_panel_url(url: str) -> None:
    parsed=urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        raise HTTPException(422, detail={"detail": "آدرس پنل نامعتبر است", "code": "INVALID_PANEL_URL"})
    if not settings.panel_allow_private_addresses:
        host=parsed.hostname or ""
        if host.lower() in {"localhost", "localhost.localdomain"}:
            raise HTTPException(422, detail={"detail": "آدرس داخلی مجاز نیست", "code": "PRIVATE_PANEL_URL"})
        try:
            addrs=[ipaddress.ip_address(host)]
        except ValueError:
            try:
                infos=socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
                addrs=[ipaddress.ip_address(i[4][0].split("%")[0]) for i in infos]
            except (socket.gaierror, ValueError):
                addrs=[]
        if any(not a.is_global for a in addrs):
            raise HTTPException(422, detail={"detail": "آدرس داخلی مجاز نیست", "code": "PRIVATE_PANEL_URL"})

def _credentials(panel: Panel) -> dict:
    raw = decrypt_secret(panel.credentials_enc)
    username, _, password = raw.partition("\n")
    return {"username": username, "password": password}


@router.get("")
def list_panels(_: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    rows=[]
    for p in db.query(Panel).all():
        try:
            capabilities=build_driver(p.type,p.base_url,{},p.verify_ssl).capabilities
        except Exception:
            capabilities={}
        rows.append({"id": p.id, "name": p.name, "type": p.type, "base_url": p.base_url,
                     "enabled": p.enabled, "status": p.status, "last_ok_at": p.last_ok_at,
                     "last_error": p.last_error, "capabilities": capabilities})
    return rows


@router.post("")
def create_panel(body: PanelInput, _: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    if body.type not in {"marzban", "marzdar", "marzyar", "pasarguard", "rebecca"}:
        raise HTTPException(422, detail={"detail": "درایور این نوع پنل هنوز پیاده‌سازی نشده است", "code": "INVALID_PANEL_TYPE"})
    _validate_panel_url(str(body.base_url))
    try:
        encrypted = encrypt_secret(body.username + "\n" + body.password)
    except RuntimeError as exc:
        raise HTTPException(503, detail={"detail": str(exc), "code": "CRYPTO_NOT_CONFIGURED"}) from exc
    panel = Panel(name=body.name, type=body.type, base_url=str(body.base_url),
                  credentials_enc=encrypted, verify_ssl=body.verify_ssl, enabled=body.enabled,
                  username_prefix=body.username_prefix, sync_interval=body.sync_interval)
    db.add(panel)
    db.commit()
    db.refresh(panel)
    return {"id": panel.id, "name": panel.name, "status": panel.status}


@router.post("/{panel_id}/test")
async def test_panel(panel_id: int, _: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    panel = db.get(Panel, panel_id)
    if not panel:
        raise HTTPException(404, detail={"detail": "پنل پیدا نشد", "code": "PANEL_NOT_FOUND"})
    try:
        result = await build_driver(panel.type, panel.base_url, _credentials(panel), panel.verify_ssl).test_connection()
        panel.status, panel.last_error = "healthy", None
        from datetime import datetime, timezone
        panel.last_ok_at = datetime.now(timezone.utc)
        db.commit()
        return result
    except Exception as exc:
        panel.status, panel.last_error = "down", type(exc).__name__
        db.commit()
        raise HTTPException(502, detail={"detail": "اتصال به پنل ناموفق بود", "code": "PANEL_CONNECTION_FAILED"}) from exc


@router.delete("/{panel_id}")
def delete_panel(panel_id: int, _: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    panel = db.get(Panel, panel_id)
    if not panel:
        raise HTTPException(404, detail={"detail": "پنل پیدا نشد", "code": "PANEL_NOT_FOUND"})
    from app.db.models import ServiceItem, PanelInbound, UserPanelAccount, SyncTask, User
    accounts=db.query(UserPanelAccount).filter_by(panel_id=panel.id).all()
    for account in accounts:
        owner = db.get(User, account.user_id)
        db.add(SyncTask(user_id=None,panel_id=panel.id,action='delete',payload={'username':account.remote_username,'admin_id':owner.admin_id if owner else None}))
        db.delete(account)
    db.query(ServiceItem).filter_by(panel_id=panel.id).delete()
    db.query(PanelInbound).filter_by(panel_id=panel.id).delete()
    # Keep the panel row until queued remote deletion tasks finish; disable it to prevent new work.
    if accounts:
        panel.enabled=True
        panel.status='degraded'
        db.commit()
        return {"ok": True, "pending_remote_deletions": len(accounts), "note": "Panel retained and kept enabled until queued remote deletions finish"}
    db.delete(panel)
    db.commit()
    return {"ok": True}

@router.post('/{panel_id}/sync')
async def sync_panel(panel_id: int, _: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    """Pull the panel's INBOUNDS (what admins see and pick). Rebecca services / PasarGuard groups are
    never listed to admins; they are cached as hidden lookups only, because those panels refuse to
    create a user without one."""
    from datetime import datetime, timezone
    from app.core.access import tags_from_group
    from app.db.models import PanelInbound
    panel = db.get(Panel, panel_id)
    if not panel:
        raise HTTPException(404, detail={'detail': 'پنل پیدا نشد', 'code': 'PANEL_NOT_FOUND'})
    try:
        driver = build_driver(panel.type, panel.base_url, _credentials(panel), panel.verify_ssl)
        try:
            inbounds = await driver.list_inbounds()
        except NotImplementedError:
            inbounds = []
        if not inbounds:
            raise RuntimeError('Panel exposed no readable inbounds')
        groups = []
        if panel.type in ('rebecca', 'pasarguard'):
            try:
                groups = await driver.list_groups()
            except Exception:  # hidden helper data; inbound sync must still succeed
                groups = []
        db.query(PanelInbound).filter(PanelInbound.panel_id == panel.id).delete()
        now = datetime.now(timezone.utc)
        for item in inbounds:
            tag = item.get('tag') or item.get('remark') or item.get('name')
            db.add(PanelInbound(panel_id=panel.id, kind='inbound',
                remote_id=str(item.get('id')) if item.get('id') is not None else None,
                tag=tag, protocol=item.get('protocol'), network=item.get('network'), security=item.get('security'),
                remark=item.get('remark') or tag, cached_at=now))
        for item in groups:
            name = item.get('name') or item.get('display_name') or item.get('remark')
            db.add(PanelInbound(panel_id=panel.id, kind='group',
                remote_id=str(item.get('id')) if item.get('id') is not None else None,
                tag=name, remark=name, cached_at=now, extra={'inbound_tags': tags_from_group(item)}))
        panel.status='healthy'; panel.last_error=None; panel.last_ok_at=now; db.commit()
        return {'synced': len(inbounds), 'inbounds': inbounds}
    except Exception as exc:
        panel.status='down'; panel.last_error=type(exc).__name__; db.commit()
        raise HTTPException(502, detail={'detail': 'همگام‌سازی پنل ناموفق بود', 'code': 'PANEL_SYNC_FAILED'}) from exc

@router.get('/{panel_id}/inbounds')
def get_inbounds(panel_id: int, _: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    from app.db.models import PanelInbound
    if not db.get(Panel, panel_id):
        raise HTTPException(404, detail={'detail': 'پنل پیدا نشد', 'code': 'PANEL_NOT_FOUND'})
    # Only real inbounds are exposed; hidden group/service lookups (kind='group') are not listed.
    return [{'id':x.id,'kind':x.kind,'remote_id':x.remote_id,'tag':x.tag,'protocol':x.protocol,'network':x.network,'security':x.security,'remark':x.remark,'cached_at':x.cached_at} for x in db.query(PanelInbound).filter_by(panel_id=panel_id, kind='inbound').all()]


@router.put('/{panel_id}')
def update_panel(panel_id: int, body: PanelInput, _: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    panel = db.get(Panel, panel_id)
    if not panel:
        raise HTTPException(404, detail={'detail': 'پنل پیدا نشد', 'code': 'PANEL_NOT_FOUND'})
    if body.type not in {"marzban", "marzdar", "marzyar", "pasarguard", "rebecca"}:
        raise HTTPException(422, detail={'detail': 'نوع پنل نامعتبر است', 'code': 'INVALID_PANEL_TYPE'})
    _validate_panel_url(str(body.base_url))
    panel.name=body.name; panel.type=body.type; panel.base_url=str(body.base_url)
    panel.credentials_enc=encrypt_secret(body.username + "\n" + body.password)
    panel.verify_ssl=body.verify_ssl; panel.enabled=body.enabled; panel.username_prefix=body.username_prefix; panel.sync_interval=body.sync_interval
    db.commit(); return {'ok': True}


@router.get("/{panel_id}/capabilities")
def get_panel_capabilities(panel_id: int, _: Admin = Depends(require_sudo), db: Session = Depends(get_db)):
    panel = db.get(Panel, panel_id)
    if not panel:
        raise HTTPException(404, detail={"detail": "پنل پیدا نشد", "code": "PANEL_NOT_FOUND"})
    driver = build_driver(panel.type, panel.base_url, {}, panel.verify_ssl)
    return {"panel_id": panel.id, "panel_type": panel.type, "capabilities": driver.capabilities}
