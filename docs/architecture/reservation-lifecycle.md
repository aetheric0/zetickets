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
| Payment failure recording | No trusted provider verifier is configured | Fails closed with `PaymentVerificationUnavailable`; no database read/write or inventory change. |
| Checkout success | No trusted payment verifier exists | The current checkout operation returns HTTP 409; it cannot complete the order. |

The former `VerifiedPaymentFailure` dataclass and the service operation that accepted it were removed in Phase 3 Package 1. A Python object or caller-provided status is not provider evidence. There is no current payment-success or payment-failure state transition. Checkout remains HTTP 409, and failure recording is disabled until an application-owned provider verification flow is implemented. Reservation expiry and user cancellation continue to release inventory transactionally.

## Payment lifecycle is not yet modeled

The Phase 3 Package 2 schema now defines payment attempts, provider/account/environment references, webhook receipt/authentication/processing records, refunds, reconciliation observations and a unique fulfillment claim. These are persistence structures only: `payment_reference` is still not bound to a provider by runtime code, and there is no payment service, verification path, webhook route or refund execution. No successful-payment transition is currently available.

See the [payment architecture](payment-architecture.md), [lifecycle/reconciliation requirements](../payments/lifecycle-and-reconciliation.md) and [Phase 3 execution plan](../phase-3-implementation-plan.md). Provider adapter, verified payment transitions, webhook processing, refund execution and reconciliation behavior remain deferred.
