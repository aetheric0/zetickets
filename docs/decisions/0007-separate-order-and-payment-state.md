# ADR 0007: Separate order fulfillment from payment state

- **Status:** Proposed; owner approval required for terminal order semantics
- **Date:** 2026-11-19

## Context

Current `OrderStatus` includes pending, successful, failed, completed, cancelled, expired and payment-failed values, while no payment-attempt lifecycle exists. Legacy values cannot be safely reinterpreted. Provider results can arrive asynchronously or after reservation expiry.

## Decision

Propose separate normalized payment-attempt status from order/reservation/fulfillment status. Persist provider success as a financial fact even when fulfillment cannot proceed. Derive order completion only after verified payment and an atomic, eligible fulfillment transaction.

## Alternatives considered

- Continue representing every payment state on the order: risks conflating delayed attempts, refunds and fulfillment.
- Treat provider success as order completion: unsafe for expired/cancelled orders, duplicates or mismatched amount/currency.

## Consequences

The domain will support multiple payment attempts and explicit exception/refund states. Existing enum labels remain for compatibility; no backfill or legacy translation is proposed. Payment-attempt and likely refund/evidence persistence require a new forward migration after schema design.

## Security and operations

Only provider-verified evidence may advance payment state. Payment success is not sufficient for fulfillment: verify account/mode, reference, amount/currency and order eligibility. Conflicts enter reconciliation.

## Evidence and references

Current model/service review: [`Order`](../../app/models/order.py), [`OrderStatus`](../../app/models/enums.py), [`orders service`](../../app/services/orders.py). Paystack recommends server verification and amount comparison in [Verify Payments](https://paystack.com/docs/payments/verify-payments/). Accessed 2026-11-18.

## Open questions

Owner/product review must approve the order's terminal state semantics and handling of multiple successes/refunds.
