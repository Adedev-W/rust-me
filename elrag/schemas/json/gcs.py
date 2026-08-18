from datetime import datetime

from pydantic import Field

from elrag.schemas.json.base import JsonSchemaBase


class GcsUploadResponse(JsonSchemaBase):
    """Google Cloud Storage upload response."""

    message: str = Field(description="Operation result message")
    cloud_storage_id: str | None = Field(None, description="Cloud storage record identifier")


class GcsFileListResponse(JsonSchemaBase):
    """List of objects in a Google Cloud Storage bucket."""

    data: list[str] = Field(description="Object names")


class GcsFileInfoResponse(JsonSchemaBase):
    """Metadata for one Google Cloud Storage object."""

    name: str
    size: int | None = None
    content_type: str | None = None
    updated: datetime | None = None


class GcsDownloadResponse(JsonSchemaBase):
    """Google Cloud Storage download response."""

    message: str = Field(description="Operation result message")
    success: bool = Field(description="Whether the download succeeded")
