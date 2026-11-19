# ADR 0008: Webhook intake is a signal, not standalone payment proof

- **Status:** Proposed security requirement; implementation belongs to Phase 3
- **Date:** 2026-11-19

## Context

There is no webhook route or payment verifier. Phase 2's `VerifiedPaymentFailure` Python dataclass is constructible by ordinary application code, so type naming cannot establish authenticity. Paystack supports signed webhook validation and server-side transaction verification; Daraja provides asynchronous callbacks and status queries.

## Decision

Propose a durable webhook inbox: capture raw body as needed, authenticate with the provider's current documented mechanism, deduplicate, persist the receipt, independently verify provider transaction state and amount/currency/reference/account, and only then call an idempotent payment service. Callback payloads and internal status objects alone never trigger success fulfillment.

## Alternatives considered

- Trust a callback's `success` boolean: vulnerable to forgery, mismatch and replay.
- Verify only browser redirects: client navigation is not proof and can be forged or omitted.
- Poll only: can miss real-time outcomes and creates rate/latency costs; remains a useful reconciliation fallback.

## Consequences

Requires event receipts, verification outcomes, uniqueness/idempotency behavior, key rotation and monitoring. It adds storage and operational support responsibilities. Daraja's exact callback authentication guarantee requires account-specific confirmation.

## Security and operations

Verify signatures against raw bytes, use constant-time comparison, enforce provider timestamp/key rotation rules where available, separate test/live credentials, minimize logs, and alert on invalid/unmatched/conflicting events. Provider API verification remains authoritative for fulfillment.

## Evidence and references

- Paystack [Webhook security and retries](https://paystack.com/docs/payments/webhooks/), [payment verification](https://paystack.com/docs/payments/verify-payments/).
- Safaricom [Transaction Status](https://developer.safaricom.co.ke/apis/TransactionStatus) for asynchronous missing-callback reconciliation.
- Reviewed 2026-11-18.

## Open questions

Confirm Daraja callback security/retry behavior and decide payload retention and durable acknowledgement semantics before building the inbox.
