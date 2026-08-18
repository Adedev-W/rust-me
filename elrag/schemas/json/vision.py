from pydantic import Field

from elrag.schemas.json.base import JsonSchemaBase


class VisionResponse(JsonSchemaBase):
    """Vision text extraction response."""

    id: str = Field(description="Vision processing record identifier")
    metadata: str | None = Field(None, description="Optional Vision metadata")
    content: str | None = Field(None, description="Detected text content")
