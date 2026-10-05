"""
Centralized application configuration, loaded from environment variables
(see .env.example at the repo root).
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator, Field
from typing import Literal


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    # Database - defaults to a local SQLite file so pytest/local dev work
    # without Postgres. Docker Compose overrides this in the full stack.
    database_url: str = "sqlite:///./dev.db"

    # Auth
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    access_token_expire_minutes: int = Field(60, ge=1, le=1440)
    environment: Literal["development", "staging", "production"] = "development"
    ingestion_api_key: str = ""
    public_app_url: str = "http://localhost:8081"
    account_action_base_url: str = ""
    # Owner-approved published documents/contact only; blank means not configured.
    privacy_contact_email: str = ""
    controller_legal_name: str = Field('', max_length=200)
    business_address: str = Field('', max_length=1000)
    support_contact_email: str = ''
    legal_contact_email: str = ''
    operations_contact_email: str = ''
    privacy_notice_url: str = ""
    privacy_notice_version: str = ""
    terms_url: str = ""
    terms_version: str = ""

    # Browser OAuth. The callback URL is registered with Google/Apple; the
    # app redirect is the Expo/React Native deep link receiving a short-lived
    # exchange code. Providers stay disabled until their credentials exist.
    oauth_callback_base_url: str = "http://localhost:8000"
    oauth_app_redirect_uri: str = "bratislava-events://oauth"
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_android_client_id: str = ""
    google_ios_client_id: str = ""
    apple_oauth_client_id: str = ""
    apple_ios_client_id: str = "com.bratislavaevents.app"
    apple_team_id: str = ""
    apple_key_id: str = ""
    apple_private_key: str = ""
    oauth_token_encryption_key: str = ""
    # JSON key-ID -> base64 AES-256 key; deployment secrets, never DB/mobile.
    private_data_keys: str = Field("", repr=False)
    private_data_active_key: str = ""

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True
    smtp_ssl: bool = False
    mail_from: str = "noreply@example.com"
    mail_from_name: str = "BACity"
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_pro_price_id: str = ""
    stripe_business_price_id: str = ""
    consumer_billing_enabled: bool = False
    stripe_consumer_secret_key: str = ""
    stripe_consumer_webhook_secret: str = ""
    stripe_consumer_plus_price_id: str = ""
    stripe_consumer_plus_product_id: str = ""
    stripe_consumer_success_url: str = "http://localhost:8081/plus?billing=success"
    stripe_consumer_cancel_url: str = "http://localhost:8081/plus?billing=cancelled"
    stripe_consumer_portal_return_url: str = "http://localhost:8081/plus"
    stripe_consumer_livemode: bool = False
    stripe_consumer_api_version: str = "2024-06-20"
    google_play_billing_enabled: bool = False
    google_play_package_name: str = ""
    google_play_subscription_product_id: str = ""
    google_play_base_plan_id: str = ""
    google_play_service_account_json: str = ""
    google_play_rtdn_audience: str = ""
    google_play_rtdn_service_account_email: str = ""
    enable_development_plus_grants: bool = False
    message_retention_days: int = Field(90, ge=1, le=3650)
    utility_sync_enabled: bool = False
    utility_sync_interval_hours: int = Field(24, ge=1, le=168)
    media_root: str = "./media"

    # CORS
    cors_origins: str = "http://localhost:8081,http://localhost:19006"
    trusted_hosts: str = ""

    # Misc
    default_city: str = "Bratislava"
    default_timezone: str = "Europe/Bratislava"

    @model_validator(mode="after")
    def deployment_secrets(self):
        from urllib.parse import urlsplit
        for contact in (self.privacy_contact_email, self.support_contact_email, self.legal_contact_email, self.operations_contact_email):
            if contact and ('@' not in contact or any(c in contact for c in '\r\n ?&')):
                raise ValueError('Contact must be a plain email address')
        for value in (self.privacy_notice_url, self.terms_url):
            if value:
                part = urlsplit(value)
                if part.scheme not in ('http', 'https') or not part.hostname or part.username or part.password or (self.environment != 'development' and part.scheme != 'https'):
                    raise ValueError('Policy URLs require public HTTPS outside development, without credentials')
        for origin in self.cors_origin_list:
            part = urlsplit(origin)
            if (part.scheme not in ('http', 'https') or not part.hostname or '*' in part.netloc
                    or part.username or part.password or part.path not in ('', '/') or part.query or part.fragment):
                raise ValueError("CORS origins must be explicit HTTP(S) origins without credentials or wildcards")
        if any('*' in host or '/' in host or ':' in host for host in self.trusted_host_list):
            raise ValueError("Trusted hosts must be explicit host names")
        if self.consumer_billing_enabled:
            required = (
                self.stripe_consumer_secret_key,
                self.stripe_consumer_webhook_secret,
                self.stripe_consumer_plus_price_id,
                self.stripe_consumer_success_url,
                self.stripe_consumer_cancel_url,
                self.stripe_consumer_portal_return_url,
            )
            if not all(required):
                raise ValueError("Consumer billing requires Stripe secret, webhook secret, price and return URLs")
            from urllib.parse import urlsplit
            allowed = {f"{part.scheme}://{part.netloc}" for value in [self.public_app_url, *self.cors_origin_list]
                       if (part := urlsplit(value)).scheme and part.netloc}
            for value in (self.stripe_consumer_success_url, self.stripe_consumer_cancel_url,
                          self.stripe_consumer_portal_return_url):
                part = urlsplit(value)
                if f"{part.scheme}://{part.netloc}" not in allowed:
                    raise ValueError("Consumer billing return URLs must use an allowlisted BACity origin")
            if self.environment == "production":
                if not self.stripe_consumer_livemode or not self.stripe_consumer_secret_key.startswith("sk_live_"):
                    raise ValueError("Production consumer billing requires Stripe live mode credentials")
                if any(not value.startswith("https://") for value in (
                    self.stripe_consumer_success_url, self.stripe_consumer_cancel_url,
                    self.stripe_consumer_portal_return_url,
                )):
                    raise ValueError("Production consumer billing return URLs require HTTPS")
        if self.environment != "development" and self.enable_development_plus_grants:
            raise ValueError("Development BACity+ grants must be disabled outside development")
        if self.private_data_keys:
            from app.core.encryption import keyring, EncryptionError
            try:
                keyring(self)
            except EncryptionError:
                raise ValueError('Invalid private-data encryption configuration') from None
        elif self.private_data_active_key or self.environment != 'development':
            raise ValueError('Configure PRIVATE_DATA_KEYS and PRIVATE_DATA_ACTIVE_KEY outside development')
        if self.google_play_billing_enabled:
            required = (
                self.google_play_package_name,
                self.google_play_subscription_product_id,
                self.google_play_service_account_json,
            )
            if not all(required):
                raise ValueError("Google Play billing requires package, subscription product and service account")
            import json
            try:
                credentials = json.loads(self.google_play_service_account_json)
            except (TypeError, ValueError):
                raise ValueError("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON must be valid JSON")
            if not isinstance(credentials, dict) or not all(credentials.get(key) for key in ("client_email", "private_key", "token_uri")):
                raise ValueError("Google Play service account JSON is incomplete")
            if credentials['token_uri'] not in ('https://oauth2.googleapis.com/token', 'https://accounts.google.com/o/oauth2/token'):
                raise ValueError("Google Play credentials require a Google HTTPS token endpoint")
            if bool(self.google_play_rtdn_audience) != bool(self.google_play_rtdn_service_account_email):
                raise ValueError("Google Play RTDN audience and service-account email must be configured together")
        if self.environment != "development":
            if not self.oauth_callback_base_url.startswith('https://'):
                raise ValueError('Staging and production API callback URLs require HTTPS')
            if self.smtp_host and not (self.smtp_starttls or self.smtp_ssl):
                raise ValueError("Staging and production SMTP require TLS")
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
            if any(apple_parts) and not self.oauth_token_encryption_key:
                raise ValueError("Apple OAuth requires OAUTH_TOKEN_ENCRYPTION_KEY for revocable credentials")
            if self.environment == "production":
                if not all(google_parts) or not all(apple_parts):
                    raise ValueError("Production requires Google and Apple OAuth credentials")
                if not self.google_android_client_id or not self.google_ios_client_id:
                    raise ValueError("Production requires Android and iOS Google OAuth client IDs")
                if not self.apple_ios_client_id:
                    raise ValueError("Production requires the Apple iOS client ID")
                if not self.oauth_callback_base_url.startswith("https://"):
                    raise ValueError("Production OAuth callbacks require HTTPS")
                if self.account_action_url and not self.account_action_url.startswith("https://"):
                    raise ValueError("Production account action links require HTTPS")
        if self.smtp_ssl and self.smtp_starttls:
            raise ValueError("Choose either SMTP_SSL or SMTP_STARTTLS, not both")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def trusted_host_list(self) -> list[str]:
        from urllib.parse import urlsplit
        if self.trusted_hosts:
            return [host.strip().lower() for host in self.trusted_hosts.split(',') if host.strip()]
        # Public URLs are configuration, never derived from the request Host.
        return list(dict.fromkeys(host for host in (
            urlsplit(self.oauth_callback_base_url).hostname,
            urlsplit(self.public_app_url).hostname, 'localhost', '127.0.0.1',
        ) if host))

    @property
    def google_oauth_configured(self) -> bool:
        return bool(self.google_oauth_client_id and self.google_oauth_client_secret)

    @property
    def google_native_configured(self) -> bool:
        return bool(self.google_oauth_client_id and (self.google_android_client_id or self.google_ios_client_id))

    @property
    def apple_oauth_configured(self) -> bool:
        return bool(
            self.apple_oauth_client_id
            and self.apple_team_id
            and self.apple_key_id
            and self.apple_private_key
        )

    @property
    def apple_native_configured(self) -> bool:
        return bool(self.apple_ios_client_id and self.apple_team_id and self.apple_key_id and self.apple_private_key
                    and self.oauth_token_encryption_key)

    @property
    def account_action_url(self) -> str:
        return self.account_action_base_url or self.public_app_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
