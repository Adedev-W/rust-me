from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse

from elrag.api.error_handling import build_error_response
from elrag.lib.agents import GmapsAgent
from elrag.schemas.json.agent import AgentRunRequest, AgentRunResponse

logger = logging.getLogger(__name__)

agent_api = APIRouter(prefix="/agent", tags=["Agent"])
gmaps_agent = GmapsAgent()


@agent_api.post("/run", response_model=None)
async def run_agent(
    payload: AgentRunRequest,
    request: Request,
) -> AgentRunResponse | JSONResponse | StreamingResponse:
    user = getattr(request.state, "user", None)
    user_id = getattr(user, "google_sub", None)
    if not user_id:
        return build_error_response(
            request,
            status_code=401,
            code="authentication_required",
            message="Authenticated user is required.",
        )

    if payload.stream:
        return StreamingResponse(
            _stream_agent_response(
                payload.message,
                user_id=user_id,
                session_id=payload.session_id,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    try:
        output = await gmaps_agent.run(
            payload.message,
            user_id=user_id,
            session_id=payload.session_id,
        )
    except Exception as exc:
        logger.exception("Agent run failed")
        return build_error_response(
            request,
            status_code=502,
            code="agent_service_unavailable",
            message="Agent service is unavailable.",
            exception=exc,
        )

    return AgentRunResponse(
        run_id=getattr(output, "run_id", None),
        session_id=getattr(output, "session_id", payload.session_id),
        content=jsonable_encoder(getattr(output, "content", output)),
    )


async def _stream_agent_response(
    message: str,
    *,
    user_id: str,
    session_id: str | None,
) -> AsyncIterator[str]:
    try:
        async for event in gmaps_agent.stream(
            message,
            user_id=user_id,
            session_id=session_id,
        ):
            event_name, data = _to_public_stream_event(event, session_id=session_id)
            if event_name is not None:
                yield _format_sse(event_name, data)
    except Exception:
        logger.exception("Agent stream failed")
        yield _format_sse(
            "error",
            {
                "error": {
                    "code": "agent_service_unavailable",
                    "message": "Agent service is unavailable.",
                }
            },
        )


def _to_public_stream_event(
    event: Any,
    *,
    session_id: str | None,
) -> tuple[str | None, dict[str, Any]]:
    event_type = getattr(event, "event", "")
    data = {
        "run_id": getattr(event, "run_id", None),
        "session_id": getattr(event, "session_id", None) or session_id,
    }

    if event_type == "RunStarted":
        return "start", data
    if event_type == "RunContent":
        data["content"] = jsonable_encoder(getattr(event, "content", None))
        return "delta", data
    if event_type == "RunCompleted":
        data["content"] = jsonable_encoder(getattr(event, "content", None))
        return "complete", data
    if event_type == "RunError":
        data["error"] = {
            "code": "agent_service_unavailable",
            "message": "Agent service is unavailable.",
        }
        return "error", data
    return None, data


def _format_sse(event_name: str, data: dict[str, Any]) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"
