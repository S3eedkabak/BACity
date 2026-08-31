"""
Centralized application configuration, loaded from environment variables
(see .env.example at the repo root). Kept deliberately small for the MVP —
see docs/architecture.md for what each setting maps to in the spec.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # CORS
    cors_origins: str = "http://localhost:8081,http://localhost:19006"

    # Misc
    default_city: str = "Bratislava"
    default_timezone: str = "Europe/Bratislava"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
