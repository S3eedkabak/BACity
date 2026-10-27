"""Run privately: uvicorn app.social.main:app --no-proxy-headers --no-access-log."""
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import IntegrityError
from app.core.http import RequestMiddleware
from .boundary import PrivateBoundary
from .auth import router as auth
from .routes import router as routes

app=FastAPI(title='BACity staff',docs_url=None,redoc_url=None,openapi_url=None)
app.add_middleware(RequestMiddleware,max_body=65536)
app.add_middleware(PrivateBoundary)
app.include_router(auth)
app.include_router(routes)
STATIC=Path(__file__).parent/'static'
app.mount('/assets',StaticFiles(directory=STATIC),name='staff-assets')

@app.get('/')
def index():
    return FileResponse(STATIC/'index.html')

@app.exception_handler(RequestValidationError)
async def invalid_request(request,exc):
    return JSONResponse({'detail':'Invalid or unexpected input fields'},422)

@app.exception_handler(IntegrityError)
async def conflict(request,exc):
    return JSONResponse({'detail':'This record already exists or changed concurrently'},409)
