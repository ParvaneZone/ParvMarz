import typer
from app.db.session import Base, engine, SessionLocal
from app.db.models import Admin
from app.core.security import hash_password

app = typer.Typer(help="Jinx Data administration CLI")

@app.command()
def init_db():
    """Create database tables."""
    Base.metadata.create_all(bind=engine)
    typer.echo("Database initialized.")

@app.command()
def admin_create(username: str = typer.Option(..., prompt=True),
                 password: str = typer.Option(..., prompt=True, hide_input=True, confirmation_prompt=True)):
    """Create the first sudo administrator."""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.query(Admin).filter(Admin.username == username).first():
            raise typer.BadParameter("Username already exists")
        db.add(Admin(username=username, password_hash=hash_password(password), role="sudo",
                     permissions={"*": True}, allowed_services=[]))
        db.commit()
    typer.echo("Administrator created.")

@app.command()
def backup(directory: str = "./backups", keep: int = 7):
    """Create a rotating SQLite database backup."""
    from app.jobs.backup import backup_database
    typer.echo(backup_database(directory, keep))

@app.command()
def reconcile_users():
    """Queue reconciliation tasks for unsynced user accounts."""
    from app.jobs.reconcile import reconcile
    typer.echo(reconcile())


@app.command()
def reset_admin_password(username: str = typer.Option("", help="Admin username (default: first sudo admin)"),
                         password: str = typer.Option(..., prompt=True, hide_input=True, confirmation_prompt=True)):
    """Reset an administrator's password (re-enables the account, revokes old tokens)."""
    from datetime import datetime, timezone
    from sqlalchemy import func
    if len(password) < 12:
        raise typer.BadParameter("Password must be at least 12 characters")
    with SessionLocal() as db:
        q = db.query(Admin)
        admin = (q.filter(func.lower(Admin.username) == username.lower()).first() if username
                 else q.filter(Admin.role == "sudo").order_by(Admin.id).first())
        if not admin:
            raise typer.BadParameter("Admin not found")
        admin.password_hash = hash_password(password)
        admin.disabled = False
        admin.password_reset_at = datetime.now(timezone.utc)
        db.commit()
        typer.echo(f"Password reset for '{admin.username}'. Use `clear-login-lock` to clear login locks.")



@app.command()
def disable_2fa(username: str = typer.Option(..., help="Admin username")):
    """Turn off two-factor authentication for an admin (lost phone / lost recovery codes)."""
    from sqlalchemy import func
    with SessionLocal() as db:
        admin = db.query(Admin).filter(func.lower(Admin.username) == username.lower()).first()
        if not admin:
            raise typer.BadParameter("Admin not found")
        admin.totp_enabled = False
        admin.totp_secret_enc = None
        admin.totp_last_step = None
        admin.recovery_codes = []
        db.commit()
        typer.echo(f"2FA disabled for '{admin.username}'.")


@app.command()
def export_openapi(directory: str = "./openapi"):
    """Export private API docs offline: openapi.json (full), agent.json (agents only) and api-fa.md (agents, Persian)."""
    import json
    from pathlib import Path
    from app.core.apidocs import build_schema, to_markdown
    from app.main import app as fastapi_app
    out = Path(directory); out.mkdir(parents=True, exist_ok=True)
    (out / "openapi.json").write_text(json.dumps(build_schema(fastapi_app, False), ensure_ascii=False, indent=2), encoding="utf-8")
    agent = build_schema(fastapi_app, True)
    (out / "agent.json").write_text(json.dumps(agent, ensure_ascii=False, indent=2), encoding="utf-8")
    (out / "api-fa.md").write_text(to_markdown(agent), encoding="utf-8")
    typer.echo(f"Exported to {out}/ (openapi.json = sudo only; give agents agent.json / api-fa.md)")


@app.command()
def clear_login_lock():
    """Clear all login lockouts (failed-attempt counters are stored in the database)."""
    from app.db.models import Setting
    with SessionLocal() as db:
        n = db.query(Setting).filter(Setting.key.like("login:%")).delete(synchronize_session=False)
        db.commit()
        typer.echo(f"Cleared {n} login lock(s).")
