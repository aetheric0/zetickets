# ADR 0009: Immutable purchase amount snapshots and explicit currency

- **Status:** Proposed technical direction; currency policy requires owner approval
- **Date:** 2026-11-19

## Context

The current order snapshots decimal `unit_price` and `total_amount`; `currency` is nullable and reservation code sets it to `None`. Ticket-type price has no currency. Paystack APIs accept provider currency and minor-unit amount; advertised currencies/settlements do not decide Zetickets' product pricing policy.

## Decision

Propose that each payment attempt capture immutable expected amount and ISO currency derived server-side from an explicit order pricing snapshot. Never start checkout with unknown currency. Use exact decimal/integer arithmetic, never floats; convert to provider subunits using explicit currency exponent rules and compare verified amount/currency to the attempt snapshot. Do not update old rows with guessed currencies.

This ADR does not yet select KES-only, KES plus USD, or tier-specific currency. Owner approval is required for allowed currencies, ticket display currency, FX/pricing source and settlement currency. Keep existing fields until a schema decision is approved.

## Alternatives considered

- Default all rows to KES: fabricates a financial fact and is rejected.
- Use binary float: risks rounding and mismatch errors.
- Snapshot only current tier price at verification: permits later price edits to change an existing purchase.
- Immediately replace decimals with integer minor units: may be viable, but needs a broader migration/API contract review; no change is made here.

## Consequences

Checkout remains blocked for orders with unknown currency. Payment amount, currency, fee/settlement amount and FX must not be conflated. Legacy NULLs require evidence-backed reconciliation only.

## Security and operations

Reject client-supplied amount/currency overrides. Verify provider account, environment, expected amount and currency. Audit mismatches; refund or resolve under approved policy.

## Evidence and references

Source: [`Order`](../../app/models/order.py), [`TicketType`](../../app/models/ticket.py), [`reservation service`](../../app/services/orders.py). Paystack [API currency reference](https://paystack.com/docs/api/) describes currency subunits; [Kenya pricing](https://paystack.com/ke/pricing) lists public KES/USD options. Accessed 2026-11-18.

## Open questions

Owner approval is mandatory for currency, pricing, FX and settlement policy before payment initialization is implemented.
