"""Service inbound mode (all/rotate/random) + subscription access geo."""
from alembic import op
import sqlalchemy as sa

revision = "0007_inbound_mode_geo"
down_revision = "0006_api_keys"
branch_labels = None
depends_on = None


def upgrade():
    insp = sa.inspect(op.get_bind())
    cols = {c["name"] for c in insp.get_columns("services")}
    for name, typ, default in (("inbound_mode", sa.String(10), "all"), ("inbound_interval", sa.Integer(), "60"), ("inbound_count", sa.Integer(), "1")):
        if name not in cols:
            op.add_column("services", sa.Column(name, typ, nullable=False, server_default=default))
    if "sub_access" not in insp.get_table_names():
        op.create_table(
            "sub_access",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("ip", sa.String(64), nullable=False),
            sa.Column("inbounds", sa.JSON(), nullable=False),
            sa.Column("country", sa.String(80), nullable=False, server_default=""),
            sa.Column("region", sa.String(120), nullable=False, server_default=""),
            sa.Column("city", sa.String(120), nullable=False, server_default=""),
            sa.Column("isp", sa.String(160), nullable=False, server_default=""),
            sa.Column("hits", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
            sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("user_id", "ip", name="uq_sub_access_user_ip"),
        )
        op.create_index("ix_sub_access_user_id", "sub_access", ["user_id"])
        op.create_index("ix_sub_access_last_seen", "sub_access", ["last_seen"])


def downgrade():
    op.drop_table("sub_access")
    for name in ("inbound_count", "inbound_interval", "inbound_mode"):
        op.drop_column("services", name)
