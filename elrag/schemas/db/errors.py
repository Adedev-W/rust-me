from pydantic import Field

from elrag.schemas.json.base import JsonSchemaBase


class DatabaseErrorSchema(JsonSchemaBase):
    """Internal context describing a database failure."""

    code: str = Field(description="Stable database error code")
    operation: str = Field(description="Database operation that failed")
    resource: str = Field(description="Database resource involved in the failure")
    retryable: bool = Field(description="Whether retrying the operation may succeed")
