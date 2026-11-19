# Architecture Decision Records

Store material, durable engineering decisions here. Phase 1/2 records 0001–0004 are existing decisions. The following Phase 3 payment records are proposals, not approved financial/provider policy:

- [0001 — Preserve unknown historical values](0001-preserve-unknown-historical-values.md) — accepted.
- [0002 — Transactional inventory locking and expiry](0002-transactional-inventory-locking.md) — accepted; fresh disposable PostgreSQL verification recorded.
- [0003 — Reservation idempotency](0003-order-idempotency.md) — accepted.
- [0004 — Payment evidence boundary](0004-payment-evidence-boundary.md) — accepted; successful payment deferred.
- [0005 — Provider-independent payment boundary](0005-provider-independent-payment-boundary.md) — proposed.
- [0006 — Paystack first-provider candidate](0006-paystack-first-provider-candidate.md) — proposed; owner approval required.
- [0007 — Separate order and payment state](0007-separate-order-and-payment-state.md) — proposed.
- [0008 — Webhook evidence trust boundary](0008-webhook-evidence-trust-boundary.md) — proposed security requirement.
- [0009 — Immutable amount snapshots and currency](0009-immutable-money-snapshots-and-currency.md) — proposed; currency policy requires owner approval.
- [0010 — Late payment after reservation expiry](0010-late-payment-after-reservation-expiry.md) — proposed; business/refund policy requires owner approval.

Each record should include:
- Status and date.
- Context and constraints.
- Decision.
- Alternatives considered.
- Consequences and trade-offs.
- Tests or evidence.
- Open questions.
