from typing import Any

from pydantic import Field

from elrag.schemas.json.base import JsonSchemaBase


class DocumentAiGcsResponse(JsonSchemaBase):
    """Document AI result for a Google Cloud Storage document."""

    id: str = Field(description="Document processing record identifier")
    gcs_uri: str | None = Field(None, description="Google Cloud Storage URI")
    metadata: dict[str, Any] | None = Field(None, description="Extracted document metadata")
    content: str | None = Field(None, description="Extracted document text")


class DocumentAiBytesResponse(JsonSchemaBase):
    """Document AI result for an uploaded document."""

    id: str = Field(description="Document processing record identifier")
    filename: str | None = Field(None, description="Uploaded filename")
    metadata: dict[str, Any] | None = Field(None, description="Extracted document metadata")
    content: str | None = Field(None, description="Extracted document text")


class DocumentAiGcsRequest(JsonSchemaBase):
    """Request data for a Google Cloud Storage document."""

    gcs_uri: str = Field(description="Google Cloud Storage URI")
    mime_type: str = Field(description="Document MIME type")


class DocumentAiBytesRequest(JsonSchemaBase):
    """Request data for an uploaded document."""

    files: bytes = Field(description="Document bytes")
    mime_type: str = Field(description="Document MIME type")
