"""
Centralized application configuration, loaded from environment variables
(see .env.example at the repo root). Kept deliberately small for the MVP —
see docs/architecture.md for what each setting maps to in the spec.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator, Field
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database - defaults to a local SQLite file so `pytest` / local dev
    # work without Postgres running. Docker Compose overrides this with
    # the real Postgres+PostGIS DATABASE_URL.
    database_url: str = "sqlite:///./dev.db"

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    environment: Literal['development', 'staging', 'production'] = 'development'
    ingestion_api_key: str = ''
    public_app_url: str = 'http://localhost:8081'
    smtp_host: str = ''
    smtp_port: int = 587
    smtp_username: str = ''
    smtp_password: str = ''
    smtp_starttls: bool = True
    mail_from: str = 'noreply@example.com'
    stripe_secret_key: str = ''
    stripe_webhook_secret: str = ''
    stripe_pro_price_id: str = ''
    stripe_business_price_id: str = ''
    message_retention_days: int = Field(90, ge=1, le=3650)

    # CORS
    cors_origins: str = "http://localhost:8081,http://localhost:19006"

    # Misc
    default_city: str = "Bratislava"
    default_timezone: str = "Europe/Bratislava"

    @model_validator(mode='after')
    def deployment_secrets(self):
        if self.environment != 'development':
            if len(self.jwt_secret) < 32 or self.jwt_secret == 'change-me-in-production':
                raise ValueError('Set a random JWT_SECRET of at least 32 characters')
            if len(self.ingestion_api_key) < 32 or 'replace-with' in self.ingestion_api_key:
                raise ValueError('Set a random INGESTION_API_KEY of at least 32 characters')
            if not self.database_url.startswith('postgresql'):
                raise ValueError('Staging and production require PostgreSQL')
            if not self.public_app_url.startswith('https://') or any(not origin.startswith('https://') for origin in self.cors_origin_list):
                raise ValueError('Staging and production require HTTPS application and CORS origins')
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
