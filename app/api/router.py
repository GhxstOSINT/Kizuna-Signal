from fastapi import APIRouter

from app.api.routes import analyses, health, model, projects, sources, state_signals

api_router = APIRouter()
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(analyses.router, tags=["analysis"])
api_router.include_router(state_signals.router, tags=["state-signals"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(model.router, prefix="/model", tags=["model"])
api_router.include_router(health.router, tags=["health"])
