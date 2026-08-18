from __future__ import annotations

import os
import secrets
import base64
import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt
from dotenv import load_dotenv
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from elrag.core.quota import (
    QuotaSnapshot,
    QuotaStoreUnavailableError,
    RedisQuotaStore,
)
from elrag.models.db.google_oauth_user import GoogleOAuthUserModel

GoogleOAuthUser = GoogleOAuthUserModel

load_dotenv()

GOOGLE_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_OAUTH_SCOPES = ("openid", "email", "profile")
JWT_ALGORITHM = "HS256"
JWT_AUDIENCE = "elrag-api"
JWT_ISSUER = "elrag"
OAUTH_STATE_COOKIE = "elrag_oauth_state"
OAUTH_PKCE_VERIFIER_COOKIE = "elrag_oauth_pkce_verifier"


class AuthConfigurationError(RuntimeError):
    """Raised when required authentication configuration is missing."""


class AuthenticationError(ValueError):
    """Raised when a token or OAuth response cannot be authenticated."""


class AuthorizationError(PermissionError):
    """Raised when an authenticated user is not allowed to access the API."""


class QuotaExceededError(PermissionError):
    """Raised when the global API quota has been exhausted."""


@dataclass(frozen=True)
class OAuthSettings:
    google_client_id: str
    google_client_secret: str
    jwt_secret: str
    redirect_uri: str | None
    token_ttl_seconds: int

    @classmethod
    def from_env(cls) -> OAuthSettings:
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET") or os.getenv("GOOGLE_SECRET_ID")
        jwt_secret = os.getenv("AUTH_JWT_SECRET")

        missing = [
            name
            for name, value in (
                ("GOOGLE_CLIENT_ID", client_id),
                ("GOOGLE_CLIENT_SECRET or GOOGLE_SECRET_ID", client_secret),
                ("AUTH_JWT_SECRET", jwt_secret),
            )
            if not value
        ]
        if missing:
            raise AuthConfigurationError(
                "Missing auth configuration: " + ", ".join(missing)
            )

        return cls(
            google_client_id=client_id,
            google_client_secret=client_secret,
            jwt_secret=jwt_secret,
            redirect_uri=os.getenv("GOOGLE_REDIRECT_URI"),
            token_ttl_seconds=_read_positive_int("AUTH_TOKEN_TTL_SECONDS", 3600),
        )


@dataclass(frozen=True)
class OAuthPKCEPair:
    code_verifier: str
    code_challenge: str


@dataclass(frozen=True)
class AuthenticatedUser:
    google_sub: str
    email: str
    name: str | None
    picture: str | None
    role: str


class AuthorizationServiceBE:
    def __init__(self, settings: OAuthSettings | None = None) -> None:
        self._settings = settings
        self.quota_limit = self._read_quota_limit()
        self.quota_store = RedisQuotaStore(limit=self.quota_limit)

    @property
    def settings(self) -> OAuthSettings:
        if self._settings is None:
            self._settings = OAuthSettings.from_env()
        return self._settings

    @staticmethod
    def _read_quota_limit() -> int:
        return _read_positive_int("GLOBAL_API_QUOTA_LIMIT", 1000)

    async def quota_snapshot(self) -> QuotaSnapshot:
        return await self.quota_store.snapshot()

    async def consume_quota(self) -> tuple[int, int]:
        snapshot = await self.quota_store.consume()
        if not snapshot.allowed:
            raise QuotaExceededError("global quota exhausted")
        return snapshot.limit, snapshot.remaining

    async def build_quota_headers(self) -> dict[str, str]:
        snapshot = await self.quota_snapshot()
        return {
            "X-Global-Quota-Limit": str(snapshot.limit),
            "X-Global-Quota-Remaining": str(snapshot.remaining),
        }

    async def check_quota_store(self) -> bool:
        return await self.quota_store.ping()

    async def close(self) -> None:
        await self.quota_store.close()

    def create_state(self) -> str:
        return secrets.token_urlsafe(32)

    def create_pkce_pair(self) -> OAuthPKCEPair:
        code_verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
        code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return OAuthPKCEPair(
            code_verifier=code_verifier,
            code_challenge=code_challenge,
        )

    def build_authorization_url(
        self,
        state: str,
        redirect_uri: str,
        code_challenge: str,
    ) -> str:
        settings = self.settings
        query = urlencode(
            {
                "client_id": settings.google_client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": " ".join(GOOGLE_OAUTH_SCOPES),
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
                "access_type": "offline",
                "include_granted_scopes": "true",
                "prompt": "consent",
            }
        )
        return f"{GOOGLE_AUTHORIZATION_URL}?{query}"

    def get_redirect_uri(self, fallback_redirect_uri: str) -> str:
        return self.settings.redirect_uri or fallback_redirect_uri

    async def exchange_authorization_code(
        self,
        code: str,
        redirect_uri: str,
        code_verifier: str,
    ) -> dict[str, Any]:
        settings = self.settings
        payload = {
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": code_verifier,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(GOOGLE_TOKEN_URL, data=payload)

        if response.status_code >= 400:
            raise AuthenticationError("failed to exchange authorization code")

        token_response = response.json()
        if "id_token" not in token_response:
            raise AuthenticationError("Google token response did not include id_token")
        return token_response

    def verify_google_id_token(self, raw_id_token: str) -> dict[str, Any]:
        request = google_requests.Request()
        try:
            claims = google_id_token.verify_oauth2_token(
                raw_id_token,
                request,
                audience=self.settings.google_client_id,
                clock_skew_in_seconds=10,
            )
        except Exception as exc:
            raise AuthenticationError("invalid Google id_token") from exc

        if not claims.get("sub") or not claims.get("email"):
            raise AuthenticationError("Google id_token is missing required claims")
        return claims

    def get_or_create_user(self, claims: dict[str, Any]) -> GoogleOAuthUserModel:
        google_sub = str(claims["sub"])
        now = datetime.now(timezone.utc)
        user = self._get_user(google_sub)
        if user is None:
            user = GoogleOAuthUser.create(
                google_sub=google_sub,
                email=str(claims["email"]),
                name=claims.get("name"),
                picture=claims.get("picture"),
                is_active=True,
                role="user",
                created_at=now,
                updated_at=now,
                last_login_at=None,
            )
            return user

        user.email = str(claims["email"])
        user.name = claims.get("name")
        user.picture = claims.get("picture")
        user.updated_at = now
        user.save()
        return user

    def require_active_user(self, user: GoogleOAuthUserModel) -> AuthenticatedUser:
        if not user.is_active:
            raise AuthorizationError("pending approval")
        return self._to_authenticated_user(user)

    def record_login(self, user: GoogleOAuthUserModel) -> None:
        user.last_login_at = datetime.now(timezone.utc)
        user.updated_at = user.last_login_at
        user.save()

    def create_access_token(self, user: GoogleOAuthUserModel) -> str:
        settings = self.settings
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=settings.token_ttl_seconds)
        payload = {
            "sub": user.google_sub,
            "email": user.email,
            "name": user.name,
            "picture": user.picture,
            "role": user.role,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
        }
        return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)

    def authenticate_bearer_token(self, raw_token: str) -> AuthenticatedUser:
        try:
            claims = jwt.decode(
                raw_token,
                self.settings.jwt_secret,
                algorithms=[JWT_ALGORITHM],
                audience=JWT_AUDIENCE,
                issuer=JWT_ISSUER,
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationError("invalid bearer token") from exc

        google_sub = claims.get("sub")
        if not google_sub:
            raise AuthenticationError("bearer token is missing subject")

        user = self._get_user(str(google_sub))
        if user is None:
            raise AuthorizationError("user not found")
        return self.require_active_user(user)

    @staticmethod
    def _get_user(google_sub: str) -> GoogleOAuthUserModel | None:
        return GoogleOAuthUser.objects(google_sub=google_sub).first()

    @staticmethod
    def _to_authenticated_user(user: GoogleOAuthUserModel) -> AuthenticatedUser:
        return AuthenticatedUser(
            google_sub=user.google_sub,
            email=user.email,
            name=user.name,
            picture=user.picture,
            role=user.role,
        )


def _read_positive_int(env_name: str, default: int) -> int:
    raw_value = os.getenv(env_name, str(default))
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return max(value, 1)
