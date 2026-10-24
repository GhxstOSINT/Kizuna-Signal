from pydantic import BaseModel


class MissingItem(BaseModel):
    field: str
    message: str


class CompletenessReport(BaseModel):
    ready_for_analysis: bool
    score: float  # share of all checks (required + recommended) that pass, 0..1
    missing_required: list[MissingItem]
    missing_recommended: list[MissingItem]
