import gzip
import logging
import re
import shutil
import sqlite3
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
import httpx
from app.config import settings
from app.db.models import Setting
from app.db.session import SessionLocal

log = logging.getLogger("jinxdata.backup")
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_TIME = re.compile(r"([01]?\d|2[0-3])[:.]([0-5]\d)")
_DIR = "./data/backups"


def parse_time(v) -> str | None:
    m = _TIME.fullmatch(str(v or "").strip().translate(_DIGITS))
    return f"{int(m[1]):02d}:{m[2]}" if m else None


def backup_database(directory: str = "./backups", keep: int = 7) -> dict:
    """Consistent SQLite snapshot (safe while the panel writes, also in WAL mode), gzipped; only the newest `keep` files stay."""
    if not settings.database_url.startswith("sqlite:///"):
        raise RuntimeError("Automatic backup currently supports SQLite only; use database-native dump for other engines")
    source = Path(settings.database_url.removeprefix("sqlite:///"))
    if not source.exists(): raise FileNotFoundError("Database file does not exist yet")
    destdir = Path(directory); destdir.mkdir(parents=True, exist_ok=True)
    for stale in destdir.glob(".tmp-*"): stale.unlink(missing_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tmp = destdir / f".tmp-{stamp}.db"; dest = destdir / f"parvmarz-{stamp}.db.gz"
    src = sqlite3.connect(str(source)); dst = sqlite3.connect(str(tmp))
    try: src.backup(dst)
    finally: dst.close(); src.close()
    try:
        with tmp.open("rb") as i, gzip.open(dest, "wb", compresslevel=6) as o: shutil.copyfileobj(i, o, 1 << 20)
    finally: tmp.unlink(missing_ok=True)
    files = sorted((p for p in destdir.iterdir() if p.is_file() and p.name.endswith((".db", ".db.gz")) and not p.name.startswith(".tmp-")),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    keep = max(1, keep)
    for old in files[keep:]: old.unlink(missing_ok=True)
    return {"path": str(dest), "retained": min(len(files), keep)}


def split_file(src: Path, part_bytes: int, outdir: Path) -> list[Path]:
    """Cut src into name.001, name.002 ... (streamed, 1 MB at a time). Small files are returned as they are."""
    if src.stat().st_size <= part_bytes: return [src]
    parts = []
    with src.open("rb") as f:
        i = 0
        while True:
            i += 1; p = outdir / f"{src.name}.{i:03d}"; written = 0
            with p.open("wb") as o:
                while written < part_bytes:
                    b = f.read(min(1 << 20, part_bytes - written))
                    if not b: break
                    o.write(b); written += len(b)
            if written == 0: p.unlink(); break
            parts.append(p)
            if written < part_bytes: break
    return parts


def send_backup(path: Path, chats: list[str]) -> int:
    """Upload the backup (in parts when bigger than BACKUP_PART_MB) to every chat. Returns how many chats got all parts."""
    if not settings.telegram_bot_token or not chats: return 0
    limit = max(1, min(49, settings.backup_part_mb)) * 1024 * 1024
    size = path.stat().st_size; bad: set[str] = set()
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendDocument"
    with tempfile.TemporaryDirectory(dir=path.parent) as tmp:
        parts = split_file(path, limit, Path(tmp)); n = len(parts)
        with httpx.Client(timeout=300) as c:
            for i, p in enumerate(parts, 1):
                cap = f"💾 {path.name}\n{size / 1048576:.1f} MB" + (f" · بخش {i}/{n}" if n > 1 else "")
                if n > 1 and i == n: cap += f"\nبازیابی: cat {path.name}.0* > {path.name}"
                for chat in chats:
                    if chat in bad: continue
                    try:
                        with p.open("rb") as fh:
                            r = c.post(url, data={"chat_id": chat, "caption": cap}, files={"document": (p.name, fh)})
                        if not r.json().get("ok"): bad.add(chat)
                    except Exception as exc:
                        log.warning("backup upload failed: %s", type(exc).__name__); bad.add(chat)
    return len(chats) - len(bad)


def _get(db, key: str, default):
    s = db.get(Setting, key); v = s.value if s else None
    return v.get("value", default) if isinstance(v, dict) else default


def _set(db, key: str, val) -> None:
    db.merge(Setting(key=key, value={"value": val}))


def _local_now() -> datetime:
    return datetime.now(timezone.utc) + timedelta(minutes=settings.tz_offset_minutes)


def load_cfg(db) -> dict:
    """Runtime config: stored settings (bot /backuptime, PUT /api/system/settings) override the .env defaults."""
    return {"enabled": bool(_get(db, "backup_enabled", settings.backup_enabled)),
            "time": parse_time(_get(db, "backup_time", settings.backup_time)) or parse_time(settings.backup_time) or "03:00",
            "telegram": bool(_get(db, "backup_telegram", settings.backup_send_telegram))}


def _sudo_chats() -> list[str]:
    from app.core.notify import _chat_ids
    return _chat_ids("backup.send", None)


def run_backup(send: bool = True) -> dict:
    info = backup_database(_DIR, keep=settings.backup_keep)
    if send and settings.telegram_bot_token:
        chats = _sudo_chats()
        if chats and send_backup(Path(info["path"]), chats) < len(chats):
            from app.core.notify import notify_event
            notify_event("backup.failed", {"error": "ارسال به تلگرام ناموفق بود"})
    return info


def backup_tick() -> None:
    """Runs every minute (cheap): does the daily backup once, the first minute at/after the configured local time."""
    with SessionLocal() as db:
        c = load_cfg(db)
        if not c["enabled"]: return
        h, m = map(int, c["time"].split(":")); now = _local_now()
        if (now.hour, now.minute) < (h, m): return
        day = now.strftime("%Y-%m-%d")
        if _get(db, "backup_last", "") == day: return
        _set(db, "backup_last", day); db.commit()
    try: run_backup(c["telegram"])
    except Exception as exc:
        from app.core.notify import notify_event
        notify_event("backup.failed", {"error": type(exc).__name__})


def _send_now(chat_id: str) -> None:
    from app.core.tgbot import send_text_sync
    try:
        info = backup_database(_DIR, keep=settings.backup_keep)
        if send_backup(Path(info["path"]), [chat_id]) < 1: send_text_sync(chat_id, "❌ ارسال پشتیبان ناموفق بود.")
    except Exception as exc:
        log.warning("manual backup failed: %s", type(exc).__name__)
        send_text_sync(chat_id, f"❌ تهیه پشتیبان ناموفق بود ({type(exc).__name__})")


def bot_command(cmd: str, arg: str, chat_id: str) -> str:
    """Main-admin Telegram commands: /backup (now) · /backuptime HH:MM · /backupon · /backupoff."""
    if cmd == "/backup":
        threading.Thread(target=_send_now, args=(chat_id,), daemon=True).start()
        return "⏳ در حال تهیه پشتیبان…"
    with SessionLocal() as db:
        if cmd == "/backuptime":
            t = parse_time(arg)
            if not t: return "فرمت درست: /backuptime 03:30 (ساعت ۲۴ساعته، به وقت محلی)"
            h, m = map(int, t.split(":")); now = _local_now()
            _set(db, "backup_time", t); _set(db, "backup_enabled", True)
            _set(db, "backup_last", now.strftime("%Y-%m-%d") if (now.hour, now.minute) >= (h, m) else "")  # passed today -> tomorrow
            db.commit()
            return f"✅ پشتیبان روزانه ساعت {t} ارسال می‌شود."
        on = cmd == "/backupon"; _set(db, "backup_enabled", on); db.commit(); t = load_cfg(db)["time"]
    return f"✅ پشتیبان روزانه فعال شد (ساعت {t})." if on else "⏸ پشتیبان روزانه غیرفعال شد."
