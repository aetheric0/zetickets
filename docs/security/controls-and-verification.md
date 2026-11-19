# Security controls and verification strategy

This is an implementation and release specification, not a statement that controls are implemented. See the [threat model](threat-model.md), [payment architecture](../architecture/payment-architecture.md), [lifecycle requirements](../payments/lifecycle-and-reconciliation.md) and [ADRs](../decisions/README.md).

## Security foundation

- Resolve the confirmed JWT mismatch: [`app/core/security.py`](../../app/core/security.py) signs with `JWT_SECRET`; [`app/core/deps.py`](../../app/core/deps.py) verifies with `SECRET_KEY`; both currently have empty defaults in [`config.py`](../../app/core/config.py). Use one explicitly validated key/configuration for signing and verification, fail closed when absent/weak, allowlist algorithm and define rotation. Do not change auth code in this planning milestone.
- Tests must show a token signed with configured key validates, wrong-key/algorithm/expired/malformed tokens reject, and missing/weak secret prevents unsafe operation.
- Enforce authentication, ownership and least-privilege role authorization in service operations, including every order read, payment lookup, refund, reconciliation, payout and organizer balance view. Never trust identifiers alone.
- Restrict role mutation and administrative financial actions; audit actor, reason, object/reference and outcome. Consider dual control for payout/refund execution after risk/commercial thresholds are defined.

## Provider evidence boundary

- Persist a payment attempt before external I/O. The trusted service invokes the Paystack adapter verifier and validates merchant account, environment, unique reference, order association, exact integer amount and KES currency against immutable snapshots.
- Do not accept browser status, arbitrary JSON or a constructible `VerifiedPaymentFailure`/similar Python dataclass as provider proof. That existing Phase 2 object is not independently authenticated.
- Verify Paystack webhook signature over raw bytes according to current docs (timestamp, all key-ID signatures during rotation, freshness window, HMAC-SHA512 and constant-time compare). Store/deduplicate authenticated receipts; webhook only queues/query-verifies. Treat valid signature as origin/integrity, not correctness of amount/order.
- Record API timeout as ambiguous until reference-based verification; never repeat charge/refund blindly.

## Data and financial controls

- Initial currency KES only; integer minor units plus ISO currency code, immutable purchase/payment snapshots, server-side price derivation and no floats. Do not invent historical facts.
- Separate payment capture, settlement to platform, organizer liability, fees, revenue, refund and organizer payout in an auditable balanced journal. Provider success is not proof of cleared funds. An initiated organizer payout is not paid until verified confirmation.
- Never store card PAN/CVV. Minimize webhook/customer data, redact secrets and sensitive fields, define encrypted storage/backup and retention before raw payload persistence.
- Keep test and live credentials/accounts separate; inject secrets externally, restrict access, rotate safely and verify no secrets appear in code, logs, error responses or artifacts.

## Required automated verification

1. **Authentication/authorization:** JWT consistency and fail-closed configuration; role matrix; order ownership/IDOR; self-escalation; admin audit and denied actions.
2. **Webhook/provider:** signature correctness, changed bytes, invalid/stale timestamps, rotation keys, replay, duplicate/reordered events; provider verification status/reference/account/environment/amount/currency mismatch.
3. **Transactional lifecycle:** duplicate/concurrent initialization, timeout after provider acceptance, expiry/cancellation race, one-time fulfillment, no ticket when inventory unavailable, repeated reconciliation.
4. **Refund:** duplicate request idempotency, ambiguous timeout query-before-retry, provider failure/attention/delay, partial refund bounds and confirmation-only completion.
5. **Accounting/payout:** balanced entries, unique source references, cleared-versus-pending distinction, duplicate/unauthorized payout rejection, confirmed payout only updates liability, repeatable settlement reconciliation and auditable discrepancy resolution.
6. **Operations/privacy:** log/response redaction, no secret leakage, test/live separation, key rotation, access and retention tests, alerting on aged unresolved payment/refund/payout.

Use provider sandbox and disposable PostgreSQL for their corresponding integration tests. Mocks are useful for isolated adapter/service logic but do not establish live eligibility or PostgreSQL concurrency behavior. Never use an existing application database for verification.

## Release gates and account checks

Before production, verify the Paystack merchant dashboard/agreement for Zetickets: enabled Kenya M-PESA/card channels, live eligibility/KYB, settlement destination/currency and clearing evidence, applicable fees/taxes/limits, refund and dispute behavior, webhook signing configuration, secret rotation and support escalation. Owner's existing verified Paystack access does not itself establish these settings. Commercial choices still needed include commission, fee allocation, tax, reserves, payout schedule and organizer contractual terms.
