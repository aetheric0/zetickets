# Phase 2 Execution Log: Transactional Business Logic

**Current status:** Phase 2 exit criteria pass on a fresh, isolated PostgreSQL 18.6 cluster. Compatibility with any existing application database remains unverified.

| Sub-phase | Acceptance focus | Current result |
|---|---|---|
| 1. Order/reservation lifecycle | Explicit legal transitions; legacy states preserved | Implemented: pending reservations can cancel/expire; completion is closed without trusted payment evidence; legacy statuses are preserved. |
| 2. Inventory reservation/release | Atomic counter and ticket changes | Implemented: inventory lock, counter, order and tickets share one transaction; cancellation and trusted failure release once. |
| 3. Expiry/cleanup | Bounded, repeat-safe cleanup | Implemented as a callable bounded service using `SKIP LOCKED`; unknown/inconsistent inventory is left unchanged. Scheduler intentionally deferred. |
| 4. Checkout/payment boundary | No client assertion of payment success | Implemented: existing checkout operation returns 409; no provider or successful-payment path added. |
| 5. Cancellation/failure | Preserve inventory on cancellation/failure | Implemented internally: cancellation and typed trusted payment failure are idempotent; transaction exceptions roll back. Legacy `FAILED` is not reinterpreted. |
| 6. Concurrency/transaction integrity | Lock order and atomicity | Verified against PostgreSQL 18.6, including capacity contention, rollback and `SKIP LOCKED` behavior. |
| 7. Idempotency | Duplicate reservation cannot double-reserve | PostgreSQL same-key contention, replay and mismatch behavior pass; uniqueness constraints are present. |
| 8. Tests/regression | Normal, boundary, failure and concurrency evidence | 34 tests pass across Phase 1 compatibility, Phase 2 service and PostgreSQL integration modules. |

## Active limitations

- The disposable-cluster tests prove behavior on a fresh PostgreSQL 18.6 schema only. They do not establish compatibility with any deployed or existing database.
- No expiry scheduler, route registration, payment verifier, successful-payment transition, currency policy, or late-payment reconciliation was added.
- Full application tests were not run because the repository's existing `app/tests/conftest.py` opens an SQLite database automatically. Phase-specific tests were run directly without that fixture scope.

## Verification record

- `UV_CACHE_DIR=/tmp/zetickets-uv-cache uv run --no-sync python -m pytest -q app/test_model_schema_compatibility.py` — 6 passed.
- `UV_CACHE_DIR=/tmp/zetickets-uv-cache uv run --no-sync python -m pytest -q app/test_order_transactions.py` — 17 passed.
- On the verified temporary PostgreSQL 18.6 cluster, `alembic upgrade head` applied the complete chain; `alembic current` reported `a2d4e6f8091b (head)`; a repeat `upgrade head` completed with no operations; and `alembic check` reported no new upgrade operations.
- PostgreSQL-only integration module plus the six Phase 1 compatibility tests and 17 Phase 2 service tests — **34 passed**. Coverage includes ORM-to-schema comparison, enum labels, constraints, foreign keys, reservations, rollback, cancellation, expiry, payment-failure boundary, retries and real concurrent requests/locks.
- PostgreSQL identity was checked before migrations and by the integration fixture: PostgreSQL 18.6, loopback `127.0.0.1:55439`, database `zetickets_phase2_test`, role `zetickets_test_owner`, temporary cluster ID `7709571397362928905`.
- The guarded Alembic test branch commits its read-only identity preflight before beginning the migration transaction; this ensures Alembic persists its revisions.
- PostgreSQL test fixture scope is per test, matching pytest's per-test event loops and preventing asyncpg connections from crossing loops.
- Python `compileall` over the changed models, schemas, service, endpoint, tests and both new revisions — passed.
- `git diff --check` — passed.
- Ruff was attempted but could not spawn because the executable returned `Permission denied`.
- No existing application database was connected to, modified or migrated. No container operation occurred.

## Migration implications

The Phase 2 forward-only revision adds nullable reservation idempotency/evidence references, the `PAYMENT_FAILED` enum label, uniqueness constraints, inventory/quantity checks and PostgreSQL column comments needed to align reflected metadata. The complete chain was applied and re-applied on the fresh disposable PostgreSQL cluster, and Alembic schema comparison matched ORM metadata. This verifies migration consistency against that PostgreSQL version and empty schema; it does not verify upgrade safety or compatibility against existing data or any other PostgreSQL version. The initial migration remains unchanged. Downgrade intentionally raises `NotImplementedError`.

## Correction record from PostgreSQL verification

- The first migration run exposed a transaction ownership bug in the guarded `alembic/env.py` test branch: its identity SELECT opened an autobegun transaction, causing Alembic's work to roll back on connection close. The branch now commits only that read-only identity check before Alembic starts its owned migration transaction.
- `alembic check` found three missing PostgreSQL column comments. The Phase 2 revision now applies those comments without editing the initial revision.
- The first integration run exposed a session-scoped async engine crossing pytest's function-scoped event loops. PostgreSQL test fixtures now use function scope; the full suite passes without cross-loop connection reuse.
