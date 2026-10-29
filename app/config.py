from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator


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
    login_rate_limit_enabled: bool = True
    login_max_attempts: int = 5
    login_lock_seconds: int = 900

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

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
