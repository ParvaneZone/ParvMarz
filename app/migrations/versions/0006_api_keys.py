"""API keys for bots."""
from alembic import op
import sqlalchemy as sa

revision = "0006_api_keys"
down_revision = "0005_usage_attribution"
branch_labels = None
depends_on = None


def upgrade():
    if "api_keys" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admin_id", sa.Integer(), sa.ForeignKey("admins.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expire", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_api_keys_admin_id", "api_keys", ["admin_id"])
    op.create_index("ix_api_keys_key_prefix", "api_keys", ["key_prefix"], unique=True)


def downgrade():
    op.drop_index("ix_api_keys_key_prefix", table_name="api_keys")
    op.drop_index("ix_api_keys_admin_id", table_name="api_keys")
    op.drop_table("api_keys")
