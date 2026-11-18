# ADR 0004: Payment Evidence Boundary

- **Status:** Accepted; successful payment verification deferred to Phase 3
- **Date:** 2026-11-18

## Context

The existing checkout operation marked an order complete based only on an authenticated client request. No trusted payment verifier or currency source exists.

## Decision

- Client checkout requests cannot complete an order; the existing operation returns a conflict until trusted payment evidence is available.
- The service accepts a provider-neutral `VerifiedPaymentFailure` only for an internal caller, records its reference, and releases a pending reservation atomically. The type itself is not proof of authenticity; Phase 3 must ensure only a verifier constructs/passes it.
- Preserve legacy `FAILED` without assigning it new meaning. Use explicit `PAYMENT_FAILED` for the new trusted-failure path.
- Do not implement successful payment completion until Phase 3 defines trusted evidence and the product's currency source. Currency remains nullable and is never guessed.

## Alternatives considered

- Continue client-triggered completion. Rejected because it lets a client assert payment success.
- Add payment-provider or currency configuration now. Deferred to Phase 3 and requires a business/provider decision.

## Consequences and evidence

Checkout rejection is covered by the database-independent service suite. Trusted failure evidence handling is verified for transaction/release behavior on the disposable PostgreSQL 18.6 database; no provider integration or new route is added. Successful payment verification and any provider-specific security are not implemented.

## Open questions

- Which payment provider and verification channel will Phase 3 use?
- What currency is authoritative for ticket pricing and order evidence?
- How should a verified success arriving after reservation expiry be reconciled/refunded?
