# Security controls and verification strategy

This is a proposed Phase 3/4 release checklist, not a statement of current implementation.

## Before provider code

- Resolve provider selection, supported currencies, merchant-of-record/organizer settlement, refund authority and late-success policy with the owner.
- Fix and test JWT key consistency and fail-closed secret validation; define user/role ownership policy.
- Define payment/order state machines and immutable purchase snapshots before preparing schema revisions.
- Decide PII/evidence retention, redaction, encryption, backup access and incident response.

## Provider adapter controls

- Use provider-hosted checkout where practical; do not receive or store raw PAN/CVV.
- Keep API/webhook credentials server-side, separated by test/live environment, rotated and never logged.
- Verify signatures over raw bytes according to current provider documentation, including key rotation and freshness rules where present.
- Independently query provider status and compare merchant account, environment, reference, amount, currency and status before fulfillment.
- Persist attempt and webhook/event identities before retries; make all transitions/refund calls idempotent.
- Treat provider timeouts as ambiguous, not as definitive failure.

## Domain and operations controls

- Lock order/payment attempt/inventory consistently and commit payment evidence, order transition, ticket changes and counters atomically.
- Keep provider event/evidence records append-only; separate payment success from fulfillment and refund states.
- Restrict reconciliation/refund operations, require actor/reason audit, and consider dual approval for material refunds.
- Monitor unresolved/late payments, duplicate successes, amount mismatches, webhook failures, provider timeouts, refund status and settlement variances.
- Define a documented and staffed support path for late success, provider outage, refund needs-attention and reconciliation conflicts.

## Verification levels

1. Unit tests for normalization, state transition rules, signatures and money conversion with deterministic fixtures.
2. Service/database tests against disposable PostgreSQL for transactionality, uniqueness, locks, idempotency and migration parity.
3. Provider sandbox tests for initialization, cards/M-PESA paths, delayed/missing callbacks, verification, key rotation and refunds, using test-only merchant credentials.
4. API security tests for ownership/role boundaries, malformed payloads, replay, rate limits, logging and response redaction.
5. Controlled production readiness review of merchant dashboard eligibility, fees, settlement, callback URLs, secrets, alerting and operational ownership. Do not use live customer transactions as a test fixture.

Every report should label checks as passed, failed, blocked or not run. A fake callback test is not proof of a provider's signature scheme; a sandbox success is not proof of production onboarding or settlement terms.
