# Phase 3 payment architecture proposal

**Status: Proposed; no provider or financial policy is approved by this document.** No payment code is implemented by this review.

## Goals

- Keep orders and fulfillment provider-independent.
- Keep provider credentials and provider-specific API semantics inside separate adapters.
- Base fulfillment on persisted, server-verified payment evidence rather than client assertions or a Python type.
- Make retries, duplicate webhook delivery, missing callbacks and ambiguous network outcomes recoverable.
- Preserve auditability without retaining unnecessary cardholder or customer data.

## Proposed components

```text
API checkout operation
  -> Order/payment application service
  -> PaymentAttempt persistence (one order can have multiple attempts)
  -> Provider interface
      ├── Paystack adapter (candidate first)
      └── Daraja adapter (independent future option)

Provider webhook -> raw-body authentication -> durable inbox/evidence
                 -> provider-side verification/reconciliation
                 -> idempotent payment transition
                 -> order fulfillment transaction
```

The API should create a local payment attempt before initiating an external charge. Persisting first gives the callback and reconciliation jobs a stable local association. A provider timeout after sending a request is ambiguous: mark the attempt as initiation-unknown/pending verification and query or reconcile it before creating another active attempt.

## Persistence proposal

1. **PaymentAttempt**: foreign key to order; provider and merchant-account/environment identifiers; local attempt/idempotency reference; provider transaction reference; amount and currency snapshot; normalized status; timestamps; minimal channel metadata. Uniqueness must be scoped to provider account and environment. One order may have sequential attempts, but avoid concurrent unresolved charge attempts until the owner approves a different policy.
2. **PaymentEvent / evidence record**: append-only receipt of authenticated/observed provider events and verification decisions. Store stable provider event identity when available, normalized event type/status, provider reference, payload digest, received/verified timestamps and outcome. Retain full raw payload only if required, encrypted and under a documented retention policy. Never store card PAN/CVV or provider credentials.
3. **Refund record or refund attempts**: model provider refund references, amount/currency and pending/processing/failed/complete state if refunds are brought into scope. Do not represent a refund request as a completed refund.

These names and fields are a proposal, not a schema commitment. A migration and retention design belong to an authorized Phase 3 implementation plan.

## Provider-neutral interface

The application service should depend on narrow operations such as `initialize(attempt)`, `verify(reference)`, `parse_and_authenticate_webhook(raw_request)`, and `request_refund(verified_payment, amount)`. Provider adapters translate their native states, currencies, references, callback behavior, and API errors. The application must not infer that a provider result means order fulfillment is safe; the service checks order ownership/association, attempt state, expected amount/currency and reservation state inside a transaction.

Do not persist a generic provider status as the sole source of truth. Preserve provider-native references/status metadata needed for support and reconciliation while exposing a small normalized payment state machine to the domain.

## State separation

The order state answers “may this order be fulfilled/cancelled/expired?” The payment state answers “what has the provider reported and what has this system independently verified?” These are related but not identical. For example, a payment may be verified successful after its order reservation has expired; that payment must not silently reopen the reservation or issue tickets.

Suggested normalized payment states for review: `CREATED`, `INITIATION_UNKNOWN`, `PENDING_CUSTOMER`, `PENDING_PROVIDER`, `VERIFY_REQUIRED`, `SUCCEEDED`, `FAILED`, `CANCELLED`, `EXPIRED`, `REFUND_PENDING`, `REFUNDED`, and `REVIEW_REQUIRED`. The final set and allowed transitions need review against chosen provider(s) and business policies.

## Monetary representation

Current models use `Decimal` and `Numeric(10,2)` but do not define currency. Do not initiate a payment while the expected order currency is null. Keep values in exact decimal/integer form; never use binary floating point. At the provider boundary convert to the provider's documented minor units with explicit currency exponent handling. Compare verified currency and amount to the immutable attempt snapshot, not to mutable current ticket price. Owner approval is required for the supported currency set, authoritative price currency and whether ticket tiers may be multi-currency.

## Fulfillment transaction boundary

Only after independent verification should a transaction lock the order, its active attempt and the ticket-type inventory, validate expected amount/currency/reference and current order eligibility, then perform a single idempotent order/payment/ticket/inventory transition. Store the verified result and all fulfillment writes atomically. Repeated verification/webhook deliveries must return the already-applied outcome and must not issue tickets or change counters twice.

If payment succeeded but the order is cancelled/expired or another attempt already fulfilled it, record the successful payment as such and route it to an explicit exception/refund path. Do not re-reserve scarce inventory or silently mark it fulfilled.

## Open owner decisions

- Approve Paystack as the first adapter, subject to dashboard and merchant agreement checks, or choose Daraja first.
- Decide supported currency, displayed ticket currency and settlement currency policy.
- Decide merchant of record, organizer split/subaccount model, fee allocation, refund authority and chargeback responsibility. Existing `OrganizerProfile` Paystack fields do not settle these questions.
- Decide whether one unresolved payment attempt per order is mandatory and when a replacement attempt may start.
- Decide whether a late verified success is automatically refunded, held for manual review, or can be fulfilled only after explicit inventory revalidation.
- Approve refund authorization, partial refunds, and customer/support operations.
- Set payment-evidence/raw-webhook retention, privacy and audit requirements.

## Related records

- [Provider comparison](../payments/provider-comparison.md)
- [Payment lifecycle and reconciliation](../payments/lifecycle-and-reconciliation.md)
- [Threat model](../security/threat-model.md)
- [ADRs 0005–0010](../decisions/README.md)
