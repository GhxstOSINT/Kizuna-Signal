from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str | None = None
    avatar_url: str | None = None


class ProviderRead(BaseModel):
    id: str
    label: str
    enabled: bool


class ProvidersRead(BaseModel):
    providers: list[ProviderRead]
