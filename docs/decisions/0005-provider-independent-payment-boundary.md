# ADR 0005: Provider-independent payment boundary

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

Paystack is the owner-approved initial provider. Future providers have different channel flows, references, callback formats, verification and refunds. Package 2 now provides payment-attempt/evidence/refund/reconciliation persistence, but no provider or payment behavior.

## Decision

Use canonical internal payment attempts/evidence and a narrow provider adapter for initialization, transaction verification, webhook authentication/normalization, refund initiation/status verification and transaction reconciliation. Implement Paystack first; keep provider-specific semantics inside its adapter. Daraja remains a future option outside the initial implementation scope.

## Alternatives considered

- Provider-specific state and branching on `Order`: couples order history to vendor behavior.
- Implement Paystack without a boundary: smaller first patch, but makes domain verification and future adapter replacement harder to test.
- Multi-provider routing framework: unnecessary before a second provider is approved.

## Consequences

An order can have multiple distinct attempts; unresolved attempts require verify-before-retry in future orchestration. Provider transaction references are unique within provider account/environment. Package 2 implements the persistence boundary; provider operations and verification remain deferred.

## Security and operations

Only provider verification performed by the trusted application service can produce a persisted verified result. Internal Python dataclasses and caller-provided statuses are not proof. Credentials and provider formats remain in adapters; sandbox/live accounts are distinct.

## Evidence and references

Source review: [`Order`](../../app/models/order.py), [`OrderStatus`](../../app/models/enums.py), [`orders service`](../../app/services/orders.py). Official [Paystack Verify Payments](https://paystack.com/docs/payments/verify-payments/) and [webhooks](https://paystack.com/docs/payments/webhooks/) reviewed 2026-11-19.

## Implementation refinement from Package 2

The persistence schema uses `PaymentAttempt`, `WebhookEvent`, `Refund`, `ReconciliationRecord` and a unique `PaymentFulfillment` claim. Webhook raw payloads are not retained; a digest and bounded metadata are persisted. Provider idempotency guarantees, adapter timeout/retry behavior, event retention duration and evidence incident procedures remain implementation/operations questions. They do not reopen the accepted provider-independent boundary.
