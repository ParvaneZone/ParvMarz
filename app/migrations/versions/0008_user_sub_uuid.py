"""Per-user random UUID used as the subscription link path."""
import uuid
from alembic import op
import sqlalchemy as sa

revision = "0008_user_sub_uuid"
down_revision = "0007_inbound_mode_geo"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "sub_uuid" not in {c["name"] for c in insp.get_columns("users")}:
        op.add_column("users", sa.Column("sub_uuid", sa.String(36), nullable=True))
    users = sa.table("users", sa.column("id", sa.Integer), sa.column("sub_uuid", sa.String))
    for (uid,) in bind.execute(sa.select(users.c.id).where(users.c.sub_uuid.is_(None))).fetchall():
        bind.execute(users.update().where(users.c.id == uid).values(sub_uuid=str(uuid.uuid4())))
    if "ix_users_sub_uuid" not in {i["name"] for i in sa.inspect(bind).get_indexes("users")}:
        op.create_index("ix_users_sub_uuid", "users", ["sub_uuid"], unique=True)


def downgrade():
    op.drop_index("ix_users_sub_uuid", table_name="users")
    op.drop_column("users", "sub_uuid")
