# ADR 0009: Immutable money snapshots and KES-first currency policy

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

Orders contain decimal price snapshots and nullable currency; historical currency/price facts may be unknown. Ticket prices can change after reservation. Payment APIs require explicit amount and currency.

## Decision

Initial payment transactions use KES only. Design currency fields with explicit ISO codes so additional currencies can be supported later, but do not enable them now. Store financial amounts as integer minor units, use exact arithmetic only, and snapshot expected order/payment amount and currency immutably before provider initialization. Verify provider amount and currency exactly against that snapshot. Derive all amounts server-side; reject client overrides and unknown currency. Do not guess or backfill historical values.

## Alternatives considered

- Default historical nulls to KES: fabricates financial facts and is rejected.
- Floating-point arithmetic: risks rounding and mismatches.
- Re-read current ticket price at payment: allows later edits to alter an existing purchase.
- Enable multiple currencies initially: outside the approved first release.

## Consequences

Checkout remains unavailable for orders lacking an authoritative amount/currency snapshot. Conversion at the provider boundary must follow explicit currency exponents. Fees, FX, gross/net and settlement amounts are separate values; no implicit conversion or float is allowed.

## Security and operations

Reject amount/currency tampering; mismatch enters reconciliation and cannot fulfill. Record provider fees and settlement evidence separately. A successful payment is not proof that funds are cleared.

## Evidence and references

Current [`Order`](../../app/models/order.py), [`TicketType`](../../app/models/ticket.py), [`reservation service`](../../app/services/orders.py); Paystack [Verify Payments](https://paystack.com/docs/payments/verify-payments/) returns transaction amount/currency for comparison. Public [Kenya pricing](https://paystack.com/ke/pricing) does not determine this account's terms.

## Open implementation details

Define authoritative ticket price unit, conversion helpers, precision bounds and storage migration from current `Numeric` fields. Historical values remain nullable until evidence-backed reconciliation. Future currency activation requires explicit product/commercial policy.
