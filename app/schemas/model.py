from typing import Any

from pydantic import BaseModel, Field


class StateCoverage(BaseModel):
    state: str
    name: str
    real_titles: int = Field(description="labelled titles with Trends data in this state")
    synthetic_rows: int = Field(description="weighted-average rows added for titles with no data here")
    sparse: bool = Field(description="under 20 real titles: the least reliable states")
    heldout_bias: float | None = Field(default=None, description="mean(predicted - observed) lift on real held-out rows")
    heldout_rmse: float | None = None


class ModelCard(BaseModel):
    model_version: str
    task: str
    trained_at: str | None
    n_labelled_titles: int
    n_states: int
    training_data: dict[str, Any]
    evaluation: dict[str, Any]
    success_model: dict[str, Any] | None = Field(description="content-fit model behind the India success score")
    states: list[StateCoverage]
    limitations: list[str]
