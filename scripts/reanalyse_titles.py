"""Run a fresh analysis (live sources by default) for every stored title.

    PYTHONPATH=.packages py -3.12 scripts/reanalyse_titles.py

Adds a new analysis snapshot per title; older snapshots are kept. The portfolio shows the newest.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db.models import Analysis, Title  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.services.analysis import create_analysis, run_analysis_pipeline  # noqa: E402


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    with SessionLocal() as db:
        titles = list(db.scalars(select(Title)))
        ids = [(t.id, t.name) for t in titles]
    for title_id, name in ids:
        with SessionLocal() as db:
            analysis, _ = create_analysis(db, db.get(Title, title_id))
            analysis_id = analysis.id
        run_analysis_pipeline(analysis_id)
        with SessionLocal() as db:
            result = db.get(Analysis, analysis_id).result or {}
        sources = ", ".join(f"{s['source']}={s['status']}" for s in result.get("source_status", []))
        print(f"{name:20s} score {result.get('market_potential_score')} "
              f"confidence {result.get('confidence_score')} [{sources}]")


if __name__ == "__main__":
    main()
