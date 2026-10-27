"""Apify policy; the actual token is passed only to the isolated collector."""
from decimal import Decimal
from typing import Literal
from pydantic import Field,field_validator
from pydantic_settings import BaseSettings,SettingsConfigDict

class ApifySettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix='APIFY_',extra='ignore',hide_input_in_errors=True)
    enabled: bool=False
    api_token: str=Field('',repr=False)
    token_configured: bool=False
    instagram_actor_id: Literal['apify/instagram-scraper']='apify/instagram-scraper'
    monthly_budget_usd: Decimal=Field(Decimal('4.00'),gt=0,le=4)
    monthly_reserve_usd: Decimal=Field(Decimal('1.00'),ge=1,le=5)
    max_active_profiles: int=Field(20,ge=1,le=20)
    default_posts_per_profile: int=Field(1,ge=1,le=3)
    collection_interval_hours: int=Field(24,ge=24,le=168)
    @field_validator('token_configured',mode='before')
    @classmethod
    def empty_boolean(cls,value):return False if value=='' else value
    @property
    def configured(self):return self.token_configured or bool(self.api_token)
    @property
    def interval(self):return self.collection_interval_hours*3600
    @property
    def budget(self):return int(self.monthly_budget_usd*1000000)
    @property
    def reserve(self):return int(self.monthly_reserve_usd*1000000)

def apify_settings():return ApifySettings()

def provider_preference():
    import os
    value=os.environ.get('INSTAGRAM_ACQUISITION_PROVIDER','apify')
    if value not in ('apify','scrapingant'):raise ValueError('Select apify or scrapingant explicitly')
    return value
