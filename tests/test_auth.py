from __future__ import annotations

import os
import unittest
from dataclasses import asdict
from datetime import datetime, timezone
from unittest.mock import patch

import httpx
import jwt
from fastapi import FastAPI

from elrag.api.auth.auth import auth_api
from elrag.core.auth_be import (
    AuthenticationError,
    AuthorizationError,
    AuthenticatedUser,
    AuthorizationServiceBE,
    OAuthSettings,
)


class FakeOAuthUser:
    created_user = None

    def __init__(
        self,
        *,
        google_sub: str = "google-sub-1",
        email: str = "user@example.com",
        name: str | None = "User Example",
        picture: str | None = "https://example.com/user.png",
        is_active: bool = False,
        role: str = "user",
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
        last_login_at: datetime | None = None,
    ) -> None:
        self.google_sub = google_sub
        self.email = email
        self.name = name
        self.picture = picture
        self.is_active = is_active
        self.role = role
        self.created_at = created_at
        self.updated_at = updated_at
        self.last_login_at = last_login_at
        self.saved = False

    @classmethod
    def create(cls, **kwargs):
        cls.created_user = cls(**kwargs)
        return cls.created_user

    def save(self) -> None:
        self.saved = True


def _settings() -> OAuthSettings:
    return OAuthSettings(
        google_client_id="google-client-id",
        google_client_secret="google-client-secret",
        jwt_secret="jwt-secret-with-at-least-32-bytes",
        redirect_uri=None,
        token_ttl_seconds=3600,
    )


class AuthorizationServiceTest(unittest.TestCase):
    def test_missing_config_raises_clear_error(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            service = AuthorizationServiceBE()

            with self.assertRaisesRegex(Exception, "Missing auth configuration"):
                _ = service.settings

    def test_new_google_user_is_created_active(self) -> None:
        claims = {
            "sub": "google-sub-1",
            "email": "user@example.com",
            "name": "User Example",
            "picture": "https://example.com/user.png",
        }
        service = AuthorizationServiceBE(settings=_settings())
        FakeOAuthUser.created_user = None

        with patch.object(service, "_get_user", return_value=None), patch(
            "elrag.core.auth_be.GoogleOAuthUser",
            FakeOAuthUser,
        ):
            user = service.get_or_create_user(claims)

        self.assertIs(user, FakeOAuthUser.created_user)
        self.assertTrue(user.is_active)
        self.assertEqual("user", user.role)

    def test_pkce_pair_generates_matching_challenge(self) -> None:
        service = AuthorizationServiceBE(settings=_settings())

        pair = service.create_pkce_pair()

        self.assertTrue(pair.code_verifier)
        self.assertTrue(pair.code_challenge)
        self.assertNotEqual(pair.code_verifier, pair.code_challenge)
        self.assertNotIn("=", pair.code_challenge)
        self.assertNotIn("+", pair.code_challenge)
        self.assertNotIn("/", pair.code_challenge)

    def test_authorization_url_includes_pkce_challenge(self) -> None:
        service = AuthorizationServiceBE(settings=_settings())

        url = service.build_authorization_url(
            "state-1",
            "http://localhost/auth/callback",
            "challenge-1",
        )

        self.assertIn("code_challenge=challenge-1", url)
        self.assertIn("code_challenge_method=S256", url)

    def test_active_user_gets_valid_jwt(self) -> None:
        user = FakeOAuthUser(is_active=True)
        service = AuthorizationServiceBE(settings=_settings())

        token = service.create_access_token(user)
        decoded = jwt.decode(
            token,
            "jwt-secret-with-at-least-32-bytes",
            algorithms=["HS256"],
            audience="elrag-api",
            issuer="elrag",
        )

        self.assertEqual(user.google_sub, decoded["sub"])
        self.assertEqual(user.email, decoded["email"])

        with patch.object(service, "_get_user", return_value=user):
            authenticated = service.authenticate_bearer_token(token)

        self.assertEqual(user.google_sub, authenticated.google_sub)
        self.assertEqual(user.email, authenticated.email)


class AuthRouterTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.app = FastAPI()
        self.app.include_router(auth_api, prefix="/auth")
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_invalid_state_callback_returns_400(self) -> None:
        self.client.cookies.set("elrag_oauth_state", "expected-state")
        self.client.cookies.set("elrag_oauth_pkce_verifier", "verifier-1")
        response = await self.client.get(
            "/auth/callback",
            params={"code": "code-1", "state": "wrong-state"},
        )

        self.assertEqual(400, response.status_code)
        self.assertEqual("oauth_state_invalid", response.json()["error"]["code"])
        self.assertEqual("OAuth state is invalid.", response.json()["error"]["message"])

    async def test_token_exchange_failure_returns_401(self) -> None:
        class FailingAuthService:
            def get_redirect_uri(self, fallback_redirect_uri: str) -> str:
                return fallback_redirect_uri

            async def exchange_authorization_code(self, code, redirect_uri, code_verifier):
                raise AuthenticationError("failed to exchange authorization code")

        with patch("elrag.api.auth.auth.auth_service", FailingAuthService()):
            self.client.cookies.set("elrag_oauth_state", "state-1")
            self.client.cookies.set("elrag_oauth_pkce_verifier", "verifier-1")
            response = await self.client.get(
                "/auth/callback",
                params={"code": "code-1", "state": "state-1"},
            )

        self.assertEqual(401, response.status_code)
        self.assertEqual("authentication_error", response.json()["error"]["code"])
        self.assertEqual(
            "failed to exchange authorization code",
            response.json()["error"]["message"],
        )

    async def test_inactive_user_callback_returns_403(self) -> None:
        class PendingAuthService:
            def get_redirect_uri(self, fallback_redirect_uri: str) -> str:
                return fallback_redirect_uri

            async def exchange_authorization_code(self, code, redirect_uri, code_verifier):
                return {"id_token": "google-id-token"}

            def verify_google_id_token(self, raw_id_token: str) -> dict:
                return {"sub": "google-sub-1", "email": "user@example.com"}

            def get_or_create_user(self, claims: dict) -> FakeOAuthUser:
                return FakeOAuthUser(is_active=False)

            def require_active_user(self, user: FakeOAuthUser) -> AuthenticatedUser:
                raise AuthorizationError("pending approval")

        with patch("elrag.api.auth.auth.auth_service", PendingAuthService()):
            self.client.cookies.set("elrag_oauth_state", "state-1")
            self.client.cookies.set("elrag_oauth_pkce_verifier", "verifier-1")
            response = await self.client.get(
                "/auth/callback",
                params={"code": "code-1", "state": "state-1"},
        )

        self.assertEqual(403, response.status_code)
        self.assertEqual("authorization_error", response.json()["error"]["code"])
        self.assertEqual("pending approval", response.json()["error"]["message"])

    async def test_active_user_callback_returns_bearer_token(self) -> None:
        user = AuthenticatedUser(
            google_sub="google-sub-1",
            email="user@example.com",
            name="User Example",
            picture=None,
            role="user",
        )

        class ActiveAuthService:
            settings = _settings()

            def get_redirect_uri(self, fallback_redirect_uri: str) -> str:
                return fallback_redirect_uri

            async def exchange_authorization_code(self, code, redirect_uri, code_verifier):
                return {"id_token": "google-id-token"}

            def verify_google_id_token(self, raw_id_token: str) -> dict:
                return {"sub": "google-sub-1", "email": "user@example.com"}

            def get_or_create_user(self, claims: dict) -> FakeOAuthUser:
                return FakeOAuthUser(is_active=True)

            def require_active_user(self, user_model: FakeOAuthUser) -> AuthenticatedUser:
                return user

            def record_login(self, user_model: FakeOAuthUser) -> None:
                user_model.last_login_at = datetime.now(timezone.utc)

            def create_access_token(self, user_model: FakeOAuthUser) -> str:
                return "app-jwt"

        with patch("elrag.api.auth.auth.auth_service", ActiveAuthService()):
            self.client.cookies.set("elrag_oauth_state", "state-1")
            self.client.cookies.set("elrag_oauth_pkce_verifier", "verifier-1")
            response = await self.client.get(
                "/auth/callback",
                params={"code": "code-1", "state": "state-1"},
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {
                "accessToken": "app-jwt",
                "tokenType": "bearer",
                "expiresIn": 3600,
                "user": {
                    "googleSub": user.google_sub,
                    "email": user.email,
                    "name": user.name,
                    "picture": user.picture,
                    "role": user.role,
                },
            },
            response.json(),
        )
        self.assertEqual("google-sub-1", response.json()["user"]["googleSub"])
        self.assertNotIn("google_sub", response.json()["user"])

    async def test_login_sets_state_and_pkce_cookies(self) -> None:
        response = await self.client.get("/auth/login", follow_redirects=False)

        self.assertEqual(307, response.status_code)
        location = response.headers["location"]
        self.assertIn("code_challenge=", location)
        self.assertIn("code_challenge_method=S256", location)
        self.assertIn("elrag_oauth_state=", response.headers.get("set-cookie", ""))
        self.assertIn("elrag_oauth_pkce_verifier=", response.headers.get("set-cookie", ""))


class MainMiddlewareTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        from elrag import main as main_module

        self.main_module = main_module
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=main_module.app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_request_without_bearer_token_returns_401(self) -> None:
        class FakeAuthService:
            async def build_quota_headers(self):
                return {
                    "X-Global-Quota-Limit": "1000",
                    "X-Global-Quota-Remaining": "1000",
                }

        with patch.object(self.main_module, "auth_service", FakeAuthService()):
            response = await self.client.get("/auth/me")

        self.assertEqual(401, response.status_code)
        self.assertEqual("authentication_required", response.json()["error"]["code"])
        self.assertEqual(
            "Authorization bearer token is required.",
            response.json()["error"]["message"],
        )

    async def test_invalid_bearer_token_returns_401(self) -> None:
        class FakeAuthService:
            async def build_quota_headers(self):
                return {"X-Global-Quota-Limit": "1000", "X-Global-Quota-Remaining": "1000"}

            def authenticate_bearer_token(self, raw_token: str):
                raise AuthenticationError("invalid bearer token")

        with patch.object(self.main_module, "auth_service", FakeAuthService()):
            response = await self.client.get(
                "/auth/me",
                headers={"Authorization": "Bearer invalid-token"},
            )

        self.assertEqual(401, response.status_code)
        self.assertEqual("authentication_error", response.json()["error"]["code"])
        self.assertEqual("invalid bearer token", response.json()["error"]["message"])

    async def test_inactive_user_returns_403(self) -> None:
        class FakeAuthService:
            async def build_quota_headers(self):
                return {"X-Global-Quota-Limit": "1000", "X-Global-Quota-Remaining": "1000"}

            def authenticate_bearer_token(self, raw_token: str):
                raise AuthorizationError("pending approval")

        with patch.object(self.main_module, "auth_service", FakeAuthService()):
            response = await self.client.get(
                "/auth/me",
                headers={"Authorization": "Bearer inactive-token"},
            )

        self.assertEqual(403, response.status_code)
        self.assertEqual("authorization_error", response.json()["error"]["code"])
        self.assertEqual("pending approval", response.json()["error"]["message"])

    async def test_active_user_can_access_me_with_quota_headers(self) -> None:
        user = AuthenticatedUser(
            google_sub="google-sub-1",
            email="user@example.com",
            name="User Example",
            picture=None,
            role="user",
        )

        class FakeAuthService:
            def authenticate_bearer_token(self, raw_token: str):
                return user

            async def consume_quota(self):
                return 1000, 999

        with patch.object(self.main_module, "auth_service", FakeAuthService()):
            response = await self.client.get(
                "/auth/me",
                headers={"Authorization": "Bearer valid-token"},
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {
                "user": {
                    "googleSub": user.google_sub,
                    "email": user.email,
                    "name": user.name,
                    "picture": user.picture,
                    "role": user.role,
                }
            },
            response.json(),
        )
        self.assertEqual("1000", response.headers["X-Global-Quota-Limit"])
        self.assertEqual("999", response.headers["X-Global-Quota-Remaining"])

    async def test_public_docs_are_accessible_without_bearer(self) -> None:
        response = await self.client.get("/docs")

        self.assertEqual(200, response.status_code)

    async def test_document_ai_docs_router_is_protected(self) -> None:
        response = await self.client.get("/docs/documentai/not-found")

        self.assertEqual(401, response.status_code)


if __name__ == "__main__":
    unittest.main()
