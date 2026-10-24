from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.enums import AssetType

MB = 1024 * 1024

# Allowed MIME types and size ceiling per asset type.
ASSET_RULES: dict[AssetType, tuple[set[str], int]] = {
    AssetType.POSTER: ({"image/jpeg", "image/png", "image/webp"}, 20 * MB),
    AssetType.TRAILER: ({"video/mp4", "video/quicktime", "video/webm"}, 2048 * MB),
    AssetType.SYNOPSIS_DOCUMENT: (
        {
            "application/pdf",
            "text/plain",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        },
        25 * MB,
    ),
    AssetType.SCRIPT: ({"application/pdf", "text/plain"}, 25 * MB),
}


class AssetCreate(BaseModel):
    asset_type: AssetType
    filename: str = Field(min_length=1, max_length=255, pattern=r"^[^/\\]+$")
    storage_uri: str = Field(max_length=2048, pattern=r"^(s3|https)://\S+$")
    mime_type: str
    size_bytes: int = Field(gt=0)
    checksum_sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")

    @model_validator(mode="after")
    def check_type_rules(self) -> "AssetCreate":
        allowed, max_bytes = ASSET_RULES[self.asset_type]
        if self.mime_type not in allowed:
            raise ValueError(
                f"{self.asset_type.value} must be one of: {', '.join(sorted(allowed))}"
            )
        if self.size_bytes > max_bytes:
            raise ValueError(
                f"{self.asset_type.value} exceeds the {max_bytes // MB} MB limit"
            )
        return self


class AssetOut(AssetCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title_id: int
    created_at: datetime
