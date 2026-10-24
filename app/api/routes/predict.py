from datetime import date
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from app.adapters.google_trends import TrendsClient
from app.core.config import settings
from app.ml.state_model import StateModel
from app.schemas.predict import IndiaSummary, PredictIn, PredictOut
from app.seo import rank as seo_rank
from app.seo.terms import candidates
from app.services.state_scoring import make_frame

router = APIRouter(tags=["predict"])
TOP_N = 5
NOTE = ("There is no single national score: the state model predicts where a title over-performs and each "
        "state's share of India demand. Read confidence and warnings before relying on the ranking.")


@lru_cache(maxsize=1)
def _load_model() -> StateModel:
    return StateModel.load(Path(settings.models_dir))


def get_state_model() -> StateModel:
    try:
        return _load_model()
    except FileNotFoundError as exc:
        raise HTTPException(503, "No trained state model found; run scripts/train_state_model.py") from exc


@lru_cache(maxsize=1)
def get_trends_client() -> TrendsClient:
    return TrendsClient()


@router.post("/predict", response_model=PredictOut)
def predict(body: PredictIn, model: StateModel = Depends(get_state_model),
            trends: TrendsClient = Depends(get_trends_client)):
    """One request in, state-by-state prediction out (synchronous; typically about a second)."""
    launch = body.release_date or date.today()
    frame = make_frame(f"predict:{body.name_en}", f"predict:{body.name_en}", body.name_en, body.name_jp,
                       body.genres, body.tags, body.format.value, launch, body.synopsis, body.studio,
                       body.episodes, body.minutes_per_episode)
    result = model.predict(frame)
    states = [{k: v for k, v in s.items()} for s in result["states"]]
    out = {
        "model_version": result["model_version"], "task": result["task"], "title": body.name_en,
        "india": {"confidence": result["confidence"], "confidence_factors": result["confidence_factors"],
                  "warnings": result["warnings"], "note": NOTE,
                  "top_states": [s["state"] for s in states[:TOP_N]],
                  "bottom_states": [s["state"] for s in states[-TOP_N:]]},
        "states": states, "comparables": result["comparables"], "seo": None,
    }
    if body.include_seo:
        cands = candidates(body.name_en, body.name_jp, body.languages,
                           body.localization_mode.value if body.localization_mode else None)
        focus = [{"state": s["state"], "name": s["name"], "lift": s["lift"], "expected_share": s["expected_share"]}
                 for s in states[:3]]
        out["seo"] = seo_rank.insight(trends, cands, date.today(), focus)
    return out
