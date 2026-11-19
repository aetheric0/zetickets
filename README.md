# Zetickets

Zetickets is an early-stage backend for event, ticket-tier, reservation and order management. The project is being hardened in five engineering phases before payments or production deployment are introduced.

> **Status:** Phases 1 and 2 have repository-level and isolated PostgreSQL verification. Phase 3 Package 1 security foundation and Package 2 payment persistence are implemented and verified on a fresh disposable PostgreSQL 18.6 cluster. Provider integration and payment behavior have not started. The runtime currently exposes only `GET /health`. This project is not production-ready.

## Feature status

| Capability | Status |
|---|---|
| Canonical SQLAlchemy models, Pydantic compatibility and Alembic revisions | Implemented; migration chain exercised on a fresh disposable PostgreSQL 18.6 database. Existing-database upgrade compatibility remains unverified. |
| Transactional reservation, persisted quantity/expiry, inventory locking, cancellation, expiry and idempotency | Implemented in the order service and verified by database-independent tests plus a disposable PostgreSQL integration suite. |
| User authentication and user/event/ticket/order endpoint modules | Code exists, but routes are not mounted in the application. JWT signing/verification now share validated `JWT_SECRET` configuration; broader authorization defects remain. |
| Payment-attempt, webhook receipt, refund and reconciliation persistence | Implemented in Package 2 and verified on a fresh disposable PostgreSQL cluster; no provider code, trusted payment transition or ticket fulfillment from payment exists. |
| Paystack integration, provider verification, webhook endpoint, refund execution, reconciliation worker and organizer payouts | Planned for later Phase 3 packages; none implemented. |
| Deployment, CI and production operations | Deferred and unverified. |

## Technology stack

- Python 3.14 or newer (per `pyproject.toml`)
- FastAPI and Pydantic Settings / Pydantic 2
- SQLAlchemy 2.x async ORM and `asyncpg`
- PostgreSQL and Alembic
- JWT (`python-jose`) and `pwdlib`/bcrypt for password hashing
- `uv` for dependency and environment management
- Docker and Docker Compose files are present, but deployment has not been validated

There is no payment SDK integration or Redis dependency in the current project dependency list.

## Architecture

The application is structured as a FastAPI HTTP boundary, Pydantic request/response schemas, SQLAlchemy ORM models, async database sessions, service-layer business operations and Alembic migrations. See [system architecture](docs/architecture/system-overview.md) and [domain model](docs/architecture/domain-model.md).

The running application is defined in [`app/main.py`](app/main.py), which currently registers only `GET /health`. [`app/api/v1/api.py`](app/api/v1/api.py) composes authentication and user routers, but that router is not included in `app.main`; event, ticket and order endpoint modules are also not wired into the v1 router. Therefore endpoint modules described in source are not currently exposed routes.

### Repository structure

```text
.
├── app/
│   ├── api/v1/endpoints/   # Endpoint modules; not all are mounted
│   ├── core/               # Settings, authentication and request dependencies
│   ├── models/             # SQLAlchemy entities and enums
│   ├── schemas/            # Pydantic contracts
│   ├── services/           # Transactional order operations
│   ├── test_*.py           # Phase-focused tests
│   └── main.py             # FastAPI app; currently health route only
├── alembic/versions/       # Initial and forward schema revisions
├── docs/                   # Roadmap, ADRs, architecture, security and post-mortems
├── Dockerfile
├── docker-compose.yml
├── alembic.ini
├── pyproject.toml
├── requirements.txt
└── uv.lock
```

## Domain concepts and relationships

- A **User** can own events and orders and may have one **OrganizerProfile**.
- An **Event** belongs to an organizer and has **TicketType** tiers.
- A **TicketType** records a price, total capacity, reserved/sold counters and activity state.
- An **Order** belongs to a user, optionally references a ticket type for legacy compatibility, and can have multiple **Ticket** rows.
- Each **Ticket** references an order and ticket type.
- Each order can have multiple **PaymentAttempt** records. A separate **PaymentFulfillment** claim can associate only one successful attempt with an order; payment persistence does not itself issue tickets or prove provider verification.
- **WebhookEvent** records retain a digest and bounded receipt/processing metadata, not raw webhook payloads or credentials. **Refund** records and **ReconciliationRecord** observations remain associated with their payment attempt; reconciliation may also refer to a refund.

New orders snapshot quantity, unit price and expiry. Historical quantities, prices, currencies and expiry that were never recorded remain unknown; the migrations do not manufacture those values. Current money fields use `Decimal`/`Numeric`, but reservation code leaves order currency null. The accepted payment policy is KES-only for initial transactions; checkout remains unavailable until each order has an authoritative immutable amount/currency snapshot in the required representation.

See [domain model](docs/architecture/domain-model.md) for nullability and relationships.

## Reservation and order lifecycle

The Phase 2 service validates quantity and an idempotency key, locks the ticket-type row, checks inventory, increments reserved quantity and writes a pending order and reserved ticket rows in one transaction. New reservations snapshot the ticket price and expire after ten minutes. Cancellation, expiry cleanup and internal verified-failure handling release reserved inventory transactionally and idempotently.

There is no successful-payment transition. The existing checkout endpoint code returns HTTP 409, and the endpoint module is not mounted. The former constructible `VerifiedPaymentFailure` value and its inventory-releasing service path have been removed. Payment failure recording now fails closed until an application-owned provider verification flow is implemented; it does not alter order or inventory state.

See [reservation lifecycle](docs/architecture/reservation-lifecycle.md) and [Phase 2 execution log](docs/phase-2-execution-log.md).

## Inventory and transactions

PostgreSQL row locks and database constraints protect reservation and release operations. Phase 2 tests exercised locking, contention, rollback, idempotency and schema parity against a fresh disposable PostgreSQL 18.6 database. Mocks and SQLite are not substitutes for PostgreSQL transaction behavior. No existing application database was used for verification; compatibility with existing database contents remains unverified.

Expiry cleanup is a callable bounded service using `SKIP LOCKED`; no scheduler invokes it today. The order router is not registered.

## Payment architecture direction

The accepted architecture separates order/reservation, payment attempt, ticket fulfillment and refund lifecycles behind a provider-neutral adapter. Paystack is the initial provider; KES is the only initially enabled currency, with future currency extensibility. The platform collects/reconciles customer payments and pays organizers separately. A verified late success after expiry/ineligible inventory is refunded; no ticket is issued without valid inventory. Webhooks are authenticated signals followed by server-side transaction verification; they are not standalone proof. Payment success is not proof that funds cleared or an organizer was paid.

Payment persistence is implemented as schema only. Paystack integration, provider verification, refund execution, reconciliation behavior, organizer accounting and payouts are not implemented. Account access, live eligibility, enabled channels, settlement configuration, fees, refund capabilities and merchant terms are not independently verified for Zetickets. Daraja is a future option and is outside initial scope. Commission, tax, reserves, fee allocation and payout timing remain undefined.

Read the [provider comparison](docs/payments/provider-comparison.md), [payment architecture](docs/architecture/payment-architecture.md), [payment lifecycle](docs/payments/lifecycle-and-reconciliation.md), [Phase 3 implementation plan](docs/phase-3-implementation-plan.md) and [ADRs](docs/decisions/README.md).

## Security principles and current limitations

- Never trust a browser redirect, caller-supplied status or webhook JSON as proof of payment.
- Keep provider credentials external; separate test and live environments; do not log secrets or card data.
- Enforce authentication, ownership and role checks at the service boundary.
- Verify payment amount and currency against immutable server-side snapshots.
- Make webhook, payment, refund and fulfillment transitions idempotent and auditable.
- Preserve unknown historical facts and minimize retained personal/payment data.

JWT creation and validation now use the same canonical `JWT_SECRET`, which is required and must contain at least 32 characters; `ALGORITHM` is also required and non-empty. Missing/invalid configuration fails during settings validation, and the secret is represented as a Pydantic `SecretStr`. Existing deployments that configure only `SECRET_KEY` must set `JWT_SECRET` before starting the application; values are not copied automatically. Broader authentication, ownership and role checks still require hardening. These features must not be treated as production-ready.

## Database and migrations

PostgreSQL is the authoritative transaction and migration target. The migration chain preserves the initial and Phase 1/2 revisions and adds forward revision `c7e2a4b19d60` for payment persistence. Fresh-chain PostgreSQL 18.6 upgrade, metadata parity, Alembic check and empty downgrade/re-upgrade passed; upgrades against a populated, existing or production database are not verified.

For local development, first configure a dedicated disposable PostgreSQL database and the variables below. Review the target identity and migration plan before running:

```bash
uv run alembic history
uv run alembic upgrade head
```

`upgrade head` changes the selected database schema. Never run it against an unknown, shared, persistent or production database. The Compose API service runs migrations at startup and its PostgreSQL service has a persistent named volume; do not start it against data that may matter. Do not use `docker compose down -v` unless intentionally deleting the Compose database volume and its contents.

## Local development setup

1. Install Python 3.14+ and [`uv`](https://docs.astral.sh/uv/).
2. Clone this repository and create a local `.env` using your own safe development configuration. Do not copy credentials into documentation or Git.
3. Provision a dedicated disposable PostgreSQL database. The application uses the async PostgreSQL driver. Do not point development or tests at production or an unknown database.
4. Install the locked project dependencies:

   ```bash
   uv sync --locked
   ```

5. After configuring the database and reviewing the migration target, apply migrations as described above.
6. Start the development server:

   ```bash
   uv run uvicorn app.main:app --reload
   ```

7. Visit `http://127.0.0.1:8000/health` or the generated API documentation at `http://127.0.0.1:8000/docs`.

The Compose file defines PostgreSQL 16 and API services, but the API container applies migrations on startup and PostgreSQL uses a persistent volume. Compose was not run or verified in this review. It does not define the Redis service mentioned in the old README.

## Environment-variable reference

Names and purposes only; this document intentionally contains no values. Settings are declared in [`app/core/config.py`](app/core/config.py). Required/optional validation is incomplete and should be improved before deployment.

| Variable | Purpose in current source |
|---|---|
| `POSTGRES_SERVER` | PostgreSQL hostname. |
| `POSTGRES_PORT` | PostgreSQL port. |
| `POSTGRES_USER` | PostgreSQL username. |
| `POSTGRES_PASSWORD` | PostgreSQL password; secret. |
| `POSTGRES_DB` | Database name. |
| `JWT_SECRET` | Required canonical JWT signing and verification key; minimum 32 characters; secret. |
| `ALGORITHM` | Required JWT signing/verification algorithm identifier. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access-token lifetime. |
| `ENVIRONMENT` | Runtime mode (`local`, `staging` or `production`). |
| `API_V1_STR` | Configured v1 prefix used by the OAuth token URL, but the router is not mounted. |
| `PROJECT_NAME` | Project label setting; current code use is limited/unclear. |
| `FRONTEND_HOST` | Frontend host setting; not currently wired into CORS behavior. |
| `BACKEND_CORS_ORIGINS` | Intended CORS origins; current app does not configure CORS middleware. |
| `PAYSTACK_SECRET_KEY` | Reserved setting; no Paystack client currently uses it. |
| `LOG_FILE` | Logging destination passed to Python logging configuration. |

## Dependencies and commands

The dependency source of truth is `pyproject.toml` plus `uv.lock`; `requirements.txt` is also present for the Docker build. No provider SDK is installed.

Database-independent regression tests can be run with:

```bash
uv run --no-sync python -m pytest -q \
  app/test_model_schema_compatibility.py \
  app/test_order_transactions.py
```

The PostgreSQL integration tests are in `app/test_orders_postgres.py`. They require explicit `ZETICKETS_TEST_DATABASE_URL` and `ZETICKETS_TEST_CLUSTER_ID` and reject targets outside their dedicated loopback test database identity. Only use a freshly provisioned disposable PostgreSQL test cluster; they do not make an ordinary application database safe to test against. The PostgreSQL provisioning used in Phase 2 was temporary and is not a supported setup script.

## API documentation and available endpoints

The only registered application route is `GET /health`. FastAPI exposes its generated `/docs`, `/redoc` and `/openapi.json` routes. The v1 endpoint modules exist in source but are not mounted; their operations should not be represented as available API functionality. API router integration and contract tests are Phase 4 work.

## Docker and deployment status

`Dockerfile` and `docker-compose.yml` exist but have not been validated as a deployment. Compose configures PostgreSQL 16 with a persistent volume and the API container runs Alembic before Uvicorn. Python dependencies in `requirements.txt`, `pyproject.toml` and the lockfile must stay aligned. No Redis service is defined. No production configuration, backup/recovery, observability, CI or deployment process is established.

## Roadmap and documentation

- Phase 1: complete; see [post-mortem](docs/postmortems/phase-1-canonical-models.md).
- Phase 2: complete on an isolated PostgreSQL test environment; existing-database compatibility remains unverified. See [post-mortem](docs/postmortems/phase-2-transactional-business-logic.md).
- Phase 3: architecture/security direction accepted; Packages 1 and 2 are implemented. Provider integration, orchestration, authorization hardening and subsequent packages remain. Account-specific readiness and commercial terms are open.
- Phases 4–5: not started.

The [engineering roadmap](docs/engineering-roadmap.md) is authoritative. Use the [documentation index](docs/README.md) to find architecture, payments, security and ADR material.

## Contribution and development workflow

Read [`AGENTS.md`](AGENTS.md), the [agent execution policy](docs/agent-execution-policy.md) and the active phase's roadmap criteria before changing code. Keep API changes, services and models in their appropriate layers; add regression tests; preserve unknown historical values; review migrations; run tests against isolated test data; update relevant ADRs and post-mortems; and create a Git checkpoint only after verification. Do not commit secrets, run migrations against unknown data or rewrite existing history.

## License

No license file or license declaration is present in the repository. No license is asserted by this README.
