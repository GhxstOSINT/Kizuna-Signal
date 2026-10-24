from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.sources import KNOWN_SOURCES
from app.db.models import Job, Source, SourceRun
from app.services import jobs as job_service


def list_all(db: Session) -> list[Source]:
    """Every known source, creating missing rows on first use."""
    have = {s.name: s for s in db.scalars(select(Source))}
    missing = [n for n in KNOWN_SOURCES if n not in have]
    if missing:
        db.add_all(Source(name=n) for n in missing)
        db.commit()
        have = {s.name: s for s in db.scalars(select(Source))}
    return [have[n] for n in KNOWN_SOURCES]


def disabled_names(db: Session) -> list[str]:
    return [s.name for s in list_all(db) if not s.enabled]


def set_enabled(db: Session, name: str, enabled: bool) -> Source | None:
    source = next((s for s in list_all(db) if s.name == name), None)
    if source is not None:
        source.enabled = enabled
        db.commit()
        db.refresh(source)
    return source


def request_collection(db: Session, title_id: int, names: list[str] | None) -> Job:
    """Queue collection for the requested sources. Raises ValueError for disabled ones."""
    enabled = [s.name for s in list_all(db) if s.enabled]
    chosen = names if names is not None else enabled
    blocked = sorted(set(chosen) - set(enabled))
    if blocked:
        raise ValueError(f"sources are disabled: {', '.join(blocked)}")
    if not chosen:
        raise ValueError("no enabled sources to collect from")
    job = job_service.add(db, "collection", {"title_id": title_id, "sources": chosen})
    db.commit()
    db.refresh(job)
    return job


def runs(db: Session, title_id: int | None, source: str | None, limit: int = 100) -> list[SourceRun]:
    stmt = select(SourceRun).order_by(SourceRun.collected_at.desc()).limit(limit)
    if title_id is not None:
        stmt = stmt.where(SourceRun.title_id == title_id)
    if source is not None:
        stmt = stmt.join(Source).where(Source.name == source)
    return list(db.scalars(stmt))
