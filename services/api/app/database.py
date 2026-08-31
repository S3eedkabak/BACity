"""
SQLAlchemy engine/session setup.

Design note (see docs/architecture.md "Geography" section): the MVP stores
latitude/longitude as plain floats on Event and Venue so the same models
and queries work against SQLite (tests, local dev without Docker) and
Postgres+PostGIS (production). `crud/event.py` detects the active dialect
and uses ST_DWithin on Postgres, falling back to a haversine bounding-box
query everywhere else. PostGIS geometry columns + GiST indexes are added
by a later migration purely as a performance layer once real traffic
justifies it (Architectural Principle 8: build infrastructure incrementally).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
