# Order and reservation lifecycle (implemented Phase 2 behavior)

Source of truth: [`app/services/orders.py`](../../app/services/orders.py), [`app/models/order.py`](../../app/models/order.py), [`app/models/ticket.py`](../../app/models/ticket.py), and the Phase 2 PostgreSQL integration tests in [`app/test_orders_postgres.py`](../../app/test_orders_postgres.py).

## Current reservation flow

1. Validate quantity (1–10) and an idempotency key.
2. Return an existing order for the same user/key if ticket type and quantity match; reject a mismatched replay.
3. Lock the ticket-type row and reject inactive or unreconciled inventory.
4. Check remaining inventory, increment reserved inventory and create a pending order plus reserved ticket rows in one transaction.
5. Snapshot the ticket price in `unit_price` and `total_amount`; currency remains unknown/null. Set expiry ten minutes after reservation creation.

## Current transitions

| Operation | Preconditions | Effects |
|---|---|---|
| Reserve | Active tier, known counters, sufficient capacity | Creates `PENDING` order and reserved tickets; increments reserved quantity. |
| Cancel | Owned pending order, known consistent inventory | Sets `CANCELLED`; releases reserved inventory once; cancels reserved tickets. |
| Expire | Due pending reservation, known consistent inventory | Sets `EXPIRED`; releases inventory once; expires reserved tickets. Uses bounded `SKIP LOCKED` batches. |
| Verified payment failure | Internal caller supplies `VerifiedPaymentFailure` | Records reference and releases pending reservation; if already expired, records evidence without a second release. |
| Checkout success | No trusted payment verifier exists | The current checkout operation returns HTTP 409; it cannot complete the order. |

The `VerifiedPaymentFailure` dataclass is only an internal naming/type boundary. Any Python caller can construct it, so it is not cryptographic or provider evidence. Phase 3 must not accept it, a caller-provided status, or a webhook body as proof of provider success. Provider verification and persisted evidence must guard transitions.

## Payment lifecycle is not yet modeled

There is no payment attempt record, provider account/mode, provider transaction reference, webhook event log or refund state. `payment_reference` is a local order field; it is not currently bound to a provider. A single evidence string cannot express multiple attempts, pending verification, refunds or conflicting outcomes.

See the [payment architecture proposal](payment-architecture.md) and [lifecycle/reconciliation proposal](../payments/lifecycle-and-reconciliation.md). Phase 3 must settle late-payment, multiple-attempt and refund policies before implementing the success path.
