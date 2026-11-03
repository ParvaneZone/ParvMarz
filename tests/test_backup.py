import gzip
import os
import sqlite3
from pathlib import Path
from app.config import settings
from app.jobs import backup as bk


def test_parse_time():
    assert bk.parse_time("3:30") == "03:30" and bk.parse_time("۰۴:۰۵") == "04:05" and bk.parse_time("23.59") == "23:59"
    assert bk.parse_time("24:00") is None and bk.parse_time("3:75") is None and bk.parse_time("") is None and bk.parse_time(None) is None


def test_split_file(tmp_path):
    f = tmp_path / "x.gz"; data = bytes(range(256)) * 40
    f.write_bytes(data)
    assert bk.split_file(f, 20000, tmp_path) == [f]
    out = tmp_path / "p"; out.mkdir()
    parts = bk.split_file(f, 4000, out)
    assert len(parts) == 3 and parts[0].name == "x.gz.001"
    assert b"".join(p.read_bytes() for p in parts) == data
    e = tmp_path / "e.gz"; e.write_bytes(b"a" * 8000)
    assert len(bk.split_file(e, 4000, out)) == 2  # exact multiple: no empty trailing part


def test_backup_is_gzip_snapshot_and_rotates(tmp_path, monkeypatch):
    db = tmp_path / "a.db"; con = sqlite3.connect(db)
    con.execute("create table t(x)"); con.execute("insert into t values (42)"); con.commit(); con.close()
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db}")
    d = tmp_path / "b"; d.mkdir()
    for i, n in enumerate(("jinx-1.db", "parvmarz-2.db.gz", "jinx-3.db")):
        p = d / n; p.write_bytes(b"x"); os.utime(p, (1000 + i, 1000 + i))
    info = bk.backup_database(str(d), keep=2)
    names = sorted(p.name for p in d.iterdir())
    assert len(names) == 2 and info["retained"] == 2 and not any(n.startswith(".tmp") for n in names)
    out = tmp_path / "r.db"; out.write_bytes(gzip.decompress(Path(info["path"]).read_bytes()))
    assert sqlite3.connect(out).execute("select x from t").fetchone() == (42,)
