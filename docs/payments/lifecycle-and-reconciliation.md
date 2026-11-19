# Payment lifecycle and reconciliation proposal

**Proposal only.** Provider sequencing, money policy, late-payment behavior and refund authority require owner approval. No payment integration is present today.

## Candidate lifecycle

```text
Order reservation PENDING
  -> persist PaymentAttempt CREATED
  -> call selected provider
     -> accepted/pending customer action
     -> definitive initialization failure
     -> ambiguous timeout (INITIATION_UNKNOWN; verify before retry)
  -> authenticated webhook and/or scheduled/manual reconciliation
  -> independently verify provider result and match attempt/order/amount/currency
     -> payment SUCCEEDED + eligible order fulfilled atomically
     -> payment FAILED/EXPIRED; reservation release follows order policy
     -> conflict/late success -> REVIEW_REQUIRED; never silently fulfill
```

Order state and payment state should be separate. Payment status is a statement about an attempt and evidence; order status is a statement about inventory reservation and fulfillment. A provider event may arrive late or out of order, and a successful payment can exist even if an order is no longer fulfillable.

## Initialization and association

- Create a local payment attempt with immutable order ID, amount, currency, provider mode/account and unique local reference before sending the provider request.
- Bind the provider transaction reference to that attempt under a uniqueness scope that includes provider account and test/live environment.
- Derive amount/currency from a persisted immutable purchase snapshot; never accept amount/currency from the browser/webhook as authoritative.
- If provider initialization times out ambiguously, query/verify by local/provider reference and reconcile before permitting a second unresolved charge attempt.
- Persist the provider response needed for support without storing credentials, card numbers or unnecessary personal data.

## Webhook inbox and trust

1. Capture the exact raw request bytes before JSON parsing when the provider's signature scheme requires it.
2. Verify signature using the provider-documented algorithm, active key rotation rules, constant-time comparison and a bounded timestamp where available.
3. Persist a durable event receipt before acknowledging if durable processing is required. Duplicate delivery must resolve to the existing receipt and never duplicate a transition.
4. Treat a valid signature as evidence of origin/integrity only; independently verify payment status and exact amount, currency, provider account, reference and intended order.
5. Process through a transaction with deterministic row locking. Store failed validation/conflict outcomes for monitoring without making them fulfillment evidence.
6. Return provider-required acknowledgements quickly after durable intake; run slow verification/reconciliation outside the request path where needed.

Paystack documents timestamped signatures and retries, while its webhook events currently emphasize successful payment notification. Daraja's status query is documented as an asynchronous secondary reconciliation route for missing callbacks. Exact Daraja callback authentication/retry behavior must be confirmed for the selected API and merchant account.

## Idempotency and ordering

- Give local attempts and refund attempts stable idempotency references.
- Use provider event IDs when the provider guarantees a stable identifier; otherwise use a carefully scoped dedupe key (provider account, environment, transaction reference, event type and payload digest) and still query provider state. Do not assume webhook resend is idempotent.
- Treat repeated same-state verification as a no-op. Reject or quarantine conflicting terminal results; reconcile from provider-authoritative state and audit the resolution.
- Apply each fulfillment exactly once under database uniqueness/state checks and one transaction. A second successful payment for an already fulfilled order is a separate duplicate-payment exception and refund decision.
- Do not regress a verified terminal state based on stale/out-of-order callbacks.

## Reconciliation operations

Reconcile unresolved attempts by provider reference and local date window; identify attempts missing callbacks, webhook delivery failures, provider-success/local-pending mismatches, local-success/provider-disagreement, duplicate provider transactions, settlement variances and refund status differences. Use bounded queries, durable run IDs, rate limits, audit logs and retryable idempotent operations. Alert on age/amount/value thresholds. Restrict reconciliation and refund actions to authenticated, audited operators.

## Late success after expiry or cancellation

The current service expires/cancels reservations and releases inventory. It cannot safely re-open scarce inventory after a provider later reports success. Proposed safe default: persist payment success as a financial fact, mark fulfillment conflict for review, do not issue tickets or reacquire inventory implicitly, and make any refund an explicit authorized/reconciled operation. Whether to automatically refund, hold for manual review or permit fulfillment after inventory revalidation is a project-owner decision. Provider cancellation/refund may be irreversible or asynchronous.

## Refund lifecycle

Keep refund request and refund settlement separate. Persist a local refund ID/reference and amount/currency; send at most once under that reference; treat provider timeout as unknown until fetched; consume refund status notifications and query/reconcile; do not tell a customer a refund completed until provider evidence confirms completion. Keep original payment as successful and attach a separate refund/reversal state rather than erasing payment history.

## Required scenario tests before release

- Valid/invalid signatures, key rotation, body alteration and stale timestamps.
- Duplicate, delayed, reordered, resent, missing and malformed event deliveries.
- Provider verify status/amount/currency/reference/account mismatch.
- Timeout before request accepted, timeout after accepted, repeated verify and provider downtime.
- Same-order concurrent attempts, duplicate successful attempts and transaction-reference collisions.
- Payment success after expiry/cancellation and during concurrent cancellation/expiry.
- Refund retry after timeout, refund failure/needs-attention and duplicate refund request.
- Transaction rollback proves payment, order, ticket and inventory remain consistent.
- Reconciliation can be rerun safely and identifies manually injected ledger/provider discrepancies.

Use provider sandbox plus a disposable PostgreSQL environment for integration tests. A mock or SQLite-only test is insufficient for transaction and uniqueness claims.
