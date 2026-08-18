# ELRAG

![ELRAG logo](elrag_icon.png)

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.138.1-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Rust](https://img.shields.io/badge/Rust-Backend-000000?logo=rust&logoColor=white)](https://www.rust-lang.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

ELRAG is a backend platform for document processing, vision tasks, cloud storage workflows, and API orchestration. It combines a FastAPI service layer, Scylla-backed models, Google Cloud integrations, an MCP server, and a Rust RPC scaffold into one codebase.

The project is aimed at teams that need a practical AI-oriented backend rather than a demo app. The Python API exposes the service surface, the database model layer persists shared state, and the supporting libraries wrap Google services such as Document AI, Vision, and Cloud Storage.

## What It Includes

ELRAG is organized around a small set of backend responsibilities. The API package exposes routes for auth, document extraction, GCS operations, vision, and agent workflows. The database model layer contains feature-level Scylla/Cassandra tables, while `schemas/` contains JSON and database error schemas. The `lib/` modules wrap the external services used by the API. The `mcp/` package exposes MCP tooling, while `rpc-services/` contains the Rust RPC service skeleton referenced by the project.

## Quick Start

Install the Python dependencies first:

```bash
.venv/bin/python -m pip install -r requirements.txt
```

Start ScyllaDB locally:

```bash
docker compose up -d
```

Run the API:

```bash
.venv/bin/python -m uvicorn elrag.main:app --reload --port 8080
```

Build the Rust RPC service if you need it:

```bash
cd rpc-services
cargo build
```

## Architecture

The FastAPI application lives in `elrag/main.py`. It mounts the public API routers, enforces bearer-token authorization, and synchronizes registered Scylla tables on startup. Route modules live under `elrag/api/`, with `auth.py`, `docs.py`, `gcs.py`, `vision.py`, and `agent.py` covering the main application surfaces.

Business logic sits in `elrag/core/`. This layer contains the service implementations that handle OAuth, document workflows, cloud storage operations, and vision-related logic. Database models are split by feature under `elrag/models/db/`, JSON schemas are split by feature under `elrag/schemas/json/`, and `elrag/models/base.py` manages connection and synchronization.

The repository also includes `elrag/mcp/` for MCP exposure and `rpc-services/` for a separate Rust RPC component. Those pieces are part of the codebase layout, even if you only use the Python API in day-to-day development.

## Authentication

Authentication uses Google OAuth with an authorization-code flow. On successful sign-in, ELRAG creates or refreshes a `google_oauth_user` record, then issues an application JWT for API access. New users are auto-provisioned as active accounts, and subsequent requests are authorized through the bearer token middleware in `elrag/main.py`.

Required environment variables for auth are `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` or `GOOGLE_SECRET_ID`, and `AUTH_JWT_SECRET`. Optional settings include `GOOGLE_REDIRECT_URI`, `AUTH_TOKEN_TTL_SECONDS`, and `GLOBAL_API_QUOTA_LIMIT`.

The quota counter is shared through Redis. Set `REDIS_URL` when Redis is not running at `redis://localhost:6379/0`. The counter is atomic per UTC day and does not fall back to process memory.

The agent API is implemented with native FastAPI routes. Use `POST /agent/run` with a required `message`, an optional `session_id`, and optional `stream: true` for SSE output. The authenticated JWT subject is used as the agent user identity.

## Protected API Test Client

The repository includes `client.py` for protected API smoke tests. It derives the API base URL from `API_BASE_URL` or `GOOGLE_REDIRECT_URI`, so changing the ngrok URL in `.env` updates the client automatically.

Start the API with the URL configured in `.env`, then save an OAuth token:

```bash
.venv/bin/python client.py login
```

The browser must complete the Google OAuth flow. Paste the `access_token` or the full JSON response shown by `/auth/callback`; the token is saved to `.api_token.json`, which is ignored by Git.

Run read-only protected checks:

```bash
.venv/bin/python client.py smoke
```

Run upload and provider checks explicitly:

```bash
API_TEST_AGENT_MESSAGE="Cari satu restoran untuk meeting di Jakarta" \
.venv/bin/python client.py run-all --verbose
```

Set `API_TEST_FILE`, `API_TEST_VISION_FILE`, `API_TEST_BLOB_NAME`, `API_TEST_DOCUMENT_ID`, or `API_TEST_VISION_ID` in `.env` when testing specific fixtures or persisted records.

## Codebase Map

The repository is small enough to navigate without a large docs tree. The most useful entry points are:

`elrag/main.py` for application startup and request authorization.
`elrag/api/` for HTTP endpoints.
`elrag/core/` for service-layer logic.
`elrag/models/db/` for feature-level Scylla models and `elrag/schemas/` for JSON and database error schemas.
`elrag/lib/` for Google Cloud and service wrappers.
`tests/` for the current automated coverage.
`scripts/init-scylla.sh` for local Scylla initialization.
`rpc-services/` for the Rust RPC project.

For a compact documentation index, see [docs/README.md](docs/README.md).

## Configuration

The default Scylla contact point is `127.0.0.1` and the default keyspace is `production`. Google Cloud helpers expect standard credentials such as `GOOGLE_APPLICATION_CREDENTIALS`.

Production observability uses OpenTelemetry. Set `GOOGLE_CLOUD_PROJECT`, provide Application Default Credentials, and keep `OTEL_ENABLED=true`. The service account needs Monitoring Metric Writer and Cloud Trace Writer access. `OTEL_SERVICE_NAME`, `OTEL_SERVICE_VERSION`, `DEPLOYMENT_ENVIRONMENT`, `OTEL_TRACE_SAMPLING_RATIO`, and `OTEL_METRIC_EXPORT_INTERVAL_MS` are optional tuning settings.

Application errors use a nested JSON object under `error`. Database and JSON/API errors are exported through separate metrics named `elrag.database.error.count` and `elrag.json.error.count`. Responses use lower camel case such as `cloudStorageId`; requests accept both snake case and camel case.

For local OAuth development, you should also set the Google auth values above and ensure the redirect URI matches the running FastAPI instance. In production, the callback URL should be registered in Google Cloud Console and the app should be deployed behind HTTPS.

## Testing

The repository currently uses `pytest` for the Python suite.

```bash
OTEL_ENABLED=false .venv/bin/python -m pytest
```

To verify atomic quota behavior against the local Compose Redis service:

```bash
RUN_REDIS_INTEGRATION_TESTS=1 .venv/bin/python -m pytest tests/test_quota.py
```

The existing tests cover auth behavior, middleware enforcement, Redis quota concurrency, OpenTelemetry request outcomes, and the Google Maps service wrapper.

## License

ELRAG is released under the MIT License. See [LICENSE](LICENSE) for details.
