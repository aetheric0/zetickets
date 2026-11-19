# ADR 0010: Refund verified late payments after reservation expiry

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

Phase 2 expires reservations and releases inventory. An asynchronous M-PESA/card result can succeed after that inventory is released or sold. Owner has explicitly selected a refund for late success and prohibited ticket issuance without valid inventory.

## Decision

For a late reported success: independently verify it with Paystack; persist the verified transaction evidence; inspect reservation status and inventory eligibility; do not issue a ticket if reservation expired/cancelled or valid inventory is unavailable; initiate one idempotent refund; persist the refund attempt and provider reference; reconcile until confirmed refunded or escalated for manual handling. Never reopen/reacquire inventory implicitly. A refund request is not a completed refund.

## Alternatives considered

- Automatically reopen and fulfill: risks oversell and violates approved direction.
- Ignore verified success: leaves customer funds unresolved.
- Hold funds without a defined process: no customer resolution and poor auditability.

## Consequences

Requires durable payment evidence, refund lifecycle, idempotent references, reconciliation and an operator exception queue. Refund failure does not erase successful payment; delayed confirmation remains pending/reconciliation-required.

## Security and operations

Provider verification must match account/environment/reference/order/amount/currency. Refund operations require authorization and auditable actor/reason; ambiguous timeouts are queried before retry. Do not claim the refund complete until provider confirmation.

## Evidence and references

Phase 2 [`expiry service`](../../app/services/orders.py) releases inventory for due orders. Paystack [Verify Payments](https://paystack.com/docs/payments/verify-payments/) and [Refunds](https://paystack.com/docs/payments/refunds/) document server verification and asynchronous refund processing (reviewed 2026-11-19).

## Open implementation details

Account/channel refund eligibility, customer communication, escalation ownership and refund processing SLAs require operational/account-specific definition. These do not change the approved late-success outcome.
