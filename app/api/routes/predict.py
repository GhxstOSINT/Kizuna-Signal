from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response

from app.adapters.google_trends import TrendsClient
from app.core.config import settings
from app.ml.state_model import StateModel
from app.ml.success import SuccessModel
from app.reports import build as report_build
from app.reports.render import MEDIA, RENDER
from app.schemas.predict import PredictIn, PredictOut
from app.seo import rank as seo_rank
from app.seo.terms import candidates
from app.services.state_frame import make_frame

router = APIRouter(tags=["predict"])


@lru_cache(maxsize=1)
def _load_model() -> StateModel:
    return StateModel.load(Path(settings.models_dir))


def get_state_model() -> StateModel:
    try:
        return _load_model()
    except FileNotFoundError as exc:
        raise HTTPException(503, "No trained state model found; run scripts/train_state_model.py") from exc


_SUCCESS: dict[int, SuccessModel | None] = {}  # one fit per state-model object


def get_success_model(model: StateModel = Depends(get_state_model)) -> SuccessModel | None:
    if id(model) not in _SUCCESS:
        _SUCCESS[id(model)] = SuccessModel.from_csv(model, Path(settings.csv_dir))
    return _SUCCESS[id(model)]


@lru_cache(maxsize=1)
def get_trends_client() -> TrendsClient:
    return TrendsClient()


def _model_folder(model: StateModel) -> Path:
    return Path(settings.models_dir) / "state" / model.version


def run_prediction(body: PredictIn, model: StateModel, trends: TrendsClient, success: SuccessModel | None) -> dict:
    launch = body.release_date or date.today()
    frame = make_frame(f"predict:{body.name_en}", f"predict:{body.name_en}", body.name_en, body.name_jp,
                       body.genres, body.tags, body.format.value, launch, body.synopsis, body.studio,
                       body.episodes, body.minutes_per_episode)
    result = model.predict(frame)
    states = result["states"]
    out = report_build.prediction_out(result, body.name_en,
                                      success.score(model, frame, states, _model_folder(model)) if success is not None else None)
    unknown = sorted(set(frame.iloc[0]["genres"]) - set(model.encoder.genres_))
    if unknown:  # silently scoring a genre the model never saw would look like a real signal
        out["india"]["warnings"].append("unknown_genres: " + ", ".join(unknown))
    if body.include_seo:
        cands = candidates(body.name_en, body.name_jp, body.languages,
                           body.localization_mode.value if body.localization_mode else None)
        focus = [{"state": s["state"], "name": s["name"], "lift": s["lift"], "expected_share": s["expected_share"]}
                 for s in states[:3]]
        out["seo"] = seo_rank.insight(trends, cands, date.today(), focus)
    return out


@router.post("/predict", response_model=PredictOut)
def predict(body: PredictIn, model: StateModel = Depends(get_state_model),
            success: SuccessModel | None = Depends(get_success_model),
            trends: TrendsClient = Depends(get_trends_client)):
    """One request in, state-by-state prediction and India success score out (synchronous)."""
    return run_prediction(body, model, trends, success)


@router.post("/predict/report")
def predict_report(body: PredictIn, format: Literal["json", "csv", "xml", "pdf"] = "pdf",
                   model: StateModel = Depends(get_state_model),
                   success: SuccessModel | None = Depends(get_success_model),
                   trends: TrendsClient = Depends(get_trends_client)):
    """The same prediction as a downloadable report: pdf (charts and maths), json, csv (one row per state) or xml."""
    out = run_prediction(body, model, trends, success)
    report = report_build.assemble(report_build.title_from_body(body), out, out["success"], model)
    slug = "".join(c if c.isalnum() else "_" for c in body.name_en).strip("_") or "title"
    return Response(RENDER[format](report), media_type=MEDIA[format],
                    headers={"Content-Disposition": f'attachment; filename="kizuna_{slug}.{format}"'})
