# ADR 0008: Authenticated provider evidence is required

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

There is no payment verifier or webhook route. Phase 2's `VerifiedPaymentFailure` dataclass can be constructed by ordinary Python callers; its name/type does not authenticate a provider. Paystack documents signed webhook requests and transaction verification.

## Decision

Webhook intake authenticates raw bytes using Paystack's currently documented signature scheme, applies freshness/key-rotation checks, deduplicates and stores a durable receipt. A webhook is only a signal to independently verify the transaction server-to-server. The trusted payment service itself calls the provider adapter, validates provider/account/environment/reference/order/amount/currency and persists the verification outcome. Do not accept a caller-constructible status/result object as proof, and do not allow an untrusted payload or browser request to set success or failure.

## Alternatives considered

- Trust a webhook `success` value: allows forged or mismatched fulfillment.
- Trust a redirect: browser navigation is neither complete nor trustworthy evidence.
- Treat a Python type as a capability: any in-process caller can construct it.
- Poll only: useful fallback, but slower and still needs verified provider state.

## Consequences

Requires a durable inbox, verification service, uniqueness/idempotency, secret rotation and reconciliation. Raw-body retention, encryption, redaction and retention duration need explicit privacy design.

## Security and operations

Use raw bytes, HMAC verification with constant-time compare and provider freshness/key-rotation rules. A valid signature establishes origin/integrity, not order association or amount correctness. Invalid/unmatched/conflicting events are quarantined and audited; they never fulfill.

## Evidence and references

Paystack [Webhooks](https://paystack.com/docs/payments/webhooks/) and [Verify Payments](https://paystack.com/docs/payments/verify-payments/), reviewed 2026-11-19. Current webhook docs describe timestamped `Paystack-Signature`, multiple key-ID signatures, HMAC-SHA512 over timestamp plus raw body and a documented timestamp window; implementation must recheck current docs.

## Open implementation details

Define durable acknowledgement, event identity/dedupe, key rotation overlap, data retention and incident procedures as implementation work. No payment behavior is implemented by this ADR.
