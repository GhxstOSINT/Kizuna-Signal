from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.db.models import Title
from app.ml.state_model import StateModel
from app.ml.success import SuccessModel
from app.schemas.analysis import PredictionDriver, RegionalScore
from app.services import census
from app.services.state_frame import make_frame

settings = get_settings()

WARNING_TEXT = {
    "no_pre_release_demand": "An unreleased title has no Google Trends window before launch, so demand momentum is not scored.",
    "no_youtube_adapter": "Trailer engagement is not collected yet, so engagement quality is not scored.",
    "no_comparable_titles": "No comparable titles were found.",
    "few_comparables": "Fewer than three comparable titles were found.",
    "unlike_training_titles": "This title is unlike the titles the model was trained on.",
    "no_franchise_history": "There is no franchise history for this title.",
    "small_training_set": "The model was trained on a small set of titles, so its results are exploratory.",
    "sparse_state_training": "Some states have too few training titles for a reliable result.",
    "synthetic_augmented": "The training data includes synthetic rows.",
}


def readable_warning(warning: str) -> str:
    """Turn a machine code such as `no_franchise_history` into a sentence."""
    code = warning.split(":", 1)[0].strip()
    return WARNING_TEXT.get(code, warning)


@dataclass(frozen=True, slots=True)
class ModelAnalysis:
    score: float
    interval: tuple[float, float]
    confidence: float
    components: dict[str, float]
    component_details: list[dict]
    regions: list[RegionalScore]
    positive_drivers: list[PredictionDriver]
    negative_drivers: list[PredictionDriver]
    warnings: list[str]
    model_version: str
    score_meaning: str
    evaluation: dict[str, float | int | str | None]


@lru_cache(maxsize=1)
def load_state_model() -> StateModel:
    return StateModel.load(Path(settings.models_dir))


@lru_cache(maxsize=1)
def load_success_model() -> SuccessModel | None:
    return SuccessModel.from_csv(load_state_model(), Path(settings.csv_dir))


def current_model_version() -> str | None:
    try:
        return load_state_model().version
    except (FileNotFoundError, ValueError, OSError):
        return None


def _release_date(value: str) -> date:
    quarter = re.search(r"\bQ([1-4])\s+(20\d{2})\b", value, re.IGNORECASE)
    if quarter:
        return date(int(quarter.group(2)), 1 + (int(quarter.group(1)) - 1) * 3, 1)
    year = re.search(r"\b(20\d{2})\b", value)
    return date(int(year.group(1)), 7, 1) if year else date.today()


def _frame(title: Title):
    genres = list(dict.fromkeys([title.primary_genre, *title.genres]))
    return make_frame(
        title.id,
        title.id,
        title.english_title or title.name,
        title.name if title.english_title and title.english_title != title.name else None,
        genres,
        title.themes,
        title.content_format,
        _release_date(title.expected_release_period),
        title.synopsis,
        title.studio,
    )


def _regions(states: list[dict], confidence: float, platform: str) -> list[RegionalScore]:
    count = max(1, len(states))
    rows: list[RegionalScore] = []
    for item in states:
        name = item["name"]
        profile = census.resolve_state(name)
        percentile = 100 * (count - item["rank"] + 0.5) / count
        training_confidence = min(100.0, 35 + 2.5 * item["train_titles"])
        state_confidence = min(confidence, training_confidence)
        rows.append(
            RegionalScore(
                state=name,
                score=round(percentile, 2),
                confidence=round(state_confidence, 2),
                recommended_language=profile.language if profile else "Hindi / English",
                preferred_platform="OTT" if platform.lower() == "undecided" else platform,
                reasons=[
                    f"Ranked {item['rank']} of {count} states by predicted relative demand lift.",
                    f"Expected share of modelled India demand is {100 * item['expected_share']:.1f}%.",
                    f"The state estimate uses {item['train_titles']} real labelled titles and {item['synthetic_rows']} synthetic rows.",
                ],
            )
        )
    return rows


def _drivers(components: list[dict]) -> tuple[list[PredictionDriver], list[PredictionDriver]]:
    positive: list[PredictionDriver] = []
    negative: list[PredictionDriver] = []
    for component in components:
        value = component.get("value")
        if value is None or component.get("status") != "ok":
            continue
        contribution = (float(value) - 50) * float(component["weight"])
        driver = PredictionDriver(
            name=component["label"],
            contribution=round(abs(contribution), 2),
            direction="positive" if contribution >= 0 else "negative",
            evidence=(
                f"Model component {value:.1f}/100 with {100 * float(component['weight']):.0f}% configured weight; "
                f"held-out Spearman {component.get('validation_spearman', 0):.2f}."
            ),
        )
        (positive if contribution >= 0 else negative).append(driver)
    return positive[:5], negative[:5]


def score_title(title: Title, evidence_confidence: float) -> ModelAnalysis:
    model = load_state_model()
    success = load_success_model()
    if success is None:
        raise FileNotFoundError("Success-model outcome tables are unavailable")

    frame = _frame(title)
    prediction = model.predict(frame)
    success_score = success.score(
        model,
        frame,
        prediction["states"],
        Path(settings.models_dir) / "state" / model.version,
    )
    components = success_score["components"]
    measured = {
        component["key"]: round(float(component["value"]), 2)
        for component in components
        if component.get("value") is not None
    }
    positive, negative = _drivers(components)
    warnings = list(prediction["warnings"])
    warnings.extend(
        component["reason"]
        for component in components
        if component.get("status") != "ok" and component.get("reason")
    )
    model_confidence = float(prediction["confidence"])
    confidence = round(0.75 * model_confidence + 0.25 * evidence_confidence, 2)
    report = model.report
    ensemble = report.get("metrics_oof", {}).get("ensemble", {})
    evaluation = {
        "scheme": report.get("evaluation"),
        "labelled_titles": report.get("n_labelled_titles"),
        "oof_titles": report.get("oof_titles"),
        "spearman": ensemble.get("spearman", {}).get("mean"),
        "top3_hit": ensemble.get("top3_hit", {}).get("mean"),
    }
    return ModelAnalysis(
        score=float(success_score["rating"]),
        interval=(float(success_score["rating_low"]), float(success_score["rating_high"])),
        confidence=confidence,
        components=measured,
        component_details=components,
        regions=_regions(prediction["states"], confidence, title.target_platform),
        positive_drivers=positive,
        negative_drivers=negative,
        warnings=list(dict.fromkeys(readable_warning(w) for w in warnings)),
        model_version=model.version,
        score_meaning=success_score["rating_reference"]["meaning"],
        evaluation=evaluation,
    )
