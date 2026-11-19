# Phase 2 Review: Transactional Business Logic

**Status:** Phase 2 implementation verified on an isolated PostgreSQL 18.6 cluster and eligible for a repository checkpoint. Compatibility with any existing application database remains unverified.

## Defects and root causes

- The previous reservation flow wrote inventory, order and ticket rows directly in a route and had no duplicate-request key.
- The previous checkout marked orders complete and issued tickets from a client request without trusted payment evidence.
- Quantity/expiry-based checkout and release logic could be repeated or race without a consistent state lock; expiry cleanup did not exist.
- Historical counters/expiry can remain null after Phase 1 because they were absent from the original schema.

## Impact

Concurrent or retried reservations could double-reserve inventory. Cancellation, failure and expiry could release counters incorrectly or more than once. A client could assert payment success. PostgreSQL locking, `SKIP LOCKED`, unique-conflict recovery and check constraints are central to the fix and are now exercised against a disposable PostgreSQL cluster.

## Corrections and design decisions

- Moved reservation, cancellation, payment-failure and expiry operations into `app/services/orders.py`. Each operation commits atomically and rolls back on exceptions.
- Reservation locks its ticket-type row before capacity checks and changes; order creation, ticket rows and reserved inventory share a transaction.
- Cancellation/failure lock the order and then inventory, validate the current pending state and quantity, and release once. Repeated terminal operations are safe.
- Expiry cleanup uses bounded batches and `FOR UPDATE SKIP LOCKED`; it leaves unknown or inconsistent inventory unchanged. No route/scheduler was introduced.
- Added a required per-user `Idempotency-Key` contract, unique constraint and replay payload comparison. A simulated uniqueness race rolls back the losing inventory mutation and reloads the winning order.
- The existing checkout operation now returns conflict without changing order/ticket state. Trusted internal payment-failure evidence has a provider-neutral boundary; no request can create that evidence. Successful payment completion awaits Phase 3 verification and a currency decision.
- Added nonnegative inventory and positive order quantity database constraints while allowing legacy NULL values.
- Added an isolated PostgreSQL integration suite. It verifies real transaction rollback, capacity contention, same-key uniqueness races, row locks, `SKIP LOCKED`, inventory release, migrated enum/constraint/FK shape and ORM metadata parity.
- Corrected the test-only Alembic identity guard after integration exposed that its preflight SELECT left an autobegun transaction open, preventing Alembic's migration transaction from being committed. The guard now commits that read-only preflight before migration execution.
- Reconciled PostgreSQL column comments in the forward Phase 2 revision after `alembic check` identified the differences. The preserved initial revision was not changed.
- Changed PostgreSQL async test fixtures to per-test scope after pytest exposed cross-event-loop reuse from a session-scoped engine.

## Files changed

- `AGENTS.md`
- `app/api/v1/endpoints/orders.py`
- `app/models/enums.py`, `app/models/order.py`, `app/models/ticket.py`
- `app/services/orders.py`
- `app/test_order_transactions.py`
- `app/test_orders_postgres.py`
- `alembic/env.py`
- `alembic/versions/a2d4e6f8091b_phase2_transactional_order_support.py`
- `docs/agent-execution-policy.md`
- `docs/decisions/0001-preserve-unknown-historical-values.md`
- `docs/decisions/0002-transactional-inventory-locking.md`
- `docs/decisions/0003-order-idempotency.md`
- `docs/decisions/0004-payment-evidence-boundary.md`
- `docs/phase-2-execution-log.md`
- `docs/postmortems/phase-1-canonical-models.md`
- `docs/postmortems/phase-2-transactional-business-logic.md`

## Verification evidence

- Six Phase 1 schema compatibility tests, 17 Phase 2 service tests and 11 PostgreSQL integration tests — **34 passed** on the final run.
- On a dedicated PostgreSQL 18.6 cluster in `/tmp`, `alembic upgrade head` applied the complete chain, `alembic current` reported `a2d4e6f8091b (head)`, repeating `upgrade head` was a no-op, and `alembic check` reported no new operations.
- Integration assertions checked cluster/database identity before migration and fixture connections, and compared PostgreSQL schema metadata with ORM metadata.
- Python `compileall` over changed implementation, tests and migrations — passed.
- `git diff --check` — passed.
- Ruff invocation was blocked because its executable could not spawn (`Permission denied`).
- Tests used only the disposable cluster. No existing application database was accessed.

## Migration and database implications

The forward-only revisions were executed only against an empty temporary database on PostgreSQL 18.6. The resulting schema reached head, was repeatable, and matched ORM metadata. This establishes consistency for that fresh schema and PostgreSQL version. Compatibility with existing application data, deployed schemas, and other PostgreSQL versions remains unverified. The initial migration is unchanged; the Phase 1 and Phase 2 revisions intentionally have no downgrade implementation.

## Residual risks and blockers

- Existing database upgrades require a separate backup-backed rehearsal and data review; they were explicitly out of scope and remain unverified.
- No expiry scheduler is configured; an authorized runtime integration must invoke `expire_due_orders` later.
- Successful payment completion, payment verification, currency selection and late-success/refund reconciliation are intentionally deferred. Checkout currently rejects all requests.
- The `VerifiedPaymentFailure` value is an internal type boundary, not cryptographic proof. Phase 3 must ensure only an authenticated verifier calls that service.

- The order router remains unregistered; route registration is Phase 4.
- Existing legacy rows with unknown order or inventory facts remain unreconciled and ineligible for unsafe transitions.

### Phase 3 Package 1 follow-up

The constructible value and its state-changing service operation were subsequently removed. Payment failure recording now fails closed without accepting caller-supplied evidence or changing order/inventory state; see the [Phase 3 Package 1 post-mortem](phase-3-package-1-security-foundation.md).
