# Documentation Index

This directory provides a short map of the ELRAG codebase.

## Project Layout

`elrag/main.py` is the FastAPI entry point. It wires the application together, mounts the routers, and enforces bearer-token access for protected paths.

`elrag/api/` contains the HTTP surface. The auth router handles Google login and JWT issuance, while the other routers expose document, storage, vision, and agent endpoints.

The agent endpoint is a native FastAPI route at `POST /agent/run`. It supports JSON responses by default and SSE events when the request body includes `stream: true`.

`elrag/core/` contains the service layer. This is where the backend logic for OAuth, document workflows, storage orchestration, and related behavior lives.

`elrag/models/db/` defines the Scylla/Cassandra tables per feature. `elrag/schemas/json/` defines public request and response schemas, while `elrag/schemas/db/` defines internal database error context. The database bootstrap and table sync logic remain in `elrag/models/base.py`.

`elrag/lib/` wraps external integrations such as Google Cloud Storage, Vision, Document AI, Google Maps, and OpenTelemetry observability.

Public errors use a nested JSON format with stable error codes and request identifiers. Database and JSON/API errors are tracked separately in Google Cloud Monitoring.

`elrag/mcp/` exposes MCP tooling for the project, and `rpc-services/` contains the Rust RPC service scaffold.

## Local Development

For the local setup, start with `README.md` in the repository root. It contains the standard install, Scylla and Redis startup, API launch, and test commands.

## Testing

The Python test suite lives in `tests/`. Auth behavior, middleware behavior, and service wrappers are already covered there.
