# ADR 0007: Separate order, payment and fulfillment state

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

The current `OrderStatus` includes historical pending/success/failed/completed/cancelled/expired/payment-failed values, while provider outcomes can be delayed or arrive after reservation expiry. Package 2 adds separate payment-attempt, fulfillment-claim, refund, webhook receipt and reconciliation persistence; no state-transition service exists yet.

## Decision

Represent order/reservation, payment attempt, ticket fulfillment and refund as separate lifecycles. Persist provider success as a financial fact independently of fulfillment. Fulfillment requires authenticated provider verification plus a single atomic check of the order, reservation and inventory. Exact normalized state names and transition implementation remain technical design work.

## Alternatives considered

- Put all state on `Order`: conflates repeated attempts, reservation and refunds.
- Treat provider success as order completion: permits fulfillment after expiry, duplicate charges or mismatched amount/currency.

## Consequences

Multiple payment attempts and exception/refund paths need persistence. Existing enum labels and rows must not be reinterpreted or backfilled without evidence. New schema evolution must be forward-only and data-preserving.

## Security and operations

Client status and webhook payload alone cannot change payment state. Reconciliation resolves missing or contradictory evidence. Payment success is not proof that funds cleared to the platform or that organizer funds were paid.

## Evidence and references

Current [`Order`](../../app/models/order.py), [`OrderStatus`](../../app/models/enums.py) and [`orders service`](../../app/services/orders.py); Paystack [Verify Payments](https://paystack.com/docs/payments/verify-payments/) recommends server-side verification and exact transaction checks.

## Implementation refinement from Package 2

The schema defines explicit native payment/refund/webhook/reconciliation enum labels, provider/account/environment uniqueness, idempotency keys, audit immutability and one fulfillment claim per order. The claim is tied to a `SUCCEEDED` attempt for the same order but is not proof of provider authentication. Transaction locking, state-transition authorization, webhook retention duration, cumulative refund policy and raw evidence needs remain service/operations decisions. Preserve this separation.
