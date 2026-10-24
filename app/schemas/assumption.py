from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.common import CleanList, iso_language_codes
from app.schemas.enums import (
    BudgetBand,
    DistributionModel,
    LaunchGeography,
    LocalizationMode,
    Positioning,
)


class AssumptionIn(BaseModel):
    """Release assumptions. The first four fields are required for a usable set."""

    distribution_model: DistributionModel
    localization_mode: LocalizationMode
    languages: CleanList = Field(min_length=1, description="ISO 639-1 codes, e.g. hi, ta")
    launch_geography: LaunchGeography
    target_states: CleanList = []
    planned_launch_date: date | None = None
    marketing_budget_band: BudgetBand | None = None
    positioning: Positioning | None = None

    _languages = field_validator("languages")(iso_language_codes)

    @model_validator(mode="after")
    def states_match_geography(self) -> "AssumptionIn":
        if self.launch_geography == LaunchGeography.NATIONAL and self.target_states:
            raise ValueError("target_states must be empty for a national launch")
        if self.launch_geography != LaunchGeography.NATIONAL and not self.target_states:
            raise ValueError(
                f"target_states is required when launch_geography is {self.launch_geography.value}"
            )
        return self


class AssumptionOut(AssumptionIn):
    model_config = ConfigDict(from_attributes=True)

    title_id: int
