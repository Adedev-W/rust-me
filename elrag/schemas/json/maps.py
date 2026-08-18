from pydantic import Field

from elrag.schemas.json.base import JsonSchemaBase


class GoogleMapsAutocompleteResponse(JsonSchemaBase):
    """Google Maps autocomplete response metadata."""

    input_text: str = Field(description="Autocomplete input text")
    language_code: str | None = Field(None, description="Optional language code")
    language_detection: str = Field(description="Detected input language")


class RouteRequest(JsonSchemaBase):
    """Google Maps route coordinate request."""

    origin: tuple[float, float] = Field(description="Origin latitude and longitude")
    destination: tuple[float, float] = Field(
        description="Destination latitude and longitude"
    )
