from datetime import datetime, timezone
from app.core.crypto import decrypt_secret
from app.db.models import Panel
from app.db.session import SessionLocal
from app.drivers.factory import build_driver
import asyncio

async def check_panels()->dict:
 with SessionLocal() as db:
  panels=[(p.id,p.type,p.base_url,p.credentials_enc,p.verify_ssl) for p in db.query(Panel).filter_by(enabled=True).all()]
 async def check(row):
  pid,ptype,url,enc,ssl=row
  try:
   username,_,password=decrypt_secret(enc).partition('\n')
   await asyncio.wait_for(build_driver(ptype,url,{'username':username,'password':password},ssl).test_connection(),timeout=10)
   ok=True; err=None
  except Exception as exc: ok=False; err=type(exc).__name__
  with SessionLocal() as db:
   p=db.get(Panel,pid)
   if p:
    p.status='healthy' if ok else 'down'; p.last_error=err
    if ok: p.last_ok_at=datetime.now(timezone.utc)
    db.commit()
  return ok
 results=await asyncio.gather(*(check(p) for p in panels))
 return {'checked':len(results),'healthy':sum(results),'down':len(results)-sum(results)}
