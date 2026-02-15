from typing import List, Union
from pydantic import AnyHttpUrl, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=True)

    PROJECT_NAME: str = "Trading Assistant"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str
    
    # Security
    SECRET_KEY: str # Used for JWT signing
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Cookies
    REFRESH_COOKIE_NAME: str = "ta_refresh"
    CSRF_COOKIE_NAME: str = "ta_csrf"
    COOKIE_SECURE: bool = False # Set True in prod
    COOKIE_SAMESITE: str = "lax" # Strict preferred, but Lax is easier for dev
    
    # CORS
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = []

    # Bootstrap Admin
    BOOTSTRAP_ADMIN_EMAIL: str = "admin@example.com"
    BOOTSTRAP_ADMIN_PASSWORD: str = "admin123" # Change in .env!
    BOOTSTRAP_ADMIN_ENABLED: bool = True

settings = Settings()
