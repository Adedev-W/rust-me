from pydantic import BaseModel, ConfigDict


class DatabaseSchemaBase(BaseModel):
    """Base model for internal database DTOs."""

    model_config = ConfigDict(serialize_by_alias=False)
