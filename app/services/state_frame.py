"""One-row content frame for a title that is not in the training data (no database)."""

from datetime import date

import pandas as pd

from app.ml.features import titles_frame
from app.ml.schema import TitleRecord

FORMATS = {"anime_series": "TV", "anime_film": "MOVIE"}


def make_frame(
    title_id: str,
    franchise_id: str,
    name_en: str,
    name_jp: str | None,
    genres: list[str],
    themes: list[str],
    fmt: str | None,
    launch: date,
    synopsis: str,
    studio: str | None = None,
    episodes: int | None = None,
    minutes: float | None = None,
    has_prequel: bool = False,
) -> pd.DataFrame:
    """One-row content frame for a title that is not in the training data."""
    record = TitleRecord(
        title_id=title_id,
        franchise_id=franchise_id,
        english_title=name_en,
        japanese_title=name_jp,
        genres=genres,
        themes=themes,
        format=FORMATS.get(fmt or "", fmt),
        original_release_date=launch,
        synopsis=synopsis,
        runtime_or_episode_count={"episodes": episodes},
    )
    return titles_frame([record]).assign(
        studio=studio, has_prequel=has_prequel, minutes=minutes or 0.0
    )
