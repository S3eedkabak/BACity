"""
Centralized application configuration, loaded from environment variables
(see .env.example at the repo root).
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator, Field
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database - defaults to a local SQLite file so pytest/local dev work
    # without Postgres. Docker Compose overrides this in the full stack.
    database_url: str = "sqlite:///./dev.db"

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    environment: Literal["development", "staging", "production"] = "development"
    ingestion_api_key: str = ""
    public_app_url: str = "http://localhost:8081"

    # Browser OAuth. The callback URL is registered with Google/Apple; the
    # app redirect is the Expo/React Native deep link receiving a short-lived
    # exchange code. Providers stay disabled until their credentials exist.
    oauth_callback_base_url: str = "http://localhost:8000"
    oauth_app_redirect_uri: str = "bratislava-events://oauth"
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    apple_oauth_client_id: str = ""
    apple_team_id: str = ""
    apple_key_id: str = ""
    apple_private_key: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    mail_from: str = "noreply@example.com"
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_pro_price_id: str = ""
    stripe_business_price_id: str = ""
    message_retention_days: int = Field(90, ge=1, le=3650)
    utility_sync_enabled: bool = False
    utility_sync_interval_hours: int = Field(24, ge=1, le=168)
    media_root: str = "./media"

    # CORS
    cors_origins: str = "http://localhost:8081,http://localhost:19006"

    # Misc
    default_city: str = "Bratislava"
    default_timezone: str = "Europe/Bratislava"

    @model_validator(mode="after")
    def deployment_secrets(self):
        if self.environment != "development":
            if len(self.jwt_secret) < 32 or self.jwt_secret == "change-me-in-production":
                raise ValueError("Set a random JWT_SECRET of at least 32 characters")
            if len(self.ingestion_api_key) < 32 or "replace-with" in self.ingestion_api_key:
                raise ValueError("Set a random INGESTION_API_KEY of at least 32 characters")
            if not self.database_url.startswith("postgresql"):
                raise ValueError("Staging and production require PostgreSQL")
            if not self.public_app_url.startswith("https://") or any(
                not origin.startswith("https://") for origin in self.cors_origin_list
            ):
                raise ValueError("Staging and production require HTTPS application and CORS origins")
            if self.environment == "production" and (
                not self.smtp_host
                or self.mail_from.endswith("@example.com")
                or self.mail_from.endswith(".example")
            ):
                raise ValueError("Production requires SMTP_HOST and a non-example MAIL_FROM")

            google_parts = [self.google_oauth_client_id, self.google_oauth_client_secret]
            if any(google_parts) and not all(google_parts):
                raise ValueError("Google OAuth requires both client ID and client secret")

            apple_parts = [
                self.apple_oauth_client_id,
                self.apple_team_id,
                self.apple_key_id,
                self.apple_private_key,
            ]
            if any(apple_parts) and not all(apple_parts):
                raise ValueError("Apple OAuth requires client ID, team ID, key ID and private key")
            if any(apple_parts) and not self.oauth_callback_base_url.startswith("https://"):
                raise ValueError("Apple OAuth requires an HTTPS OAUTH_CALLBACK_BASE_URL")
            if self.environment == "production":
                if not all(google_parts) or not all(apple_parts):
                    raise ValueError("Production requires Google and Apple OAuth credentials")
                if not self.oauth_callback_base_url.startswith("https://"):
                    raise ValueError("Production OAuth callbacks require HTTPS")
        if self.smtp_ssl and self.smtp_starttls:
            raise ValueError("Choose either SMTP_SSL or SMTP_STARTTLS, not both")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def google_oauth_configured(self) -> bool:
        return bool(self.google_oauth_client_id and self.google_oauth_client_secret)

    @property
    def apple_oauth_configured(self) -> bool:
        return bool(
            self.apple_oauth_client_id
            and self.apple_team_id
            and self.apple_key_id
            and self.apple_private_key
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
