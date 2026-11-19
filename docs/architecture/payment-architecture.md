# Payment architecture

**Status:** accepted architecture direction. Package 2 adds persistence only; no provider integration, payment verification, payment orchestration or payment routes exist. Owner-approved decisions: Paystack is the initial provider, KES is the initial transaction currency, the platform collects/reconciles and pays organizers separately, and verified late success after reservation expiry is refunded without ticket fulfillment.

## Boundaries

Keep four lifecycles distinct: order/reservation (inventory hold and expiry), payment attempt (provider transaction outcome), ticket fulfillment (entitlement issuance), and refund (return of customer funds). A successful payment is a financial fact; it is not by itself permission to issue tickets. Existing runtime currently exposes only `GET /health`; these are design requirements, not available endpoints or implemented capabilities.

The application service will use a provider-neutral interface with operations to initialize a payment, verify a transaction, authenticate and normalize a webhook, initiate a refund, verify refund status, and reconcile transactions. A Paystack adapter is first. Paystack payloads, API responses, provider references, signature formats, native statuses and metadata remain inside that adapter. Daraja is a possible future adapter and is outside initial implementation scope.

Persist a local `PaymentAttempt` before calling a provider. It associates one order with provider/account/environment, a client reference and idempotency key, provider transaction reference, immutable integer-minor-unit amount/currency snapshot, normalized state and timestamps. Multiple attempts may exist; this persistence layer does not yet enforce orchestration policy for another ambiguous attempt. Provider references are unique within provider account and environment. A database uniqueness constraint on `PaymentFulfillment.order_id`, plus a composite FK/check requiring its attempt status to be `SUCCEEDED` for that same order, permits only one fulfillment claim per order even when multiple successful attempts are retained. It does not itself prove that success was provider-authenticated or issue ticket rows.

Package 2 persistence includes `WebhookEvent`, `Refund` and `ReconciliationRecord`. Webhook rows retain the event identity, SHA-256 digest, bounded metadata and separate authentication/processing statuses; raw request payloads and credentials are not stored. Receipt evidence and reconciliation observations are immutable; financial rows cannot be deleted through ordinary SQL. An event row, digest, authentication status or Python object is not authenticated provider evidence. Future webhook code must verify the raw request and independently query the provider before any payment transition. The trusted orchestration service must match merchant account, environment, reference, amount and currency. Phase 3 Package 1 removed the Phase 2 `VerifiedPaymentFailure` value and disabled that state-changing path; no payment transition is currently available.

## State and transaction rules

The canonical states and transition sources are defined in [payment lifecycle and reconciliation](../payments/lifecycle-and-reconciliation.md). Provider initialization acknowledgements can establish pending/action-required; only server-side provider verification may establish success or terminal failure. Webhooks prompt verification; scheduled reconciliation resolves missing or conflicting evidence. Fulfillment locks and checks the order/reservation and inventory, then commits payment evidence, eligible order transition, tickets and inventory atomically and idempotently.

For verified success after expiry/cancellation or unavailable inventory: persist the verified transaction, do not issue tickets or reacquire inventory implicitly, initiate one idempotent refund, persist its reference/status, and reconcile until provider-confirmed completion or manual escalation. A refund request is never a completed refund.

## Money and organizer accounting

Initial policy is KES only. Store money as integer minor units plus explicit ISO currency code; never use binary floating point. At the provider boundary use the documented KES exponent and compare exact verified amount and currency to immutable server-derived order/payment snapshots. Historical unknown money remains unknown; no guessed currency, price, quantity, fee or expiry may be backfilled. Currency design must permit additional explicit currency codes later without enabling them now.

Track gross customer payment, provider fee, refund, platform revenue and organizer liability as separate auditable accounting movements. Payment-provider transactions are not the organizer ledger. Maintain a traceable per-currency journal and reconcile it against provider transactions, settlement statements and payout records. Provider success does not establish cleared platform funds. Do not increase available organizer payable until the applicable funds are confirmed cleared and policy adjustments are known; do not reduce liability/mark paid until payout confirmation is independently recorded. Commission, taxes, reserves, fee allocation and payout timing remain commercial decisions.

Accounting invariants before implementation:

- Every verified capture maps to exactly one local payment attempt and one immutable order snapshot; amount and currency agree.
- Each financial movement is recorded once with a unique source reference; journal entries balance per currency.
- Fees, refunds, platform revenue and organizer payable are explicit components, never hidden in a net amount.
- Refunds reference the original capture; cumulative refund cannot exceed refundable captured value under provider-confirmed status.
- Pending/un-cleared receipts are not represented as withdrawable organizer funds.
- A payout request is not a completed payout; only verified provider confirmation reduces payable.
- Reconciliation is repeatable and leaves a recorded discrepancy instead of silently editing history.

## Security and operations

Phase 3 Package 1 resolved the JWT signing/verification mismatch: both use the required validated `JWT_SECRET` and `ALGORITHM`; invalid or absent values fail configuration. Deployments using only `SECRET_KEY` must configure `JWT_SECRET`. Never expose provider credentials. Separate sandbox/live credentials and account identities; rotate secrets without logging values. Prefer provider-hosted checkout to avoid handling card data. Authorization must enforce order ownership and narrowly scoped audited administrative refund/reconciliation/payout permissions.

Paystack documentation currently describes Kenya card and M-PESA channels, server-side transaction verification, webhook signatures and refunds. Account activation, enabled channels, live eligibility, settlement, merchant terms and refund capability must be checked for Zetickets before production. See [provider comparison](../payments/provider-comparison.md) and [security controls](../security/controls-and-verification.md).

## Persistence direction and open implementation details

Implemented schema records are `PaymentAttempt`, `PaymentFulfillment`, `WebhookEvent`, `Refund` and `ReconciliationRecord`, with explicit native PostgreSQL enums, KES-only positive integer amounts, provider/account/environment-scoped references, idempotency uniqueness, restrictive foreign keys and audit immutability triggers. Refunds may be multiple/partial records; no aggregate cap or refund policy is asserted, so orchestration must apply a separately approved/provider-confirmed cumulative limit. Organizer ledger/payout records remain a later package. Raw webhook retention is intentionally avoided; the digest supports comparison but is not enough to replay an event. A later implementation must retain only a minimized canonical verified observation or use a separately controlled encrypted evidence store if required. This migration requires fresh PostgreSQL verification; no existing database has been modified.

## References

- [ADRs 0005–0011](../decisions/README.md)
- [Paystack Verify Payments](https://paystack.com/docs/payments/verify-payments/)
- [Paystack Webhooks](https://paystack.com/docs/payments/webhooks/)
- [Paystack Refunds](https://paystack.com/docs/payments/refunds/)
