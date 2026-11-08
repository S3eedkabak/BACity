from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from .config import settings

@lru_cache
def session_factory():
    url = settings().database_url
    engine = create_engine(url, hide_parameters=True, pool_pre_ping=True,
        connect_args={'check_same_thread': False} if url.startswith('sqlite') else {})
    return sessionmaker(bind=engine, expire_on_commit=False)

def database():
    with session_factory()() as db:
        from .database_policy import verify_database_policy
        cfg=settings()
        verify_database_policy(db,service_role=cfg.service_role,consumer_role=cfg.consumer_db_role)
        yield db
