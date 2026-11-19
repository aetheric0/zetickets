# Phase 3 implementation plan: security and payments

**Status:** Planning specification only. No package below has been implemented. Phase 3 follows completed Phase 1/2; no Phase 4 router rollout or Phase 5 deployment work starts automatically. Approved direction: Paystack first, KES initial only, provider-independent internals, platform collection/separate organizer settlement, and refund verified late success when reservation/inventory is invalid.

## Work package dependency map

```text
WP1 Security foundation ─┬─> WP2 payment data model ──┬─> WP4 orchestration ──> WP6 API/tests
                         └─> WP3 Paystack adapter ─────┘          │
WP5 organizer accounting (design can proceed alongside WP2; posting depends on WP4)
WP7 operational readiness depends on verified WP2–WP6 behavior and deployment environment.
```

WP2 and WP3 may be designed in parallel once WP1 defines trust boundaries, but their contracts must converge before orchestration. Commercial/account-specific checks are gates before live transactions, not blockers for sandbox coding. No fee, commission, tax, reserve, payout timing or account eligibility is assumed.

## WP1 — Security foundation

- **Scope:** Resolve `JWT_SECRET`/`SECRET_KEY` mismatch; fail-closed secret validation; authorization/ownership matrix; replace caller-constructible payment evidence trust with service-owned provider verification; define audit events and secret handling.
- **Likely components:** `app/core/config.py`, `app/core/security.py`, `app/core/deps.py`, auth/authorization dependencies, `app/services/orders.py` payment boundary, security tests and configuration docs.
- **Dependencies:** None; prerequisite to payment endpoints/adapter exposure.
- **Database implications:** No payment schema yet; audit persistence may be scoped here or in WP2.
- **Security:** One validated JWT key/algorithm; deny-by-default roles; no caller-asserted status; secrets external and redacted.
- **Tests:** Matching JWT key succeeds; missing/weak/mismatched key fails closed; expiry/algorithm rejection; ownership and role matrix; attempts to construct/inject fake evidence cannot mark paid.
- **Acceptance:** Signing/verifying configuration is consistent, protected operations enforce ownership/authorization, evidence trust is rooted in server-side adapter verification, actions are auditable.
- **Rollback:** Revert auth behavior only if safe; keep prior key as controlled rotation overlap, never revert to mismatched keys or insecure fail-open defaults. Disable payment operations while preserving audit history.

## WP2 — Payment data model

- **Scope:** Payment attempts, provider/account/environment-scoped references, KES minor-unit and ISO currency snapshots, append-only webhook/evidence inbox, refund attempts, reconciliation runs/findings and idempotency constraints.
- **Likely components:** `app/models/`, `app/models/enums.py`, `app/schemas/`, Alembic forward revisions, ORM/schema compatibility and migration tests.
- **Dependencies:** WP1 trust boundary and accepted ADRs; coordinate adapter contract with WP3.
- **Database implications:** Forward-only additive schema, nullable-safe history; do not fabricate old quantity/money/currency/expiry. PostgreSQL enum/constraint/index changes require fresh disposable PostgreSQL migration tests and existing-database compatibility remains separately unknown.
- **Security:** Minimize payload retention; no credentials/card data; protect merchant IDs and event metadata; restrict financial record access.
- **Tests:** Model/migration parity, uniqueness by provider/account/environment, legal enum transitions, nullable historical record reads, append-only evidence invariants and PostgreSQL constraints.
- **Acceptance:** A fresh DB can migrate; attempts/events/refunds/reconciliation are representable and idempotency constraints are enforced; old unknowns remain unknown.
- **Rollback:** Forward-only repair migration; disable new payment writes and preserve records. No destructive downgrade or data rewrite against existing databases.

## WP3 — Paystack provider adapter

- **Scope:** Server-side initialization, transaction verification, raw-body webhook authentication/normalization, refund initiation/status verification and reference-based reconciliation. Keep provider payloads native only inside adapter.
- **Likely components:** new `app/services/payments/` or equivalent provider module, settings schema, HTTP client boundary, adapter contract tests and sandbox configuration docs.
- **Dependencies:** WP1; adapter can develop alongside WP2 after interface contract is agreed. Account-specific live launch checks remain external.
- **Database implications:** Uses WP2 attempts, event receipts and refund references; no direct persistence decisions in adapter.
- **Security:** Test/live separation; raw-byte signature verification; timestamp/key rotation/constant-time compare; amount/currency checked by orchestration; secret redaction; bounded timeouts/rate limits.
- **Tests:** Provider contract fixtures, valid/invalid/rotated signatures, initialization accepted/rejected/ambiguous timeout, all relevant verification states, refund status and API errors. Sandbox integration tests when credentials/environment are explicitly configured without exposing them.
- **Acceptance:** Adapter returns normalized results only, performs no order/ticket state changes, and ambiguous external outcomes remain unknown pending verify/reconcile.
- **Rollback:** Disable adapter/checkout feature switch; retain attempts/events and reconcile manually; never delete records or assume provider call did not execute.

## WP4 — Transactional payment orchestration

- **Scope:** Idempotent attempt creation, webhook inbox processing, verified state transitions, atomic order/payment/ticket/inventory fulfillment, late-success refunds, duplicate charges and recovery.
- **Likely components:** `app/services/orders.py`, new payment orchestration service, persistence models/repositories, transaction tests.
- **Dependencies:** WP1, WP2 and WP3 contracts.
- **Database implications:** Lock attempt/order/ticket inventory; uniqueness and transitions in one transaction; verify under PostgreSQL concurrency. No inferred or backfilled facts.
- **Security:** Only service-invoked provider verification grants trusted result; ownership/association, exact amount and KES currency; no success from client/webhook alone; refund authorization/audit.
- **Tests:** duplicate/out-of-order/missing events, concurrent attempts, timeout after provider acceptance, expiry/cancel races, unavailable inventory, duplicate success, refund idempotency/failure and atomic rollback against disposable PostgreSQL.
- **Acceptance:** Payment can be verified without automatic fulfillment; fulfillment exactly once only when reservation/inventory eligible; late invalid success is recorded and refunded/reconciled; reruns do not duplicate effects.
- **Rollback:** Disable checkout and webhook processing only after durable intake is safely paused; keep reconciliation and refund resolution available; preserve transaction history.

## WP5 — Organizer financial accounting

- **Scope:** Platform collection/settlement records, balanced internal per-currency ledger, organizer liabilities, payout records/adapters and reconciliation. Define posting semantics without hardcoded commercial terms.
- **Likely components:** financial models/services/schemas and migrations, admin authorization/audit, reconciliation reporting.
- **Dependencies:** Data model can be designed alongside WP2; posting relies on verified captures/refunds from WP4. Commercial/legal terms required before balances become payable or any payout is sent.
- **Database implications:** Append-only source-linked journal, separate provider transactions and payout records; uniqueness/idempotency; per-currency balancing. Never treat capture as platform clearing or payout initiation as completion.
- **Security:** Strong permission separation, protected payout destinations, unique references, approval controls and audit trail.
- **Tests:** balanced entries, one posting per capture/refund/fee/settlement/payout, duplicate/unauthorized payout rejection, provider-confirmed status only, settlement variance and rerunnable reconciliation.
- **Acceptance:** Every organizer payable is explainable by source records and explicit approved policy; no payout is shown paid without confirmation; outstanding discrepancies are visible.
- **Rollback:** Suspend payout execution while preserving ledger and reconciliation; correct with auditable compensating entries, never edit/delete posted history.

## WP6 — API integration and automated testing

- **Scope:** Minimum authenticated checkout/payment status/refund/admin operations and authenticated Paystack webhook intake; stable schemas, dependency injection, contract and regression tests. Keep router registration coordinated with Phase 4's broader API integration scope; do not expose incomplete routes.
- **Likely components:** `app/api/v1/endpoints/`, router composition, `app/schemas/`, service dependencies, tests and OpenAPI docs.
- **Dependencies:** WP1–WP5 relevant flows; webhook adapter and orchestration must be complete before routes.
- **Database implications:** API tests use isolated test-only DB configuration; PostgreSQL integration required for transaction guarantees.
- **Security:** ownership on every order access; webhook signature before JSON processing; narrow admin role and rate limits; no payment credentials or sensitive payload in responses.
- **Tests:** API contract/auth matrix, malicious client status/amount, webhook verification and replay, PostgreSQL concurrency, rollback/failure injection and OpenAPI route checks.
- **Acceptance:** Only intended secure operations are registered; response contracts expose no secrets/internal evidence; all required success/failure cases are reproducible.
- **Rollback:** Unregister/disable incomplete payment routes while preserving accepted events and financial evidence; no backward destructive migration.

## WP7 — Operational readiness

- **Scope:** Bounded reconciliation worker/runbook, refund and payout monitoring, structured redacted logs, metrics/alerts, rate limiting, secret rotation and deployment/incident procedures.
- **Likely components:** worker/CLI scheduling entry point, logging/metrics configuration, operational docs, deployment/secret management later in Phase 5.
- **Dependencies:** WP2–WP6 state/evidence contracts. Basic runbooks can be drafted earlier; production execution must wait for Phase 5 environment controls.
- **Database implications:** Durable jobs/leases or bounded polling design requires review; do not add infrastructure without need/approval. Worker operations are idempotent and use existing tables where feasible.
- **Security:** Least-privilege service credentials, no payload/secret logs, operator auditing, alert access controls, key rotation and incident response.
- **Tests:** job retry/restart, lock contention, reconciliation idempotency, redaction, metrics/alerts for aged pending/refund/payout, secret rotation.
- **Acceptance:** Operators can find and safely resolve missing callbacks, payment/refund discrepancies and payout variance; recovery steps are tested; monitoring detects stuck states.
- **Rollback:** Pause workers and external side effects, preserve durable queues/records, use manual reconciliation procedure and restart from idempotent checkpoints.

## Cross-package release gates

- Verify Paystack dashboard/agreement for Zetickets live eligibility, enabled channels, settlement and clearing evidence, fee/refund/dispute terms before live charging.
- Define commission, provider fee allocation, taxes, reserves, payout timing and organizer contracts before implementing payable calculations or production payouts.
- Use provider sandbox and explicitly isolated disposable PostgreSQL; never connect tests to existing app databases.
- Each deployed schema revision must be forward-only/data-preserving and verified against a fresh PostgreSQL cluster; populated production upgrade compatibility requires a separate authorized rehearsal.
- Phase 3 exit additionally requires security/provider negative-path coverage, PostgreSQL transaction tests, controlled reconciliation and documented operational recovery. Phase 4/5 criteria remain separate.
