# Domain model

The current SQLAlchemy mapping lives in [`app/models/`](../../app/models/). Nullable fields added for facts absent from the initial schema are intentionally not backfilled with guesses.

| Entity | Current relationships and purpose | Payment-relevant fields/limits |
|---|---|---|
| `User` | One organizer profile; many events and orders. | Role and `is_superuser` are both present; authorization consistency needs review. |
| `OrganizerProfile` | One-to-one with user; organizer business details. | Has legacy Paystack subaccount, bank-code, account-number and percentage-charge columns. No payout/subaccount flow uses these in current application code. Their presence does not establish a financial or merchant-of-record policy. |
| `Event` | Belongs to an organizer; has ticket types. | Publication state can be unknown (`NULL`) for historical rows. |
| `TicketType` | Belongs to event; many tickets and orders. | Holds current displayed `price`, capacity, reserved/sold counters and optional activation. Currency is not stored here. |
| `Order` | Belongs to user; optionally references a ticket type; has tickets, multiple payment attempts and at most one fulfillment claim. | Stores legacy/order snapshots and a single optional `payment_evidence_reference`; historical purchase facts remain nullable. It has no provider state of its own. |
| `Ticket` | Belongs to order and ticket type. | Phase 2 creates reserved tickets; successful payment issuance is not implemented. |
| `PaymentAttempt` | Belongs to one order; has zero or more refunds/reconciliation observations, webhook receipts, and at most one fulfillment claim. | Stores provider/account/environment references, integer minor-unit amount, explicit KES snapshot, idempotency and normalized attempt state. Provider authentication/verification is not implemented. |
| `PaymentFulfillment` | Unique per order and tied by a composite FK to one successful attempt for that order. | A database claim preventing a second attempt from claiming fulfillment; it neither proves authenticated provider evidence nor creates `Ticket` rows. |
| `WebhookEvent` | Optionally associates to an attempt only when provider/account/environment match. | Stores event identifiers, digest, receipt/authentication/processing state and bounded failure details; no raw payload or credentials. Receipt/authentication evidence columns are protected against mutation; rejected events cannot become authenticated. |
| `Refund` | Belongs to one payment attempt; can have reconciliation observations. | Supports multiple partial/full refund records with independent idempotency/reference/state. No aggregate refund cap is encoded; orchestration must enforce approved provider and business limits. |
| `ReconciliationRecord` | Belongs to a payment attempt and optionally references a refund. | Stores immutable internal/provider observations, mismatch classification, evidence digest and mutable resolution status. |

Cardinality summary:

```text
User 1 ── 0..1 OrganizerProfile
User 1 ── * Event ── * TicketType ── * Ticket
User 1 ── * Order ── 0..1 TicketType
Order 1 ── * Ticket
Order 1 ── * PaymentAttempt ── 0..* Refund
Order 1 ── 0..1 PaymentFulfillment ── PaymentAttempt
PaymentAttempt 1 ── 0..* WebhookEvent
PaymentAttempt 1 ── 0..* ReconciliationRecord ── 0..1 Refund
```

An order's amount currently uses `Numeric(10, 2)` and Python `Decimal`; currency is nullable. Ticket-type price is also `Numeric(10, 2)` without currency. Reservation code snapshots unit price and total, but intentionally sets currency to `None` because the project has not selected an authoritative currency. This must be resolved before payment initialization.

The `OrderStatus` enum combines order lifecycle and legacy payment-shaped values (`SUCCESSFUL`, `FAILED`, `PAYMENT_FAILED`) with reservation states (`PENDING`, `CANCELLED`, `EXPIRED`, `COMPLETED`). Phase 3 should distinguish the payment attempt state from order fulfillment state; it must not reinterpret historical enum values without evidence.

The preserved initial migration and Phase 1/2 revisions are unchanged. Package 2 adds forward revision `c7e2a4b19d60` for payment persistence, enums, constraints, indexes and audit triggers. The complete chain, metadata parity and safe empty downgrade/re-upgrade were verified on a fresh disposable PostgreSQL 18.6 cluster. Compatibility with any existing database remains unverified and requires a separately authorized rehearsal.
