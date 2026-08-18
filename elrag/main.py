import asyncio
import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from starlette.responses import Response
from opentelemetry import trace

from elrag.api.auth.auth import auth_api
from elrag.api.error_handling import build_error_response, register_error_handlers
from elrag.api.gcs import gcs_api
from elrag.api.docs import docs_api
from elrag.api.vision import vision_api
from elrag.api.agent import agent_api
from elrag.core.auth_be import (
    AuthConfigurationError,
    AuthenticationError,
    AuthorizationError,
    AuthorizationServiceBE,
    QuotaExceededError,
)
from elrag.core.quota import QuotaStoreUnavailableError
from elrag.mcp.server import mcp_app
from elrag.models.base import sync_all_tables
from elrag.lib.observability import (
    configure_observability,
    monotonic,
    record_error,
    record_request,
    shutdown_observability,
    validate_observability,
)
import elrag.models.db  # noqa: F401

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        validate_observability()
        await auth_service.check_quota_store()
        sync_all_tables()
        yield
    finally:
        try:
            await auth_service.close()
        finally:
            shutdown_observability()


app = FastAPI(lifespan=lifespan)
register_error_handlers(app)
auth_service = AuthorizationServiceBE()
PUBLIC_PATHS = {
    "/auth/login",
    "/auth/callback",
    "/docs",
    "/redoc",
    "/openapi.json",
}
NON_USAGE_PATHS = {"/docs", "/redoc", "/openapi.json"}


@app.middleware("http")
async def enforce_client_authorization(request: Request, call_next):
    path = request.url.path
    request.state.request_id = request.headers.get("x-request-id") or str(uuid4())
    should_record_usage = path not in NON_USAGE_PATHS
    started_at = monotonic()
    status_code = 500
    authenticated = False
    quota_consumed = False

    try:
        if path in PUBLIC_PATHS:
            response: Response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request.state.request_id
            return response

        bearer_token = _extract_bearer_token(request)
        if bearer_token is None:
            response = build_error_response(
                request,
                status_code=401,
                code="authentication_required",
                message="Authorization bearer token is required.",
            )
            _add_quota_headers(response, await _best_effort_quota_headers())
            status_code = response.status_code
            return response

        try:
            request.state.user = auth_service.authenticate_bearer_token(bearer_token)
            authenticated = True
            quota_limit, quota_remaining = await auth_service.consume_quota()
            quota_consumed = True
            headers = {
                "X-Global-Quota-Limit": str(quota_limit),
                "X-Global-Quota-Remaining": str(quota_remaining),
            }
        except AuthConfigurationError as exc:
            response = build_error_response(
                request,
                status_code=500,
                code="authentication_configuration_error",
                message="Authentication service is not configured.",
                exception=exc,
            )
            status_code = response.status_code
            return response
        except AuthenticationError as exc:
            response = build_error_response(
                request,
                status_code=401,
                code="authentication_error",
                message=str(exc),
                exception=exc,
            )
            _add_quota_headers(response, await _best_effort_quota_headers())
            status_code = response.status_code
            return response
        except AuthorizationError as exc:
            response = build_error_response(
                request,
                status_code=403,
                code="authorization_error",
                message=str(exc),
                exception=exc,
            )
            _add_quota_headers(response, await _best_effort_quota_headers())
            status_code = response.status_code
            return response
        except QuotaExceededError as exc:
            response = build_error_response(
                request,
                status_code=429,
                code="quota_exceeded",
                message=str(exc),
                exception=exc,
            )
            _add_quota_headers(response, await _best_effort_quota_headers())
            status_code = response.status_code
            return response
        except QuotaStoreUnavailableError as exc:
            response = build_error_response(
                request,
                status_code=503,
                code="quota_service_unavailable",
                message="Quota service is unavailable.",
                exception=exc,
            )
            status_code = response.status_code
            return response

        response = await call_next(request)
        status_code = response.status_code
        for key, value in headers.items():
            response.headers[key] = value
        response.headers["X-Request-ID"] = request.state.request_id
        return response
    except Exception as exc:
        status_code = 500
        if not getattr(request.state, "error_recorded", False):
            _record_unhandled_error(request, exc)
        span = trace.get_current_span()
        if span.is_recording():
            span.record_exception(exc)
        raise
    finally:
        if should_record_usage:
            scope = getattr(request, "scope", {})
            route = getattr(scope.get("route"), "path", path)
            try:
                record_request(
                    method=request.method,
                    route=route,
                    status_code=status_code,
                    duration_seconds=monotonic() - started_at,
                    authenticated=authenticated,
                    quota_consumed=quota_consumed,
                )
            except Exception:
                logger.exception("Failed to record request observability metrics")


async def _best_effort_quota_headers() -> dict[str, str]:
    try:
        return await asyncio.wait_for(auth_service.build_quota_headers(), timeout=1.0)
    except (QuotaStoreUnavailableError, asyncio.TimeoutError):
        return {}


def _add_quota_headers(response: Response, headers: dict[str, str]) -> None:
    for key, value in headers.items():
        response.headers[key] = value


def _record_unhandled_error(request: Request, exception: Exception) -> None:
    request.state.error_layer = "json"
    request.state.error_code = "internal_error"
    request.state.error_recorded = True
    route = getattr(request.scope.get("route"), "path", request.url.path)
    try:
        record_error(
            layer="json",
            code="internal_error",
            route=route,
            status_code=500,
        )
    except Exception:
        logger.exception("Failed to record unhandled error metric")


def _extract_bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization")
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip()


app.include_router(vision_api, prefix="/vision", tags=["Vision API"])
app.include_router(gcs_api, prefix="/gcs", tags=["GCS API"])
app.include_router(docs_api, prefix="/docs", tags=["Document AI API"])
app.include_router(auth_api, prefix="/auth", tags=["Auth API"])
app.include_router(agent_api)
app.mount("/mcp", mcp_app)
configure_observability(app)
