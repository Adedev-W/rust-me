from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, RedirectResponse

from elrag.api.error_handling import build_error_response
from elrag.core.auth_be import (
    AuthConfigurationError,
    AuthenticationError,
    AuthorizationError,
    AuthorizationServiceBE,
    OAUTH_PKCE_VERIFIER_COOKIE,
    OAUTH_STATE_COOKIE,
)
from elrag.errors.api import ApiError
from elrag.schemas.json.auth import (
    AuthCallbackResponse,
    AuthMeResponse,
    AuthenticatedUserResponse,
)

auth_api = APIRouter()
auth_service = AuthorizationServiceBE()


@auth_api.get("/login")
async def login(request: Request) -> RedirectResponse:
    try:
        state = auth_service.create_state()
        pkce_pair = auth_service.create_pkce_pair()
        redirect_uri = auth_service.get_redirect_uri(
            str(request.url_for("google_oauth_callback"))
        )
        authorization_url = auth_service.build_authorization_url(
            state,
            redirect_uri,
            pkce_pair.code_challenge,
        )
    except AuthConfigurationError as exc:
        return build_error_response(
            request,
            status_code=500,
            code="authentication_configuration_error",
            message="Authentication service is not configured.",
            exception=exc,
        )

    response = RedirectResponse(authorization_url, status_code=307)
    secure_cookie = _cookie_secure(request)
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        state,
        max_age=600,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        path="/auth",
    )
    response.set_cookie(
        OAUTH_PKCE_VERIFIER_COOKIE,
        pkce_pair.code_verifier,
        max_age=600,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        path="/auth",
    )
    return response


@auth_api.get("/callback", name="google_oauth_callback")
async def callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> JSONResponse:
    if error:
        return _state_clearing_error_response(
            request,
            ApiError(
                status_code=400,
                code="oauth_provider_error",
                message="Google OAuth returned an error.",
            ),
        )

    expected_state = request.cookies.get(OAUTH_STATE_COOKIE)
    code_verifier = request.cookies.get(OAUTH_PKCE_VERIFIER_COOKIE)
    if (
        not code
        or not state
        or not expected_state
        or not code_verifier
        or state != expected_state
    ):
        return _state_clearing_error_response(
            request,
            ApiError(
                status_code=400,
                code="oauth_state_invalid",
                message="OAuth state is invalid.",
            ),
        )

    redirect_uri = auth_service.get_redirect_uri(
        str(request.url_for("google_oauth_callback"))
    )

    try:
        token_response = await auth_service.exchange_authorization_code(
            code,
            redirect_uri,
            code_verifier,
        )
        claims = auth_service.verify_google_id_token(token_response["id_token"])
        user = auth_service.get_or_create_user(claims)
        auth_user = auth_service.require_active_user(user)
        auth_service.record_login(user)
        access_token = auth_service.create_access_token(user)
    except AuthConfigurationError as exc:
        return _state_clearing_error_response(
            request,
            ApiError(
                status_code=500,
                code="authentication_configuration_error",
                message="Authentication service is not configured.",
                details=None,
            ),
        )
    except AuthenticationError as exc:
        return _state_clearing_error_response(
            request,
            ApiError(
                status_code=401,
                code="authentication_error",
                message=str(exc),
            ),
        )
    except AuthorizationError as exc:
        return _state_clearing_error_response(
            request,
            ApiError(
                status_code=403,
                code="authorization_error",
                message=str(exc),
            ),
        )

    response = JSONResponse(
        status_code=200,
        content=AuthCallbackResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=auth_service.settings.token_ttl_seconds,
            user=AuthenticatedUserResponse(**asdict(auth_user)),
        ).model_dump(by_alias=True),
    )
    return _clear_oauth_cookies(response)


@auth_api.get("/me")
async def me(request: Request) -> JSONResponse:
    user = getattr(request.state, "user", None)
    if user is None:
        return build_error_response(
            request,
            status_code=401,
            code="authentication_required",
            message="Authentication is required.",
        )
    return JSONResponse(
        status_code=200,
        content=AuthMeResponse(
            user=AuthenticatedUserResponse(**asdict(user))
        ).model_dump(by_alias=True),
    )


def _state_clearing_error_response(request: Request, error: ApiError) -> JSONResponse:
    return _clear_oauth_cookies(
        build_error_response(
            request,
            status_code=error.status_code,
            code=error.code,
            message=error.message,
            details=error.details,
            exception=error,
        )
    )


def _clear_oauth_cookies(response: JSONResponse) -> JSONResponse:
    response.delete_cookie(OAUTH_STATE_COOKIE)
    response.delete_cookie(OAUTH_PKCE_VERIFIER_COOKIE)
    return response


def _cookie_secure(request: Request) -> bool:
    setting = request.headers.get("x-forwarded-proto")
    if setting:
        return setting.split(",")[0].strip().lower() == "https"
    return request.url.scheme == "https"
