from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    cookie_secure: bool = True
    cookie_samesite: str = "Strict"
    refresh_cookie_name: str = "ta_refresh"
    csrf_cookie_name: str = "ta_csrf"

    bootstrap_admin_email: str | None = None
    bootstrap_admin_password: str | None = None
    bootstrap_admin_enabled: bool = True

    api_v1_str: str = "/api/v1"
    project_name: str = "Trading Assistant"
    cors_origins: list[str] = []

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"

    # ── Market Data ────────────────────────────────────────────────────────────
    marketdata_provider: str = "mock"  # mock, yahoo, alphavantage
    marketdata_api_key: str | None = None

    # ── Data Quality (DQ) ──────────────────────────────────────────────────────
    dq_stale_max_minutes_intraday: int = 30
    dq_stale_max_days_close: int = 3
    dq_jump_threshold_pct: float = 10.0
    dq_require_close: bool = True
    dq_fx_stale_max_days: int = 3

    # ── Mock Provider Anomaly Injection (for testing) ───────────────────────────
    mock_stale_prices: bool = False
    mock_jump_prices: bool = False
    mock_scale_mismatch: bool = False

    # ── Venue Configuration ────────────────────────────────────────────────────
    venue_lse_tz: str = "Europe/London"
    venue_lse_close_time: str = "16:30"
    venue_nyse_tz: str = "America/New_York"
    venue_nyse_close_time: str = "16:00"

    # ── Scheduler ───────────────────────────────────────────────────────────────
    scheduler_api_base_url: str = "http://localhost:8000"
    scheduler_interval_minutes: int = 5
    scheduler_auth_email: str | None = None
    scheduler_auth_password: str | None = None
    @field_validator("cookie_samesite")
    @classmethod
    def validate_cookie_samesite(cls, value: str) -> str:
        normalized = value.capitalize()
        if normalized not in {"Strict", "Lax", "None"}:
            raise ValueError("cookie_samesite must be one of: Strict, Lax, None")
        return normalized

    @property
    def SCHEDULER_API_BASE_URL(self) -> str:
        return self.scheduler_api_base_url

    @property
    def SCHEDULER_INTERVAL_MINUTES(self) -> int:
        return self.scheduler_interval_minutes

    @property
    def SCHEDULER_AUTH_EMAIL(self) -> str | None:
        return self.scheduler_auth_email

    @property
    def SCHEDULER_AUTH_PASSWORD(self) -> str | None:
        return self.scheduler_auth_password

    @property
    def DATABASE_URL(self) -> str:
        return self.database_url

    @property
    def JWT_SECRET_KEY(self) -> str:
        return self.jwt_secret_key

    @property
    def JWT_ALGORITHM(self) -> str:
        return self.jwt_algorithm

    @property
    def ACCESS_TOKEN_EXPIRE_MINUTES(self) -> int:
        return self.access_token_expire_minutes

    @property
    def REFRESH_TOKEN_EXPIRE_DAYS(self) -> int:
        return self.refresh_token_expire_days

    @property
    def COOKIE_SECURE(self) -> bool:
        return self.cookie_secure

    @property
    def COOKIE_SAMESITE(self) -> str:
        return self.cookie_samesite

    @property
    def REFRESH_COOKIE_NAME(self) -> str:
        return self.refresh_cookie_name

    @property
    def CSRF_COOKIE_NAME(self) -> str:
        return self.csrf_cookie_name

    @property
    def BOOTSTRAP_ADMIN_EMAIL(self) -> str | None:
        return self.bootstrap_admin_email

    @property
    def BOOTSTRAP_ADMIN_PASSWORD(self) -> str | None:
        return self.bootstrap_admin_password

    @property
    def BOOTSTRAP_ADMIN_ENABLED(self) -> bool:
        return self.bootstrap_admin_enabled

    @property
    def API_V1_STR(self) -> str:
        return self.api_v1_str

    @property
    def PROJECT_NAME(self) -> str:
        return self.project_name

    @property
    def BACKEND_CORS_ORIGINS(self) -> list[str]:
        return self.cors_origins


@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
