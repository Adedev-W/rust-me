from elrag.schemas.db.errors import DatabaseErrorContext


class DatabaseError(RuntimeError):
    """Base error for database and database serialization failures."""

    public_message = "Database operation failed."
    status_code = 500

    def __init__(self, context: DatabaseErrorContext, cause: Exception | None = None) -> None:
        super().__init__(context.code)
        self.context = context
        self.cause = cause


class DatabaseUnavailableError(DatabaseError):
    """Raised when the database cannot be reached or used."""

    public_message = "Database service is unavailable."
    status_code = 503


class DatabaseSerializationError(DatabaseError):
    """Raised when a stored value cannot be converted to an API value."""

    public_message = "Database data could not be serialized."
    status_code = 500
