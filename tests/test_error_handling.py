from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from elrag.api.error_handling import build_error_response


class ErrorHandlingTest(unittest.TestCase):
    def test_build_error_response_records_json_error_and_request_id(self) -> None:
        request = SimpleNamespace(
            state=SimpleNamespace(request_id="request-1"),
            scope={"route": SimpleNamespace(path="/example")},
            url=SimpleNamespace(path="/example"),
        )

        with patch("elrag.api.error_handling.record_error") as record_error:
            response = build_error_response(
                request,
                status_code=422,
                code="validation_error",
                message="Request validation failed.",
            )

        self.assertEqual(422, response.status_code)
        self.assertEqual("request-1", response.headers["X-Request-ID"])
        self.assertEqual(
            {
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed.",
                    "details": None,
                    "requestId": "request-1",
                }
            },
            response.body and __import__("json").loads(response.body),
        )
        record_error.assert_called_once_with(
            layer="json",
            code="validation_error",
            route="/example",
            status_code=422,
            operation=None,
            source=None,
        )


if __name__ == "__main__":
    unittest.main()
