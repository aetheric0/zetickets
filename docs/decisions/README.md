# Architecture Decision Records

Store material, durable engineering decisions here. Phase 1/2 records 0001–0004 are existing decisions. ADRs 0005–0011 record the accepted Phase 3 direction; unresolved implementation and account/commercial matters are stated inside each record.

- [0001 — Preserve unknown historical values](0001-preserve-unknown-historical-values.md) — accepted.
- [0002 — Transactional inventory locking and expiry](0002-transactional-inventory-locking.md) — accepted; fresh disposable PostgreSQL verification recorded.
- [0003 — Reservation idempotency](0003-order-idempotency.md) — accepted.
- [0004 — Payment evidence boundary](0004-payment-evidence-boundary.md) — accepted; successful payment deferred.
- [0005 — Provider-independent payment boundary](0005-provider-independent-payment-boundary.md) — accepted; Paystack first, Daraja future option.
- [0006 — Paystack initial provider](0006-paystack-first-provider-candidate.md) — accepted; account readiness remains to verify.
- [0007 — Separate order, payment and fulfillment state](0007-separate-order-and-payment-state.md) — accepted.
- [0008 — Authenticated provider evidence](0008-webhook-evidence-trust-boundary.md) — accepted requirement; implementation not present.
- [0009 — Immutable money snapshots and KES-first policy](0009-immutable-money-snapshots-and-currency.md) — accepted; multi-currency extensibility only.
- [0010 — Refund late success after reservation expiry](0010-late-payment-after-reservation-expiry.md) — accepted.
- [0011 — Platform collection and organizer settlement](0011-platform-collection-and-organizer-settlement.md) — accepted direction; commercial terms remain open.

Each record should include:
- Status and date.
- Context and constraints.
- Decision.
- Alternatives considered.
- Consequences and trade-offs.
- Tests or evidence.
- Open questions.
