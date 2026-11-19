# ADR 0010: Late provider success after reservation expiry

- **Status:** Proposed safety default; business/refund policy requires owner approval
- **Date:** 2026-11-19

## Context

Phase 2 expires pending orders after ten minutes and releases reserved inventory. Providers can settle asynchronously; Paystack M-PESA prompts are asynchronous and Daraja exposes callback/status query flows. A delayed success may arrive after inventory is released or re-sold.

## Decision

Propose recording verified late payment as a payment fact, marking the order/payment for manual exception review, and never silently reopening the order or issuing a ticket without an explicit, atomic inventory eligibility decision. A refund is a separate, authorized, asynchronous operation and is not implied by marking an order failed/expired.

This is a conservative default proposal only. The owner must decide automatic refund versus manual review versus conditional fulfillment, service-level timing, customer communication and refund/chargeback responsibility.

## Alternatives considered

- Automatically re-open and issue: risks overselling and bypassing current event inventory rules.
- Ignore late provider success: leaves customer funds unresolved.
- Automatically refund every late success: may be unavailable, delayed, fee-bearing or require manual details depending on provider/account/channel.

## Consequences

Requires a late-success queue, reconciliation visibility and operational owner. Refund state must remain separate and be verified until provider confirms completion. No schema or behavior change is made in this review.

## Security and operations

Only independently verified provider evidence enters the exception queue. Refund initiation requires authorization, an idempotency reference and audit record. Reconcile refund and settlement results; avoid disclosing sensitive payment data in support tools.

## Evidence and references

- Phase 2 [`expiry service`](../../app/services/orders.py) releases inventory for due orders.
- Paystack [M-PESA channel flow](https://paystack.com/docs/payments/payment-channels/) is asynchronous; [refund guide](https://paystack.com/docs/payments/refunds/) documents pending/processing/needs-attention/failed/processed states.
- Safaricom [Transaction Status API](https://developer.safaricom.co.ke/apis/TransactionStatus) provides asynchronous status query for delayed callbacks.
- Reviewed 2026-11-18.

## Open questions

Owner approval required for the actual late-success, refund, customer-remediation and inventory policy.
