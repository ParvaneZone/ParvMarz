try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
except ImportError:  # Allows static/unit testing before optional runtime dependencies are installed.
    AsyncIOScheduler = None
from app.config import settings
from app.jobs.outbox import drain_outbox
from app.jobs.usage_sync import sync_usage
from app.jobs.reconcile import reconcile
from app.jobs.reset_usage import reset_usage_job
from app.jobs.health_check import check_panels
from app.jobs.backup import backup_database

scheduler=AsyncIOScheduler(timezone='UTC') if AsyncIOScheduler else None
async def _outbox(): await drain_outbox()
async def _usage(): await sync_usage()
def _reconcile(): reconcile()
def _reset(): reset_usage_job()
async def _health(): await check_panels()
def _backup():
    try: backup_database("./data/backups", keep=7)
    except Exception: pass
def start_scheduler():
 if scheduler is None:
  import logging
  logging.getLogger(__name__).warning("APScheduler is not installed; background jobs are disabled")
  return
 if scheduler.running: return
 scheduler.add_job(_outbox,'interval',seconds=10,id='outbox',replace_existing=True,max_instances=1)
 scheduler.add_job(_usage,'interval',seconds=max(30,settings.sync_interval_seconds),id='usage',replace_existing=True,max_instances=1)
 scheduler.add_job(_reconcile,'interval',minutes=5,id='reconcile',replace_existing=True,max_instances=1)
 scheduler.add_job(_reset,'interval',minutes=5,id='reset',replace_existing=True,max_instances=1)
 scheduler.add_job(_health,'interval',minutes=2,id='health',replace_existing=True,max_instances=1)
 scheduler.add_job(_backup,'interval',hours=24,id='backup',replace_existing=True,max_instances=1)
 scheduler.start()
def stop_scheduler():
 if scheduler is not None and scheduler.running: scheduler.shutdown(wait=False)
