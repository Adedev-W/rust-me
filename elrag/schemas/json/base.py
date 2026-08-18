from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class JsonSchemaBase(BaseModel):
    """Base model for public JSON request and response schemas."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        serialize_by_alias=True,
    )
