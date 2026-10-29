"""Usage attribution: admin/panel/service on usage_logs."""
from alembic import op
import sqlalchemy as sa

revision = "0005_usage_attribution"
down_revision = "0004_inbound_alias"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("usage_logs")}
    for name in ("admin_id", "panel_id", "service_id"):
        if name not in cols:
            op.add_column("usage_logs", sa.Column(name, sa.Integer(), nullable=True))
    existing = {i["name"] for i in sa.inspect(bind).get_indexes("usage_logs")}
    for name in ("admin_id", "panel_id", "service_id", "recorded_at"):
        ix = f"ix_usage_logs_{name}"
        if ix not in existing:
            op.create_index(ix, "usage_logs", [name])
    # Owner and service of existing users are exact. The node (panel) of old rows was never recorded
    # and cannot be reconstructed, so panel_id stays NULL ("unknown") for them.
    op.execute("UPDATE usage_logs SET admin_id=(SELECT u.admin_id FROM users u WHERE u.id=usage_logs.user_id), "
               "service_id=(SELECT u.service_id FROM users u WHERE u.id=usage_logs.user_id) WHERE admin_id IS NULL")


def downgrade():
    for name in ("recorded_at", "service_id", "panel_id", "admin_id"):
        op.drop_index(f"ix_usage_logs_{name}", table_name="usage_logs")
    with op.batch_alter_table("usage_logs") as b:
        for name in ("service_id", "panel_id", "admin_id"):
            b.drop_column(name)
