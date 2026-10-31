"""Admin 2FA (TOTP) + UI preferences, and internal group metadata on panel_inbounds.

Idempotent: a fresh install creates these columns in 0001 (it builds tables from the
current ORM metadata), an upgraded install gets them here.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_admin_2fa_prefs"
down_revision = "0002_admin_panel_access"
branch_labels = None
depends_on = None


def _cols(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade():
    admin_cols = _cols("admins")
    for name, col in (
        ("totp_secret_enc", sa.Column("totp_secret_enc", sa.Text(), nullable=True)),
        ("totp_enabled", sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0"))),
        ("totp_last_step", sa.Column("totp_last_step", sa.Integer(), nullable=True)),
        ("recovery_codes", sa.Column("recovery_codes", sa.JSON(), nullable=True)),
        ("ui_prefs", sa.Column("ui_prefs", sa.JSON(), nullable=True)),
    ):
        if name not in admin_cols:
            op.add_column("admins", col)
    if "extra" not in _cols("panel_inbounds"):
        op.add_column("panel_inbounds", sa.Column("extra", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("panel_inbounds") as b:
        b.drop_column("extra")
    with op.batch_alter_table("admins") as b:
        for name in ("ui_prefs", "recovery_codes", "totp_last_step", "totp_enabled", "totp_secret_enc"):
            b.drop_column(name)
