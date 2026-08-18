from __future__ import annotations

import unittest

from elrag.models.base import MODEL_REGISTRY
from elrag.schemas.db.errors import DatabaseErrorSchema
from elrag.schemas.json.agent import AgentRunRequest
from elrag.schemas.json.errors import ApiErrorResponse
from elrag.schemas.json.gcs import GcsUploadResponse


class SchemaArchitectureTest(unittest.TestCase):
    def test_all_database_models_are_registered(self) -> None:
        self.assertEqual(
            {
                "CloudStorageModel",
                "ControllerServiceModel",
                "DocumentAIModel",
                "GoogleOAuthUserModel",
                "VisionModel",
            },
            set(MODEL_REGISTRY),
        )

    def test_json_request_accepts_snake_case_and_serializes_camel_case(self) -> None:
        payload = AgentRunRequest(session_id="session-1", message="hello")

        self.assertEqual("session-1", payload.session_id)
        self.assertEqual(
            {
                "message": "hello",
                "sessionId": "session-1",
                "stream": False,
            },
            payload.model_dump(by_alias=True),
        )

        camel_payload = AgentRunRequest.model_validate(
            {"message": "hello", "sessionId": "session-2"}
        )
        self.assertEqual("session-2", camel_payload.session_id)

    def test_json_error_has_nested_public_shape(self) -> None:
        response = ApiErrorResponse(
            error={
                "code": "validation_error",
                "message": "Request validation failed.",
                "details": None,
                "request_id": "request-1",
            }
        )

        self.assertEqual(
            {
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed.",
                    "details": None,
                    "requestId": "request-1",
                }
            },
            response.model_dump(by_alias=True),
        )

    def test_database_error_schema_is_internal_and_typed(self) -> None:
        error = DatabaseErrorSchema(
            code="database_unavailable",
            operation="read",
            resource="vision",
            retryable=True,
        )

        self.assertEqual("database_unavailable", error.code)
        self.assertTrue(error.retryable)

    def test_legacy_schema_imports_are_compatibility_aliases(self) -> None:
        from elrag.models.schema import GCSUploadResponse

        self.assertIs(GCSUploadResponse, GcsUploadResponse)


if __name__ == "__main__":
    unittest.main()
