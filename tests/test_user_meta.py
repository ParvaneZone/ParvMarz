from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.session import Base
from app.db import models
from app.routers.user_meta import users_online


def test_users_online_is_scoped_to_the_admin():
    eng = create_engine("sqlite://", future=True)
    Base.metadata.create_all(eng)
    db = sessionmaker(bind=eng)()
    db.add_all([models.Admin(id=1, username="s", password_hash="x", role="sudo"), models.Admin(id=2, username="a", password_hash="x"),
                models.Service(id=1, name="svc", display_name="Svc")])
    db.flush()
    seen = datetime(2026, 10, 1, tzinfo=timezone.utc)
    db.add_all([models.User(id=1, username="u1", admin_id=1, service_id=1, online_at=seen),
                models.User(id=2, username="u2", admin_id=2, service_id=1)])
    db.commit()
    assert set(users_online(db.get(models.Admin, 1), db)["items"]) == {"1", "2"}
    assert users_online(db.get(models.Admin, 2), db)["items"] == {"2": None}
