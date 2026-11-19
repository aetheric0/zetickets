# System architecture overview

## Current architecture

Zetickets is a Python 3.14 FastAPI application using Pydantic settings and schemas, SQLAlchemy 2.x async sessions, PostgreSQL through `asyncpg`, and Alembic for schema revisions. The application entry point is [`app/main.py`](../../app/main.py); configuration is in [`app/core/config.py`](../../app/core/config.py); ORM models are in [`app/models/`](../../app/models/); schemas are in [`app/schemas/`](../../app/schemas/); services are in [`app/services/`](../../app/services/).

The runtime currently exposes `GET /health` and FastAPI's generated documentation endpoints. `app/api/v1/api.py` composes authentication and user routers, but `app/main.py` does not include that router. Event, ticket and order endpoint modules are also not included by the v1 router. They are implementation modules, not currently available public API routes. See [`app/api/v1/api.py`](../../app/api/v1/api.py), [`app/api/v1/endpoints/`](../../app/api/v1/endpoints/) and [`app/main.py`](../../app/main.py).

The order service is the only business service currently present. It performs reservation creation, cancellation and expiry cleanup. Payment failure recording is explicitly disabled until trusted provider verification is implemented; no caller-supplied outcome can release inventory. There is no provider client, payment-success transition, webhook handler or scheduler. The Phase 2 PostgreSQL integration module documents the tested database behavior, but does not make those unregistered endpoints available.

## Runtime flow

```text
HTTP request
  -> FastAPI application (currently health route only)
  -> endpoint module (not mounted for v1 today)
  -> AsyncSession dependency
  -> SQLAlchemy ORM / PostgreSQL
```

Phase 3 should keep provider HTTP handling in adapters and payment lifecycle transitions in a service layer. A webhook should not create an order transition directly from a request payload. It should authenticate the delivery, bind it to a persisted payment attempt, verify the transaction with the provider as required, and then invoke an idempotent domain operation.

## Persistence and migrations

Alembic revisions are under [`alembic/versions/`](../../alembic/versions/). The complete chain was run on a fresh disposable PostgreSQL 18.6 database during Phase 2 verification and ORM metadata matched the resulting schema. Compatibility with an existing application database remains unverified. Never use the development migration command against an unknown or persistent database; see the [README database precautions](../../README.md#database-and-migrations).

## Architecture gaps

- The v1 API router is not mounted in the FastAPI application.
- JWT creation and validation use the same required `JWT_SECRET` (`SecretStr`, minimum 32 characters) and non-empty `ALGORITHM`; settings validation fails at startup when either is absent/invalid. Existing deployments using only `SECRET_KEY` must configure `JWT_SECRET` explicitly. Broader authorization/ownership hardening remains. See [`app/core/config.py`](../../app/core/config.py), [`app/core/security.py`](../../app/core/security.py) and [`app/core/deps.py`](../../app/core/deps.py).
- Endpoint modules contain authorization and response-handling defects that need security/API phases, not changes in this documentation-only milestone.
- There is no payment-attempt persistence model or webhook/reconciliation infrastructure.
- Docker Compose describes PostgreSQL and API services but not Redis. The API command runs migrations at container startup, and the database service uses a persistent named volume. Neither compose behavior nor a production deployment has been verified here.
