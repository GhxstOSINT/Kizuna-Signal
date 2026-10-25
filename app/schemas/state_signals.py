from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict


class StateSignalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title_id: str
    state: str
    source: str
    metric: str
    value: float
    as_of: date
    detail: dict


class StateSignalImportResult(BaseModel):
    imported: int
    rejected: list[dict]
    rejected_count: int
    import_batch: str
    state_index: dict[str, float] | None
