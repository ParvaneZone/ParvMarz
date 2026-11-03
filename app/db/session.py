from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import settings

if settings.database_url.startswith("sqlite:///"):
    db_path = settings.database_url.removeprefix("sqlite:///")
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, future=True, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

if settings.database_url.startswith("sqlite") and ":memory:" not in settings.database_url:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_conn, _):
        """WAL = fewer disk writes and readers never block the writer; small per-connection cache and capped WAL file keep RAM/disk flat."""
        cur = dbapi_conn.cursor()
        try:
            for p in ("journal_mode=WAL", "synchronous=NORMAL", "busy_timeout=10000", "cache_size=-2000",
                      "mmap_size=0", "journal_size_limit=16777216"):
                cur.execute("PRAGMA " + p)
        except Exception:
            pass
        finally:
            cur.close()


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
