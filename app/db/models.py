from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, BigInteger, String, Text, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Admin(Base):
    __tablename__ = "admins"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="admin")
    permissions: Mapped[dict] = mapped_column(JSON, default=dict)
    max_users: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_total_traffic: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    max_user_traffic: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    max_user_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    allowed_services: Mapped[list] = mapped_column(JSON, default=list)
    expire: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    telegram_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    password_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    # Optional Google-Authenticator-style TOTP (RFC 6238). Secret is Fernet-encrypted.
    totp_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    totp_last_step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recovery_codes: Mapped[list | None] = mapped_column(JSON, nullable=True)  # HMAC hashes only
    # Per-admin dashboard preferences (language, theme, custom colors).
    ui_prefs: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Panel(Base):
    __tablename__ = "panels"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    type: Mapped[str] = mapped_column(String(32))
    base_url: Mapped[str] = mapped_column(String(500))
    credentials_enc: Mapped[str] = mapped_column(Text, default="")
    verify_ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    username_prefix: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(20), default="degraded")
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_interval: Mapped[int] = mapped_column(Integer, default=60)


class AdminPanelAccess(Base):
    """Encrypted, per-representative credentials for a least-privilege upstream account."""
    __tablename__ = "admin_panel_access"
    __table_args__ = (UniqueConstraint("admin_id", "panel_id", name="uq_admin_panel_access"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admins.id", ondelete="CASCADE"), index=True)
    panel_id: Mapped[int] = mapped_column(ForeignKey("panels.id", ondelete="CASCADE"), index=True)
    remote_username: Mapped[str] = mapped_column(String(120), default="")
    credentials_enc: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class PanelInbound(Base):
    __tablename__ = "panel_inbounds"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    panel_id: Mapped[int] = mapped_column(ForeignKey("panels.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    remote_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tag: Mapped[str | None] = mapped_column(String(180), nullable=True)
    protocol: Mapped[str | None] = mapped_column(String(80), nullable=True)
    network: Mapped[str | None] = mapped_column(String(80), nullable=True)
    security: Mapped[str | None] = mapped_column(String(80), nullable=True)
    remark: Mapped[str | None] = mapped_column(String(180), nullable=True)
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    # kind='group' rows are internal lookups (Rebecca service / PasarGuard group); extra holds their inbound tags.
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class InboundAlias(Base):
    """Display name for an upstream inbound; survives re-sync (keyed by panel + tag)."""
    __tablename__ = "inbound_aliases"
    __table_args__ = (UniqueConstraint("panel_id", "tag", name="uq_inbound_alias"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    panel_id: Mapped[int] = mapped_column(ForeignKey("panels.id", ondelete="CASCADE"), index=True)
    tag: Mapped[str] = mapped_column(String(180))
    display_name: Mapped[str] = mapped_column(String(180))


class Service(Base):
    __tablename__ = "services"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    sub_remark_template: Mapped[str] = mapped_column(String(200), default="{service} | {server}")


class ServiceItem(Base):
    __tablename__ = "service_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id", ondelete="CASCADE"), index=True)
    panel_id: Mapped[int] = mapped_column(ForeignKey("panels.id", ondelete="CASCADE"), index=True)
    selected_items: Mapped[list] = mapped_column(JSON, default=list)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("username", name="uq_users_username"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(120, collation="NOCASE"), index=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admins.id"), index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    data_limit: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    used_traffic: Mapped[int] = mapped_column(BigInteger, default=0)
    expire: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    on_hold_expire_duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    on_hold_timeout: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_limit_reset_strategy: Mapped[str] = mapped_column(String(20), default="no_reset")
    note: Mapped[str] = mapped_column(Text, default="")
    sub_token_version: Mapped[int] = mapped_column(Integer, default=1)
    sub_revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    online_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    next_plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class UserPanelAccount(Base):
    __tablename__ = "user_panel_accounts"
    __table_args__ = (UniqueConstraint("user_id", "panel_id", name="uq_user_panel"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    panel_id: Mapped[int] = mapped_column(ForeignKey("panels.id"), index=True)
    remote_username: Mapped[str] = mapped_column(String(180))
    last_remote_used_traffic: Mapped[int] = mapped_column(BigInteger, default=0)
    remote_status: Mapped[str] = mapped_column(String(20), default="unknown")
    sync_state: Mapped[str] = mapped_column(String(20), default="pending")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserTemplate(Base):
    __tablename__ = "user_templates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    data_limit: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    duration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    username_prefix: Mapped[str] = mapped_column(String(80), default="")
    username_suffix: Mapped[str] = mapped_column(String(80), default="")
    reset_strategy: Mapped[str] = mapped_column(String(20), default="no_reset")
    add_remaining_traffic: Mapped[bool] = mapped_column(Boolean, default=False)


class SyncTask(Base):
    __tablename__ = "sync_tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    panel_id: Mapped[int] = mapped_column(ForeignKey("panels.id"), index=True)
    action: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    state: Mapped[str] = mapped_column(String(20), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class UsageLog(Base):
    __tablename__ = "usage_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    delta: Mapped[int] = mapped_column(BigInteger)
    total_after: Mapped[int] = mapped_column(BigInteger)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    # Attribution snapshot taken when the traffic was recorded (no FK: history must survive deletions).
    admin_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    panel_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    service_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_admin_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    object_type: Mapped[str] = mapped_column(String(80))
    object_id: Mapped[str] = mapped_column(String(120))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)


class ApiKey(Base):
    """Long-lived bot credential of one (non-sudo) admin. Only an HMAC of the key is stored."""
    __tablename__ = "api_keys"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_id: Mapped[int] = mapped_column(ForeignKey("admins.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    key_prefix: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    key_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expire: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
