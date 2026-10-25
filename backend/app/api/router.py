from fastapi import APIRouter

from app.api.routes import analyses, auth, health, model, predict, projects, sources

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(analyses.router, tags=["analysis"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(health.router, tags=["health"])
api_router.include_router(predict.router)
api_router.include_router(model.router)
