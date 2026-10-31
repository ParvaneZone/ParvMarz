"""Add encrypted per-admin upstream panel credentials."""
from alembic import op
import sqlalchemy as sa

revision = "0002_admin_panel_access"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "admin_panel_access",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admin_id", sa.Integer(), sa.ForeignKey("admins.id", ondelete="CASCADE"), nullable=False),
        sa.Column("panel_id", sa.Integer(), sa.ForeignKey("panels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("remote_username", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("credentials_enc", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("admin_id", "panel_id", name="uq_admin_panel_access"),
    )
    op.create_index("ix_admin_panel_access_admin_id", "admin_panel_access", ["admin_id"])
    op.create_index("ix_admin_panel_access_panel_id", "admin_panel_access", ["panel_id"])


def downgrade():
    op.drop_index("ix_admin_panel_access_panel_id", table_name="admin_panel_access")
    op.drop_index("ix_admin_panel_access_admin_id", table_name="admin_panel_access")
    op.drop_table("admin_panel_access")
