from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from opentelemetry import trace

from elrag.errors.api import ApiError, IntegrationError
from elrag.errors.database import DatabaseError
from elrag.lib.observability import record_error
from elrag.schemas.json.errors import ApiErrorDetail, ApiErrorResponse

logger = logging.getLogger(__name__)


def register_error_handlers(app: FastAPI) -> None:
    """Register the application's public error handlers."""

    app.add_exception_handler(ApiError, handle_api_error)
    app.add_exception_handler(DatabaseError, handle_database_error)
    app.add_exception_handler(IntegrationError, handle_integration_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(HTTPException, handle_http_exception)
    app.add_exception_handler(Exception, handle_unexpected_error)


async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
    return build_error_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def handle_database_error(request: Request, exc: DatabaseError) -> JSONResponse:
    return build_error_response(
        request,
        status_code=exc.status_code,
        code=exc.context.code,
        message=exc.public_message,
        layer="database",
        operation=exc.context.operation,
        exception=exc,
    )


async def handle_integration_error(
    request: Request,
    exc: IntegrationError,
) -> JSONResponse:
    return build_error_response(
        request,
        status_code=502,
        code=exc.code,
        message=exc.message,
        source=exc.source,
        exception=exc,
    )


async def handle_validation_error(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    details = [
        {
            "field": ".".join(str(item) for item in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]
    return build_error_response(
        request,
        status_code=422,
        code="validation_error",
        message="Request validation failed.",
        details=details,
        exception=exc,
    )


async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
    return build_error_response(
        request,
        status_code=exc.status_code,
        code="http_error",
        message=str(exc.detail),
        exception=exc,
    )


async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error")
    return build_error_response(
        request,
        status_code=500,
        code="internal_error",
        message="Internal server error.",
        exception=exc,
    )


def build_error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
    layer: str = "json",
    operation: str | None = None,
    source: str | None = None,
    exception: Exception | None = None,
) -> JSONResponse:
    request_id = _request_id(request)
    _record_error(
        request,
        layer=layer,
        code=code,
        status_code=status_code,
        operation=operation,
        source=source,
        exception=exception,
    )
    payload = ApiErrorResponse(
        error=ApiErrorDetail(
            code=code,
            message=message,
            details=details,
            request_id=request_id,
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(by_alias=True),
        headers={"X-Request-ID": request_id},
    )


def _request_id(request: Request) -> str:
    request_id = getattr(request.state, "request_id", None)
    if request_id is None:
        request_id = str(uuid4())
        request.state.request_id = request_id
    return request_id


def _record_error(
    request: Request,
    *,
    layer: str,
    code: str,
    status_code: int,
    operation: str | None,
    source: str | None,
    exception: Exception | None,
) -> None:
    request.state.error_layer = layer
    request.state.error_code = code
    request.state.error_recorded = True
    route = getattr(request.scope.get("route"), "path", request.url.path)
    try:
        record_error(
            layer=layer,
            code=code,
            route=route,
            status_code=status_code,
            operation=operation,
            source=source,
        )
    except Exception:
        logger.exception("Failed to record application error metric")

    span = trace.get_current_span()
    if not span.is_recording():
        return
    span.set_attribute("error.layer", layer)
    span.set_attribute("error.code", code)
    span.set_attribute("http.response.status_code", status_code)
    if operation:
        span.set_attribute("error.operation", operation)
    if source:
        span.set_attribute("error.source", source)
    if exception:
        span.record_exception(exception)
