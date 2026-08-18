from typing import Any

from pydantic import Field

from elrag.schemas.json.base import JsonSchemaBase


class ApiErrorDetail(JsonSchemaBase):
    """Public details for one API error."""

    code: str = Field(description="Stable public error code")
    message: str = Field(description="Human-readable error message")
    details: Any | None = Field(None, description="Safe, optional error details")
    request_id: str = Field(description="Request identifier for support and tracing")


class ApiErrorResponse(JsonSchemaBase):
    """Standard public JSON error response."""

    error: ApiErrorDetail
