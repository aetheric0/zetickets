# Phase 1 Post-mortem: Canonical Models and Schemas

**Status:** Closed at repository level; PostgreSQL migration verification remains unverified.
**Checkpoint:** `452ccc6 feat: establish canonical domain models and schemas`

## Defects and root causes

- ORM relationships and foreign keys were incomplete or inconsistent. Orders lacked a ticket-type foreign key and the ticket/order relationship used mismatched `back_populates` names. `OrganizerProfile` imported the user type from the schema package for type checking.
- Orders had no persisted quantity, expiry or purchase unit-price/currency snapshot. The checkout handler derived quantity from the monetary total and recomputed expiry from order creation time.
- Ticket-type ORM columns and request schemas diverged: description, inventory counters and activation state were missing from the initial migration; capacity aliases included a misspelling; event writers passed `capacity` where the ORM field is `quantity_available`.
- PostgreSQL enum labels drifted from Python enums. The initial order enum had `PENDING`, `SUCCESSFUL`, `FAILED`; current code used different lifecycle labels. User enum values were stored uppercase by SQLAlchemy while Python role values and authorization checks used lowercase.
- `Event.end_time` was annotated as `str` despite being a timezone-aware database timestamp and a Pydantic `datetime`. Publication state existed in the ORM but not in the initial migration.
- User schema fields and ORM fields differed for `full_name`, `role` and `is_superuser`.

## Impact

The mismatches could prevent mapper configuration, cause invalid constructor arguments or response validation, make enum values unreadable, misstate order quantities/expiry, and make inventory unsafe. Legacy rows did not contain enough evidence to derive the missing purchase facts or inventory counters.

## Corrections and decisions

- Added the missing order link, quantity, expiry and snapshot fields. Historical order values and newly added inventory/publication/activation state remain nullable when unavailable.
- Preserved legacy order enum labels and added current labels without translating ambiguous history. Updated user-role enum labels in a forward revision to lowercase values matching Python.
- Aligned response aliases with ORM attributes while retaining `capacity` as the public response key. Event creation/update paths now write the canonical ORM field.
- Changed `end_time`'s Python annotation to `datetime`; database type and Pydantic request/response contract were already datetime-based.
- Reservation/checkout now use stored order quantity and expiry. Paths that cannot safely use legacy inventory/order state return explicit conflicts/errors rather than inventing values.
- Added database-independent mapper/schema compatibility coverage.

## Files changed

- `alembic/versions/8f3c1a2d9b40_phase1_canonical_model.py`
- `app/api/v1/endpoints/events.py`
- `app/api/v1/endpoints/orders.py`
- `app/models/enums.py`, `event.py`, `order.py`, `profile.py`, `ticket.py`, `user.py`
- `app/schemas/event.py`, `order.py`, `ticket.py`, `user.py`
- `app/test_model_schema_compatibility.py`

## Verification evidence

- `UV_CACHE_DIR=/tmp/zetickets-uv-cache uv run --no-sync python -m pytest -q app/test_model_schema_compatibility.py` — 6 passed.
- `UV_CACHE_DIR=/tmp/zetickets-uv-cache uv run --no-sync python -m compileall -q app/models app/schemas app/api/v1/endpoints/events.py app/api/v1/endpoints/orders.py app/test_model_schema_compatibility.py alembic/versions/8f3c1a2d9b40_phase1_canonical_model.py` — passed.
- `git diff --check` — passed.
- No database was connected and no migration was applied.

## Migration and historical-data implications

The initial migration is preserved. The new revision is forward-only, adds columns/FKs and enum labels, and leaves uncertain historical facts null. User role enum labels are renamed in place. Code inspection establishes intended alignment only; migration compatibility has not been verified against PostgreSQL.

## Residual risks

- Existing pending orders and ticket types may have unknown quantity, expiry or inventory counters and are deliberately not eligible for unsafe reservation/checkout transitions until reconciled.
- Currency has no configured source. The order snapshot field exists, but selecting or populating currency requires a business decision.
- The enum revision assumes the deployed types and labels match the preserved initial migration. Verify against an authorized disposable PostgreSQL environment before deployment.
- Ruff was unavailable due to an executable permission error during the closure pass; compilation and tests passed.
