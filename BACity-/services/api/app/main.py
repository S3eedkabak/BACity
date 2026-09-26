from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from app.core.http import RequestMiddleware
import json
from pathlib import Path

from app.config import get_settings
from app.database import Base, engine, get_db
from app.api.routes import events, venues, auth, users, community, discovery, billing, crawler

# Import models so they're registered on Base.metadata before create_all
# (used only for the SQLite dev/test path; Postgres uses Alembic migrations).
from app import models  # noqa: F401

settings = get_settings()
Path(settings.media_root).mkdir(parents=True, exist_ok=True)

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
app.add_middleware(RequestMiddleware)
app.mount("/media", StaticFiles(directory=settings.media_root), name="media")


@app.exception_handler(ValidationError)
async def validation_error(request, exc):
    return JSONResponse(status_code=422, content={'detail': json.loads(exc.json(include_input=False, include_context=False))})


@app.exception_handler(IntegrityError)
async def duplicate_error(request, exc):
    return JSONResponse(status_code=409, content={'detail': 'This record already exists or changed concurrently; refresh and try again'})

app.include_router(auth.router)
app.include_router(community.router)
app.include_router(discovery.router)
app.include_router(billing.router)
app.include_router(users.router)
app.include_router(events.router)
app.include_router(venues.router)
app.include_router(crawler.router)
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
