from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import Session

from app.schemas.completeness import CompletenessReport, MissingItem
from app.services import assets as asset_service
from app.services import assumptions as assumption_service

MIN_SYNOPSIS_CHARS = 50


def evaluate(title: Any, assets: Sequence[Any], assumption: Any | None) -> CompletenessReport:
    """Pure check of a title's intake data; inputs are duck-typed so it is testable without a DB."""
    asset_types = {a.asset_type for a in assets}
    synopsis = (title.synopsis or "").strip()

    # (field, message, passes)
    required = [
        ("synopsis", f"synopsis of at least {MIN_SYNOPSIS_CHARS} characters", len(synopsis) >= MIN_SYNOPSIS_CHARS),
        ("genres", "at least one genre", bool(title.genres)),
        ("format", "content format", title.format is not None),
        ("studio", "studio", bool((title.studio or "").strip())),
        ("assumptions", "release assumptions", assumption is not None),
    ]
    recommended = [
        ("name_jp", "Japanese title", bool((title.name_jp or "").strip())),
        ("franchise", "franchise", bool((title.franchise or "").strip())),
        ("cast_members", "cast", bool(title.cast_members)),
        ("release_date", "release date", title.release_date is not None),
        ("assets.poster", "poster", "poster" in asset_types),
        ("assets.trailer", "trailer", "trailer" in asset_types),
        (
            "assumptions.marketing_budget_band",
            "marketing budget band",
            assumption is not None and assumption.marketing_budget_band is not None,
        ),
        (
            "assumptions.planned_launch_date",
            "planned launch date",
            assumption is not None and assumption.planned_launch_date is not None,
        ),
    ]

    missing_required = [MissingItem(field=f, message=f"Missing {m}") for f, m, ok in required if not ok]
    missing_recommended = [MissingItem(field=f, message=f"Missing {m}") for f, m, ok in recommended if not ok]
    total = len(required) + len(recommended)
    passed = total - len(missing_required) - len(missing_recommended)
    return CompletenessReport(
        ready_for_analysis=not missing_required,
        score=round(passed / total, 3),
        missing_required=missing_required,
        missing_recommended=missing_recommended,
    )


def for_title(db: Session, title: Any) -> CompletenessReport:
    assets = asset_service.list_for_title(db, title.id)
    assumption = assumption_service.get(db, title.id)
    return evaluate(title, assets, assumption)
