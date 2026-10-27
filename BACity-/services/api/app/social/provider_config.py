"""Provider policy, distinct from consumer settings; secrets never serialized."""
from pydantic import Field, model_validator, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class ScrapingAntSettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix='SCRAPINGANT_',extra='ignore',hide_input_in_errors=True)
    enabled: bool=False
    api_key: str=Field('',repr=False)
    key_configured: bool=False  # Private stack receives only this boolean, not the key.
    monthly_credit_limit: int=Field(10000,ge=1,le=1000000)
    monthly_credit_reserve: int=Field(1000,ge=0,le=1000000)
    max_active_profiles: int=Field(20,ge=1,le=100)
    collection_interval_hours: int=Field(24,ge=24,le=168)
    @field_validator('key_configured',mode='before')
    @classmethod
    def empty_boolean(cls,value):
        return False if value=='' else value
    @model_validator(mode='after')
    def reserve_within_limit(self):
        if self.monthly_credit_reserve>=self.monthly_credit_limit:
            raise ValueError('Credit reserve must be below the limit')
        return self
    @property
    def configured(self):
        return self.key_configured or bool(self.api_key)
    @property
    def interval(self):
        return self.collection_interval_hours*3600

def provider_settings():
    return ScrapingAntSettings()
