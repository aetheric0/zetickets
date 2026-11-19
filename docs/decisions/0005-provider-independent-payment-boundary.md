# ADR 0005: Provider-independent payment boundary

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

Paystack is the owner-approved initial provider. Future providers have different channel flows, references, callback formats, verification and refunds. Current orders do not have a payment-attempt model.

## Decision

Use canonical internal payment attempts/evidence and a narrow provider adapter for initialization, transaction verification, webhook authentication/normalization, refund initiation/status verification and transaction reconciliation. Implement Paystack first; keep provider-specific semantics inside its adapter. Daraja remains a future option outside the initial implementation scope.

## Alternatives considered

- Provider-specific state and branching on `Order`: couples order history to vendor behavior.
- Implement Paystack without a boundary: smaller first patch, but makes domain verification and future adapter replacement harder to test.
- Multi-provider routing framework: unnecessary before a second provider is approved.

## Consequences

An order can have multiple distinct attempts; unresolved attempts require verify-before-retry. Provider transaction references are unique within provider account/environment. This requires new persistence and reconciliation; the current code does not implement it.

## Security and operations

Only provider verification performed by the trusted application service can produce a persisted verified result. Internal Python dataclasses and caller-provided statuses are not proof. Credentials and provider formats remain in adapters; sandbox/live accounts are distinct.

## Evidence and references

Source review: [`Order`](../../app/models/order.py), [`OrderStatus`](../../app/models/enums.py), [`orders service`](../../app/services/orders.py). Official [Paystack Verify Payments](https://paystack.com/docs/payments/verify-payments/) and [webhooks](https://paystack.com/docs/payments/webhooks/) reviewed 2026-11-19.

## Open implementation questions

Exact fields, event/raw-payload retention, provider idempotency guarantees, and evidence retention/encryption require design before schema implementation. They do not reopen the accepted provider-independent boundary.
