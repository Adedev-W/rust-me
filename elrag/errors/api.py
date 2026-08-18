from typing import Any


class ApiError(Exception):
    """Expected error that can be returned safely to an API client."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


class IntegrationError(RuntimeError):
    """Expected failure from an external integration."""

    def __init__(self, *, source: str, code: str, message: str) -> None:
        super().__init__(message)
        self.source = source
        self.code = code
        self.message = message
