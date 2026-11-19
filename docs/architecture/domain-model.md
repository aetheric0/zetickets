# Domain model

The current SQLAlchemy mapping lives in [`app/models/`](../../app/models/). Nullable fields added for facts absent from the initial schema are intentionally not backfilled with guesses.

| Entity | Current relationships and purpose | Payment-relevant fields/limits |
|---|---|---|
| `User` | One organizer profile; many events and orders. | Role and `is_superuser` are both present; authorization consistency needs review. |
| `OrganizerProfile` | One-to-one with user; organizer business details. | Has legacy Paystack subaccount, bank-code, account-number and percentage-charge columns. No payout/subaccount flow uses these in current application code. Their presence does not establish a financial or merchant-of-record policy. |
| `Event` | Belongs to an organizer; has ticket types. | Publication state can be unknown (`NULL`) for historical rows. |
| `TicketType` | Belongs to event; many tickets and orders. | Holds current displayed `price`, capacity, reserved/sold counters and optional activation. Currency is not stored here. |
| `Order` | Belongs to user; optionally references a ticket type; has ticket rows. | Stores `quantity`, `unit_price`, `currency`, `expires_at`, `total_amount`, `payment_reference`, and a single optional `payment_evidence_reference`. Historical purchase facts remain nullable. There is no provider field and no payment-attempt relation. |
| `Ticket` | Belongs to order and ticket type. | Phase 2 creates reserved tickets; successful payment issuance is not implemented. |

Cardinality summary:

```text
User 1 ── 0..1 OrganizerProfile
User 1 ── * Event ── * TicketType ── * Ticket
User 1 ── * Order ── 0..1 TicketType
Order 1 ── * Ticket
```

An order's amount currently uses `Numeric(10, 2)` and Python `Decimal`; currency is nullable. Ticket-type price is also `Numeric(10, 2)` without currency. Reservation code snapshots unit price and total, but intentionally sets currency to `None` because the project has not selected an authoritative currency. This must be resolved before payment initialization.

The `OrderStatus` enum combines order lifecycle and legacy payment-shaped values (`SUCCESSFUL`, `FAILED`, `PAYMENT_FAILED`) with reservation states (`PENDING`, `CANCELLED`, `EXPIRED`, `COMPLETED`). Phase 3 should distinguish the payment attempt state from order fulfillment state; it must not reinterpret historical enum values without evidence.

The Phase 1 and Phase 2 migration chain is forward-only. Fresh-schema PostgreSQL 18.6 verification passed, but an existing database's revision/schema/data state must be inspected and rehearsed separately before any rollout.
