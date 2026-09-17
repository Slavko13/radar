from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Telegram Lead Radar"
    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///./lead_radar.db"
    app_secret_key: str = "development-only-change-me"
    admin_password: str | None = "admin-change-me"
    admin_password_hash: str | None = None
    auth_token_ttl_hours: int = Field(default=12, ge=1, le=168)
    secure_cookies: bool | None = None
    app_timezone: str = "Europe/Moscow"
    telegram_api_id: int | None = None
    telegram_api_hash: str | None = None
    telegram_session_dir: str = "./data/sessions"
    telegram_bot_token: str | None = None
    telegram_notification_chat_id: str | None = None
    ai_provider: str = "mock"
    ai_api_key: str | None = None
    ai_model: str | None = None
    ai_base_url: str = "https://api.openai.com/v1"
    ai_timeout_seconds: float = Field(default=30, gt=0, le=180)
    lead_score_threshold: int = Field(default=70, ge=0, le=100)
    cors_origins: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_api_id and self.telegram_api_hash)

    @property
    def notification_configured(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_notification_chat_id)

    @property
    def ai_configured(self) -> bool:
        return self.ai_provider == "mock" or bool(self.ai_api_key and self.ai_model)

    @property
    def is_production(self) -> bool:
        return self.environment.casefold() == "production"

    @property
    def secure_cookie_enabled(self) -> bool:
        return self.is_production if self.secure_cookies is None else self.secure_cookies

    def validate_security(self) -> None:
        if self.is_production:
            if len(self.app_secret_key) < 32 or self.app_secret_key == "development-only-change-me":
                raise ValueError("Production APP_SECRET_KEY must contain at least 32 characters")
            if not self.admin_password_hash:
                raise ValueError("ADMIN_PASSWORD_HASH is required in production")


@lru_cache
def get_settings() -> Settings:
    return Settings()
