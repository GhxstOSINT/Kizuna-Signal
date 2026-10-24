from fastapi import FastAPI

from app.api.routes import analyses, model, predict, projects, reports, seo, sources, titles
from app.core.config import settings

app = FastAPI(title="Kizuna Signal API", version=settings.api_version)
for module in (projects, titles, sources, analyses, reports, seo, predict, model):
    app.include_router(module.router, prefix="/api/v1")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": settings.api_version}
