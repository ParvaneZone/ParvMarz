from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator


class Settings(BaseSettings):
    app_name: str = "Jinx Data"
    environment: str = "development"
    database_url: str = "sqlite:///./data/subhub.db"
    jwt_secret: str = "development-only-change-me-32-characters"
    jwt_expire_minutes: int = 60
    subscription_hmac_key: str = "development-only-sub-key-change-me-32"
    credentials_encryption_key: str = ""
    public_base_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:5173"
    openapi_enabled: bool = False
    panel_allow_private_addresses: bool = True
    sync_interval_seconds: int = 60
    log_level: str = "INFO"
    initial_admin_username: str = ""
    initial_admin_password: str = ""
    telegram_bot_token: str = ""
    telegram_admin_chat_id: str = ""
    webhook_url: str = ""
    webhook_secret: str = ""
    expiry_warn_days: int = 3
    auto_delete_expired_days: int = 0  # 0 = off
    login_rate_limit_enabled: bool = True
    login_max_attempts: int = 5
    login_lock_seconds: int = 900
    # Separate listeners: when SUB_PORT is set the subscription page lives on its own port/app and the
    # panel app serves no /sub at all (so the sub page can never lead to the panel address).
    sub_port: int | None = None
    panel_listen_port: int = 8000
    sub_listen_port: int = 8001
    panel_domain: str = ""   # if set (and a certificate exists) the panel answers only on this host, over TLS
    sub_domain: str = ""
    sub_public_base_url: str = ""
    log_retention_days: int = 180  # usage/audit log pruning, 0 = keep forever

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def validate_production_secrets(self):
        if self.environment.lower() == "production":
            if len(self.jwt_secret) < 32 or self.jwt_secret.startswith(("development-only", "replace-with")):
                raise ValueError("JWT_SECRET must be a unique random secret of at least 32 characters in production")
            if len(self.subscription_hmac_key) < 32 or self.subscription_hmac_key.startswith("replace-with"):
                raise ValueError("SUBSCRIPTION_HMAC_KEY must be a unique random secret of at least 32 characters in production")
            if not self.credentials_encryption_key:
                raise ValueError("CREDENTIALS_ENCRYPTION_KEY is required in production")
            try:
                from cryptography.fernet import Fernet
                Fernet(self.credentials_encryption_key.encode())
            except Exception as exc:
                raise ValueError("CREDENTIALS_ENCRYPTION_KEY must be a valid Fernet key") from exc
        return self

    @field_validator("sub_port", mode="before")
    @classmethod
    def _empty_port(cls, v):
        return None if v in ("", None) else v

    @property
    def split_mode(self) -> bool:
        return self.sub_port is not None

    @property
    def sub_base_url(self) -> str:
        """Public base URL used in subscription links."""
        if not self.split_mode:
            return self.public_base_url.rstrip("/")
        if self.sub_public_base_url:
            return self.sub_public_base_url.rstrip("/")
        from urllib.parse import urlsplit
        u = urlsplit(self.public_base_url)
        host = self.sub_domain or u.hostname or "localhost"
        return f"{'https' if self.sub_domain else (u.scheme or 'http')}://{host}:{self.sub_port}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
