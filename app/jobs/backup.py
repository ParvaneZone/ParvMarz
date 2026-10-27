from pathlib import Path
from datetime import datetime, timezone
import shutil
from app.config import settings

def backup_database(directory:str='./backups',keep:int=7)->dict:
 if not settings.database_url.startswith('sqlite:///'):
  raise RuntimeError('Automatic backup currently supports SQLite only; use database-native dump for other engines')
 source=Path(settings.database_url.removeprefix('sqlite:///'))
 if not source.exists(): raise FileNotFoundError('Database file does not exist yet')
 destdir=Path(directory); destdir.mkdir(parents=True,exist_ok=True)
 dest=destdir/f"subhub-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.db"; shutil.copy2(source,dest)
 backups=sorted(destdir.glob('subhub-*.db'),key=lambda p:p.stat().st_mtime,reverse=True)
 for old in backups[keep:]: old.unlink()
 return {'path':str(dest),'retained':min(len(backups),keep)}
