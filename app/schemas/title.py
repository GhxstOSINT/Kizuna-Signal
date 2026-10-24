from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import CleanList
from app.schemas.enums import ContentFormat


class TitleCreate(BaseModel):
    """A title may be saved as a draft; GET /titles/{id}/completeness reports what is missing."""

    project_id: int = Field(gt=0)
    name_en: str = Field(min_length=1, max_length=255)
    name_jp: str | None = Field(default=None, max_length=255)
    synopsis: str | None = None
    genres: CleanList = []
    format: ContentFormat | None = None
    studio: str | None = Field(default=None, max_length=255)
    franchise: str | None = Field(default=None, max_length=255)
    cast_members: CleanList = []
    release_date: date | None = None
    is_unreleased: bool = True


class TitleOut(TitleCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
