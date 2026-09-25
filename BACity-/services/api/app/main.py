from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import Base, engine, get_db
from app.api.routes import events, venues, auth, users

# Import models so they're registered on Base.metadata before create_all
# (used only for the SQLite dev/test path; Postgres uses Alembic migrations).
from app import models  # noqa: F401

settings = get_settings()

app = FastAPI(
    title="Bratislava Event Discovery API",
    version="0.1.0",
    description="Read/write API over the Bratislava event dataset. "
                 "See docs/architecture.md for how this fits the wider platform.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(events.router)
app.include_router(venues.router)
app.include_router(events.router, prefix='/v1')


@app.on_event("startup")
def on_startup():
    if settings.database_url.startswith("sqlite"):
        # Convenience for local dev/tests only — Postgres is managed via Alembic.
        Base.metadata.create_all(bind=engine)


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text('SELECT 1'))
    return {"status": "ok"}
