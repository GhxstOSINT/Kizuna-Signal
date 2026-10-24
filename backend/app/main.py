from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import init_db

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Explainable market-potential intelligence for Japanese media entering India. "
        "Scores are decision-support proxies, not guaranteed revenue forecasts."
    ),
    lifespan=lifespan,
)
register_exception_handlers(app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health/live", include_in_schema=False)
def root_liveness() -> dict:
    return {"status": "ok", "service": "kizuna-signal-api"}


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {
        "service": settings.app_name,
        "version": "0.1.0",
        "docs": "/docs",
        "readiness": "/api/v1/health/ready",
    }
