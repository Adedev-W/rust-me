from pydantic import Field

from elrag.schemas.json.base import JsonSchemaBase


class AuthenticatedUserResponse(JsonSchemaBase):
    """Authenticated user information returned by the API."""

    google_sub: str = Field(description="Google account subject identifier")
    email: str = Field(description="User email address")
    name: str | None = Field(None, description="User display name")
    picture: str | None = Field(None, description="User profile image URL")
    role: str = Field(description="Application role")


class AuthCallbackResponse(JsonSchemaBase):
    """Successful OAuth callback response."""

    access_token: str = Field(description="Application access token")
    token_type: str = Field(description="Access token type")
    expires_in: int = Field(description="Access token lifetime in seconds")
    user: AuthenticatedUserResponse


class AuthMeResponse(JsonSchemaBase):
    """Current authenticated user response."""

    user: AuthenticatedUserResponse
