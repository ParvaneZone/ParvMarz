"""Initial schema generated from ORM metadata."""
from alembic import op
from app.db.session import Base
from app.db import models  # noqa: F401
revision='0001_initial'; down_revision=None; branch_labels=None; depends_on=None
def upgrade():
    # Keep the initial revision stable when later models are added.
    tables = [table for table in Base.metadata.sorted_tables if table.name != "admin_panel_access"]
    Base.metadata.create_all(bind=op.get_bind(), tables=tables)

def downgrade():
    tables = [table for table in reversed(Base.metadata.sorted_tables) if table.name != "admin_panel_access"]
    Base.metadata.drop_all(bind=op.get_bind(), tables=tables)
