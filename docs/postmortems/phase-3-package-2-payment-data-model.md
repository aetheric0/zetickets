# Phase 3 Package 2 Post-mortem: Payment Data Model

**Status:** Implemented and verified on a fresh disposable PostgreSQL 18.6 cluster. Provider integration and payment behavior remain deferred.

## Defects and root causes

- The repository had no persistent payment attempt, webhook receipt, refund or reconciliation entities. Orders could not represent multiple provider attempts or preserve auditable payment and refund observations.
- Existing `Order.total_amount` and price fields use legacy `Numeric`/`Decimal` and nullable currency. That representation cannot safely serve as the new payment provider snapshot, and historical unknowns cannot be filled by assumption.
- A database-level invariant was needed so two distinct successful attempts could not each claim fulfillment for one order. ORM-only checks would not withstand concurrent writers.
- Reconciliation observations could otherwise reference a refund from another attempt or provider scope; repeated records and changed audit facts could damage traceability.

## Impact

There was no persistence foundation for future Paystack verification, webhook replay handling, refunds, late-payment recovery or financial reconciliation. Order/payment/fulfillment/refund states were not representable as distinct durable records.

## Corrections and design decisions

- Added `PaymentAttempt`, allowing multiple attempts per order, with provider/account/environment scope, unique client and provider references, order-scoped idempotency, positive integer minor-unit amount, explicit KES currency, lifecycle enum and provider timestamps.
- Added `PaymentFulfillment` as one unique claim per order. Composite foreign keys and a check require a successful attempt belonging to the same order. This prevents duplicate claims at the database boundary but does not authenticate provider success or issue ticket rows.
- Added `WebhookEvent` with separate authentication and processing status, deduplication/provider-event uniqueness, digest and bounded metadata. Raw payloads and credentials are not stored. Rejected events cannot be updated to authenticated, and processing terminal states require authenticated status. This database state is not itself proof of provider authenticity.
- Added `Refund`, with amount/currency snapshots, provider-scoped references, per-payment idempotency and separate requested/processing/confirmed/failure states. Multiple refund records are allowed; no cumulative cap, commission, fee allocation or refund policy was invented.
- Added `ReconciliationRecord`, storing bounded internal/provider observations and resolution. Composite foreign keys enforce that the payment, refund and provider/account/environment scope agree. Unique run/idempotency keys make repeated observations deterministic.
- Added explicit Python-valued PostgreSQL enums, indexes, positive/KES/ISO checks, restrictive foreign keys and triggers that preserve financial snapshots, webhook receipt evidence and reconciliation observations and reject deletion of payment/audit rows.
- Existing order currency and price fields remain unchanged; no historical values were backfilled. Organizer ledger and payout entities remain deferred to Package 5.
- Added forward-only revision `c7e2a4b19d60`, downstream of Phase 2. It does not modify the preserved initial or earlier migrations. Downgrade refuses to remove populated payment/audit records.

## Files changed

- `app/models/enums.py`
- `app/models/payment.py` (new)
- `app/models/order.py` (payment relationships added; the pre-existing import-only consolidation remains a separate unstaged change)
- `app/models/__init__.py`
- `alembic/versions/c7e2a4b19d60_phase3_payment_data_model.py` (new)
- `app/test_payment_models.py` (new)
- `app/test_payments_postgres.py` (new)
- `app/test_orders_postgres.py` (expected head advanced)
- `README.md`
- `docs/architecture/domain-model.md`
- `docs/architecture/payment-architecture.md`
- `docs/architecture/reservation-lifecycle.md`
- `docs/architecture/system-overview.md`
- `docs/decisions/0005-provider-independent-payment-boundary.md`
- `docs/decisions/0007-separate-order-and-payment-state.md`
- `docs/decisions/0008-webhook-evidence-trust-boundary.md`
- `docs/engineering-roadmap.md`
- `docs/phase-3-implementation-plan.md`
- `docs/README.md`
- `docs/postmortems/README.md`
- `docs/postmortems/phase-3-package-2-payment-data-model.md`

## Verification evidence

- Database-independent command: `python -m pytest -q app/test_model_schema_compatibility.py app/test_payment_models.py app/test_order_transactions.py app/test_security_foundation.py` — **36 passed**.
- Fresh-database migration: `alembic upgrade head` — **passed**; resulting revision `c7e2a4b19d60`.
- `alembic check` — **passed**, no new upgrade operations detected.
- Empty disposable schema `alembic downgrade a2d4e6f8091b` then `alembic upgrade head` — **passed**.
- PostgreSQL-backed and regression command from `/tmp`, with only the guarded `ZETICKETS_TEST_DATABASE_URL`, matching cluster identifier, and generated test-only `JWT_SECRET`: `python -m pytest -q app/test_model_schema_compatibility.py app/test_payment_models.py app/test_order_transactions.py app/test_security_foundation.py app/test_orders_postgres.py app/test_payments_postgres.py` — **56 passed** on PostgreSQL **18.6**. Checks include model/migrated columns, indexes and foreign keys, enum labels, trigger presence, invalid amounts/currency/FKs, scoped references, refund-to-payment association, concurrent uniqueness, rollback, immutable audit observations, duplicate fulfillment claims and Phase 2 reservation regressions.
- Python compilation — passed for payment models, affected model registry/order model, tests and new migration.
- `git diff --check` and documentation link checks — see final task verification.
- Ruff was unavailable in the environment; no lint run is claimed.

## Migration and database implications

The full migration chain and new schema were applied only to a newly initialized disposable PostgreSQL cluster stored under `/tmp`, with a dedicated local port, role, database and generated credentials. The new migration was downgraded only while empty, then upgraded again. The test cluster is stopped after verification. **Compatibility against any existing application database is unverified**; no such database was accessed. A production rollout requires a separately authorized state review and rehearsal.

## Residual risks and deferred work

- No Paystack adapter, independent transaction verification, webhook endpoint, payment-state service, refund execution, reconciliation worker, ticket issuance or organizer ledger/payout code exists. The schema alone must never be treated as authenticated evidence.
- A payment attempt must be constructed from authoritative order facts; Package 2 adds no checkout path and does not convert legacy decimal order totals to minor units.
- Multiple refund rows are representable, but cumulative refundable amount, provider policy, partial-refund rules and operator handling require the approved orchestration and provider design; no total cap is enforced by this schema.
- The KES check is intentionally strict for initial payments/refunds. Enabling another currency requires explicit policy and a forward migration.
- PostgreSQL roles in this test-only cluster had elevated privileges solely to support controlled migration and identity checks. This says nothing about production role design.
- Existing-database migration compatibility, production database privileges, retention periods, backup/recovery, provider account settings and payment-provider behavior remain unverified.

## Git checkpoint

Created after verification. The known import-only change in `app/models/order.py` remains unstaged and excluded.
