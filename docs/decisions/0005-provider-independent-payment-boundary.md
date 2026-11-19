# ADR 0005: Provider-independent payment boundary

- **Status:** Proposed; owner approval required before Phase 3 schema implementation
- **Date:** 2026-11-19

## Context

The current domain has no payment-attempt entity or provider adapter. The order model contains one local payment reference and one optional evidence string. Paystack and direct Safaricom Daraja have different channels, references, verification paths and callback behaviors.

## Decision

Propose a canonical internal payment-attempt/evidence model and narrow provider adapter interface. Keep provider-specific credentials, references and payload normalization within adapters. Orders and fulfillment must not depend on provider-native status values.

## Alternatives considered

- Put provider-specific fields and branching directly on `Order`: simpler initially but couples order state and migration history to a vendor.
- Implement one provider with no boundary: faster for a single flow but makes second-provider support and deterministic tests harder.
- Build a multi-provider routing framework now: premature; the proposal needs only a small adapter contract.

## Consequences

An order may have multiple sequential attempts, and each provider transaction is independently identifiable. Adding persistence, retention and reconciliation logic is required before payment code. Provider portability reduces domain coupling but does not remove settlement, refund, pricing or reconciliation migration costs.

## Security and operations

Credentials stay external; incoming events are authenticated and independently verified. Persist only necessary provider metadata and evidence. Reconciliation and support procedures are required.

## Evidence and references

Source review: [`Order`](../../app/models/order.py), [`OrderStatus`](../../app/models/enums.py), [`orders service`](../../app/services/orders.py). Provider behavior differs in [Paystack transaction/webhook docs](https://paystack.com/docs/payments/verify-payments/) and [Safaricom Daraja](https://developer.safaricom.co.ke/).

## Open questions

Approve this structure and the persistence/retention boundaries before migrations are designed.
