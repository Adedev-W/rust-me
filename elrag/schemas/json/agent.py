from typing import Any

from pydantic import Field

from elrag.schemas.json.base import JsonSchemaBase


class AgentRunRequest(JsonSchemaBase):
    """Request to execute an agent run."""

    message: str = Field(min_length=1, max_length=10000, description="Agent message")
    session_id: str | None = Field(
        None,
        min_length=1,
        max_length=128,
        description="Optional agent session identifier",
    )
    stream: bool = Field(False, description="Whether to stream server-sent events")


class AgentRunResponse(JsonSchemaBase):
    """Non-streaming agent response."""

    run_id: str | None = Field(None, description="Agent run identifier")
    session_id: str | None = Field(None, description="Agent session identifier")
    content: Any = Field(description="Agent response content")
