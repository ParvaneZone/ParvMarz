"""Inbound display names."""
from alembic import op
import sqlalchemy as sa

revision = "0004_inbound_alias"
down_revision = "0003_admin_2fa_prefs"
branch_labels = None
depends_on = None


def upgrade():
    if "inbound_aliases" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "inbound_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("panel_id", sa.Integer(), sa.ForeignKey("panels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tag", sa.String(length=180), nullable=False),
        sa.Column("display_name", sa.String(length=180), nullable=False),
        sa.UniqueConstraint("panel_id", "tag", name="uq_inbound_alias"),
    )
    op.create_index("ix_inbound_aliases_panel_id", "inbound_aliases", ["panel_id"])


def downgrade():
    op.drop_index("ix_inbound_aliases_panel_id", table_name="inbound_aliases")
    op.drop_table("inbound_aliases")
