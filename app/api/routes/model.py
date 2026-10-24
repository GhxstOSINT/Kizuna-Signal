from fastapi import APIRouter, Depends

from app.api.routes.predict import get_state_model, get_success_model
from app.ml.state_model import StateModel
from app.ml.success import SuccessModel
from app.reports import build as report_build
from app.schemas.model import ModelCard

router = APIRouter(tags=["model"])


@router.get("/model", response_model=ModelCard)
def model_card(model: StateModel = Depends(get_state_model),
               success: SuccessModel | None = Depends(get_success_model)):
    """What the loaded model is: version, data, held-out accuracy, synthetic-data effect, per-state coverage."""
    return report_build.model_card(model, success)
