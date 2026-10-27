from functools import lru_cache
from urllib.parse import urlsplit
from ipaddress import ip_network
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SocialSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='SOCIAL_', extra='ignore', hide_input_in_errors=True)
    l4_enabled: bool = False
    l4_collection_enabled: bool = False
    l4_publication_enabled: bool = False
    database_url: str = Field('', repr=False)
    allow_sqlite: bool = False
    service_role: str = Field('staff', pattern='^(staff|gateway|relay|maintenance)$')
    consumer_db_role: str = Field('', max_length=63)
    admin_origin: str = 'https://localhost:8443'
    admin_networks: str = '127.0.0.1/32,::1/128'
    trusted_proxy_ip: str = ''
    worker_key: str = Field('', repr=False)
    session_idle_seconds: int = Field(900, ge=60, le=900)
    session_absolute_seconds: int = Field(28800, ge=300, le=28800)
    recent_seconds: int = Field(300, ge=30, le=300)
    observation_retention_days: int = Field(14, ge=1, le=30)
    max_publishers: int = Field(250, ge=1, le=1000)
    max_observations: int = Field(5000, ge=1, le=10000)
    max_audit_events: int = Field(100000, ge=1000, le=1000000)
    max_jobs: int = Field(5000, ge=10, le=10000)

    @model_validator(mode='after')
    def validate_boundary(self):
        if self.l4_enabled and (not self.database_url or (not self.database_url.startswith('postgresql') and not (self.allow_sqlite and self.database_url.startswith('sqlite')))):
            raise ValueError('Staff services require the existing PostgreSQL database; SQLite must be explicitly enabled for disposable tests')
        p = urlsplit(self.admin_origin)
        if p.scheme != 'https' or not p.hostname or p.username or p.password or p.path or p.query or p.fragment:
            raise ValueError('Configure an exact HTTPS administrative origin, without a path')
        if self.trusted_proxy_ip:
            from ipaddress import ip_address
            if ip_address(self.trusted_proxy_ip).is_global:
                raise ValueError('The trusted proxy must be a specific private address')
        for network in self.admin_networks.split(','):
            n = ip_network(network.strip())
            if n.prefixlen == 0 or not n.is_private:
                raise ValueError('Administrative access must be restricted to private device networks')
        if not self.admin_networks:
            raise ValueError('Private administrative networks must be explicit')
        if self.l4_collection_enabled and not self.l4_enabled:
            raise ValueError('Collection requires Level 4')
        if self.l4_publication_enabled and not self.l4_enabled:
            raise ValueError('Publication requires Level 4')
        return self

    @property
    def rp_id(self):
        return urlsplit(self.admin_origin).hostname


@lru_cache
def settings():
    return SocialSettings()
