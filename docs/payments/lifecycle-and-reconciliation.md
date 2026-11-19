# Payment lifecycle and reconciliation

**Status:** accepted requirements; no payment integration is implemented. Initial provider is Paystack, initial currency KES, platform collection with separate organizer settlement, and late verified payment after reservation expiry is refunded without issuing tickets.

## Four independent lifecycles

1. **Order/reservation:** pending inventory hold, fulfilled, cancelled or expired. Phase 2 expiry releases inventory.
2. **Payment attempt:** provider-side transaction outcome and our independently verified result.
3. **Ticket fulfillment:** entitlement issuance only after verified payment and a transactionally valid reservation/inventory check.
4. **Refund:** separate asynchronous return of captured funds; a successful payment remains historically successful even if refunded.

Do not collapse these statuses onto one `OrderStatus`. Payment success does not imply order fulfillment or organizer settlement.

## Normalized payment state machine

Suggested canonical states (exact enum/storage labels are implementation decisions):

| State | Meaning | Allowed next states |
|---|---|---|
| `INITIALIZING` | Local attempt persisted; provider request not yet resolved | `PENDING`, `FAILED`, `INITIATION_UNKNOWN` |
| `PENDING` | Provider accepted/awaiting customer or provider outcome | `SUCCEEDED`, `FAILED`, `EXPIRED`, `RECONCILIATION_REQUIRED` |
| `INITIATION_UNKNOWN` | Request timed out or response lost; may exist at provider | `PENDING`, `SUCCEEDED`, `FAILED`, `RECONCILIATION_REQUIRED` after verification |
| `SUCCEEDED` | Server-side verification confirms exact transaction and snapshot | remains `SUCCEEDED`; separate refund lifecycle may begin |
| `FAILED` | Provider verification confirms terminal failure | terminal; a new attempt is a distinct record |
| `EXPIRED` | Provider confirms terminal expiry/abandonment or applicable expiry policy is verified | terminal; late success contradicting this requires reconciliation |
| `RECONCILIATION_REQUIRED` | Missing, inconsistent or ambiguous provider result | verified `PENDING`, `SUCCEEDED`, `FAILED`, `EXPIRED`; otherwise remains unresolved |

Refund state is separate: `NOT_REQUESTED`, `PENDING`, `PROCESSING`, `REFUNDED`, `FAILED`, `NEEDS_RECONCILIATION` (or equivalent). Only provider-confirmed refund status establishes `REFUNDED`; request acceptance/queueing is not completion.

### State transition authority

- **Synchronous initialization response:** accepted/action required -> `PENDING`; definitive rejection -> `FAILED`; timeout/network ambiguity -> `INITIATION_UNKNOWN`, never assumed failure.
- **Client redirect/request:** may provide a reference to look up; cannot set payment status.
- **Webhook:** authenticated origin/integrity may create a durable receipt and enqueue verification. It does not directly mark success/failure. An invalid signature is rejected; a valid but unmatched payload is quarantined.
- **Server-side transaction verification:** may set success only when provider account/environment, transaction reference, expected order association, exact integer amount, and KES currency match. A confirmed terminal provider failure may set `FAILED`; pending/ongoing statuses remain pending.
- **Scheduled/manual reconciliation:** queries unresolved/missing-callback attempts, applies the same verification checks, records findings and is safe to repeat. It does not blindly overwrite terminal states.
- **Refund confirmation:** only provider refund verification/notification followed by independent status confirmation can set refund `REFUNDED`.

Paystack's current Verify Payments documentation says webhook notifications currently cover successful transactions; query verification is needed for pending/failure and missing callback resolution. Its webhook guidance requires signature verification on the raw body, timestamp freshness where signed timestamp is supplied, constant-time HMAC comparison and acknowledges retries. Webhook resend is not treated as idempotent; local inbox deduplication remains mandatory.

## Initialization, idempotency and event ordering

Persist the payment attempt and immutable amount/currency snapshot before provider I/O. Generate a unique local reference and bind the provider transaction reference under provider account plus environment uniqueness. One order may have several historical attempts, but do not start a second unresolved charge while the first is ambiguous. Provider-specific idempotency availability/semantics must be confirmed in the adapter contract; local uniqueness and verify-before-retry are still required.

Persist webhook receipt and deduplication key before acknowledging durable intake. Prefer stable provider event ID; otherwise use a carefully scoped account/environment/reference/event/digest key. Reverify against provider state even after a duplicate or reordered webhook. Stale events cannot regress a verified terminal state. Contradictory terminal evidence triggers reconciliation and an audit finding, not last-write-wins.

For an ambiguous initialization, refund or query request, do not blindly retry the side effect. First query by stable reference; retry only where provider semantics and local idempotency make it safe. Store each reconciliation run/outcome and make replay a no-op for already-applied effects.

## Fulfillment and late success

For every verified success, lock the attempt, order/reservation and relevant inventory in one database transaction. Check exact attempt/order/reference and immutable amount/currency, then verify reservation remains eligible and inventory is still held. Commit payment fact and eligible ticket/order/inventory transitions atomically and once. On mismatch, duplicate successful charge or ineligible order, persist the verified financial fact and route to an exception path; never issue a ticket merely because a provider succeeded.

For late success after reservation expiry/cancellation or when inventory is unavailable:

1. Independently query Paystack and validate merchant/account, environment, reference, amount and KES currency.
2. Persist immutable verified transaction evidence.
3. Check reservation status and inventory eligibility under transaction/locking.
4. If expired/ineligible/no inventory, issue no ticket and do not reopen or reacquire inventory implicitly.
5. Create one authorized, idempotent refund attempt referencing the original transaction; persist local and provider references/status.
6. Query/consume authenticated refund updates until provider confirms completion; escalate failure, timeout, `needs-attention` or prolonged pending to an audited manual queue.

Duplicate refund actions reuse the same local refund identity/reference. A timeout is an unknown outcome and must be queried before retry. Multiple partial/full refunds must respect provider-confirmed cumulative refunded amount and the internal authorization record. A failed refund does not erase payment success or prove money returned. Customer notification must reflect verified refund status only.

## Platform collection and organizer settlement

Provider transaction records establish customer payment facts, not organizer balances. Record gross captured amount, provider fees when evidenced, refunds, platform revenue and organizer liability as separate per-currency accounting movements. Keep a balanced traceable journal with unique source references. Do not call a provider-success amount cleared funds until settlement evidence supports it. Organizer payout has its own record/reference/state; initiated is not paid, and liability changes only on provider-confirmed/reconciled payout. Commercial rules for commission, taxes, reserves, deductions and timing remain undefined and must not be inferred.

## Reconciliation and operations

Reconcile attempts missing callbacks, provider success/local pending, local success/provider disagreement, unmatched references, multiple successes, amount/currency mismatches, provider settlement variance, refunds and organizer payouts. Use bounded time windows, rate limits, durable run IDs, idempotent updates, audit actor/source and retryable exception states. Keep unmatched/conflicting events for investigation without fulfilling. Reconciliation must support replay and manual escalation without editing historical records silently.

## Required tests before release

- State transition table tests for each allowed and rejected transition/source.
- Forged, malformed, changed-body, stale/future and rotated-key webhook signatures.
- Duplicate, reordered, delayed, resent and missing webhook deliveries.
- Verified amount/currency/account/environment/reference mismatch.
- Initialization/verification/refund timeouts before and after provider acceptance.
- Repeated reconciliation and duplicate payment/refund processing.
- Concurrent payment attempts; expiry/cancellation against success; inventory unavailable after late success.
- Duplicate refund, partial refund cap, failure/attention and delayed confirmation.
- Atomic rollback and PostgreSQL concurrency/uniqueness tests.
- Ledger balancing, unique source application, settlement mismatch and payout confirmation invariants.

Mocks support unit tests; only an isolated PostgreSQL environment can verify database transaction/locking guarantees. Provider sandbox tests do not establish live account eligibility or merchant terms.

## Official sources (reviewed 2026-11-19)

- Paystack [Verify Payments](https://paystack.com/docs/payments/verify-payments/)
- Paystack [Webhooks](https://paystack.com/docs/payments/webhooks/)
- Paystack [Refunds](https://paystack.com/docs/payments/refunds/)
- Paystack [Payment Channels](https://paystack.com/docs/payments/payment-channels/)
