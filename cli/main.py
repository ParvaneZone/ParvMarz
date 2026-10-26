import typer
from sqlalchemy.orm import Session
from app.db.session import Base, engine, SessionLocal
from app.db.models import Admin
from app.core.security import hash_password

app = typer.Typer(help="SubHub administration CLI")

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
