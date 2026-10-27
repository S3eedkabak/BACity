"""Shared machine authorization/content contract; independent of ASGI apps."""
import time
import secrets
from fastapi import Depends,Header,HTTPException
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal
from .db import database
from .config import settings
from .security import budget
from .workflows import stopped

def worker(x_social_worker_key: str=Header(''),db=Depends(database)):
    cfg=settings()
    if not cfg.l4_enabled or not cfg.l4_collection_enabled or len(cfg.worker_key)<32:
        raise HTTPException(503,'Social collection is disabled')
    if not secrets.compare_digest(x_social_worker_key,cfg.worker_key):
        raise HTTPException(401,'Worker authentication required')
    budget(db,'worker-requests','collector',120,60)
    if stopped(db):
        raise HTTPException(503,'Emergency stop active')

class Content(BaseModel):
    model_config=ConfigDict(extra='forbid')
    source_url: str=Field(max_length=1024)
    external_id: str=Field(min_length=1,max_length=200)
    caption: str=Field(min_length=5,max_length=20000)
    published_at: str|None=Field(None,max_length=64)
    content_type: Literal['text','event']='text'
    adapter: str=Field(max_length=80)
    publisher_identifier: str|None=Field(None,max_length=30)
    media: list[str]=Field(default_factory=list,max_length=3)



def cleanup_worker(x_social_worker_key:str=Header(''),db=Depends(database)):
    """Existing-run cancellation/accounting remains possible during shutdown.

    New launch authorization is checked separately by the Apify state machine.
    """
    cfg=settings()
    if len(cfg.worker_key)<32 or not secrets.compare_digest(x_social_worker_key,cfg.worker_key):
        raise HTTPException(401,'Worker authentication required')
    budget(db,'worker-requests','collector',120,60)
