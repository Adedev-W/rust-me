from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi import FastAPI

from elrag.api.agent import agent_api
from elrag.core.auth_be import AuthenticatedUser


class AgentApiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.app = FastAPI()
        self.app.include_router(agent_api)
        self.user = AuthenticatedUser(
            google_sub="google-sub-1",
            email="user@example.com",
            name="User Example",
            picture=None,
            role="user",
        )

        @self.app.middleware("http")
        async def set_authenticated_user(request, call_next):
            request.state.user = self.user
            return await call_next(request)

        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_json_run_returns_stable_response(self) -> None:
        output = SimpleNamespace(
            run_id="run-1",
            session_id="session-1",
            content="hasil pencarian",
        )

        with patch(
            "elrag.api.agent.gmaps_agent.run",
            new=AsyncMock(return_value=output),
        ) as run:
            response = await self.client.post(
                "/agent/run",
                json={"message": "cari restoran", "session_id": "session-1"},
            )

        self.assertEqual(200, response.status_code)
        run.assert_awaited_once_with(
            "cari restoran",
            user_id="google-sub-1",
            session_id="session-1",
        )
        self.assertEqual(
            {
                "runId": "run-1",
                "sessionId": "session-1",
                "content": "hasil pencarian",
            },
            response.json(),
        )

    async def test_stream_returns_public_sse_events(self) -> None:
        async def fake_stream(*args, **kwargs):
            yield SimpleNamespace(event="RunStarted", run_id="run-1", session_id="session-1")
            yield SimpleNamespace(
                event="RunContent",
                run_id="run-1",
                session_id="session-1",
                content="hasil",
            )
            yield SimpleNamespace(
                event="RunCompleted",
                run_id="run-1",
                session_id="session-1",
                content="hasil lengkap",
            )

        stream = MagicMock(side_effect=fake_stream)
        with patch("elrag.api.agent.gmaps_agent.stream", new=stream):
            response = await self.client.post(
                "/agent/run",
                json={"message": "cari restoran", "stream": True},
            )

        self.assertEqual(200, response.status_code)
        self.assertEqual("text/event-stream; charset=utf-8", response.headers["content-type"])
        self.assertIn("event: start", response.text)
        self.assertIn("event: delta", response.text)
        self.assertIn("event: complete", response.text)
        self.assertNotIn("RunContent", response.text)
        stream.assert_called_once_with(
            "cari restoran",
            user_id="google-sub-1",
            session_id=None,
        )

    async def test_provider_failure_returns_502(self) -> None:
        with patch(
            "elrag.api.agent.gmaps_agent.run",
            new=AsyncMock(side_effect=RuntimeError("provider failed")),
        ):
            response = await self.client.post(
                "/agent/run",
                json={"message": "cari restoran"},
            )

        self.assertEqual(502, response.status_code)
        self.assertEqual("agent_service_unavailable", response.json()["error"]["code"])
        self.assertEqual(
            "Agent service is unavailable.",
            response.json()["error"]["message"],
        )

    async def test_stream_failure_returns_public_error_event(self) -> None:
        async def failing_stream(*args, **kwargs):
            raise RuntimeError("provider failed")
            yield  # pragma: no cover

        with patch("elrag.api.agent.gmaps_agent.stream", new=failing_stream):
            response = await self.client.post(
                "/agent/run",
                json={"message": "cari restoran", "stream": True},
            )

        self.assertEqual(200, response.status_code)
        self.assertIn("event: error", response.text)
        self.assertIn("Agent service is unavailable.", response.text)

    async def test_request_requires_authentication(self) -> None:
        unauthenticated_app = FastAPI()
        unauthenticated_app.include_router(agent_api)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=unauthenticated_app),
            base_url="http://testserver",
        ) as client:
            response = await client.post(
                "/agent/run", json={"message": "cari restoran"}
            )

        self.assertEqual(401, response.status_code)

    async def test_empty_message_is_rejected(self) -> None:
        response = await self.client.post("/agent/run", json={"message": ""})

        self.assertEqual(422, response.status_code)


if __name__ == "__main__":
    unittest.main()
