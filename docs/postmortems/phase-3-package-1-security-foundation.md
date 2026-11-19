# Phase 3 Package 1 Post-mortem: Security Foundation

**Status:** Implementation checkpoint; provider integration remains deferred.

## Defects and root causes

- JWT creation used `JWT_SECRET`, while request validation used `SECRET_KEY`. Both were empty-string defaults, so deployments could start with inconsistent or unusable authentication keys. Configuration accepted short and empty values.
- Applying a standard Pydantic minimum-length constraint to a secret field included the raw invalid input in the validation error context.
- `VerifiedPaymentFailure` was a caller-constructible dataclass. `record_verified_payment_failure` trusted its reference, wrote a payment-failure state, and released inventory; the object did not authenticate a provider result.
- JWT validation logged exception details, which was unnecessary for a credential-validation failure and risked exposing token-related details.

## Impact

Tokens created by the application could fail verification when the two configuration values differed. Missing/weak configuration was not rejected early. Any in-process caller could fabricate a payment-failure object and release reserved inventory without provider verification. No payment-provider integration existed.

## Corrections and design decisions

- `JWT_SECRET` is the canonical environment setting and is represented by Pydantic `SecretStr`. Settings construction rejects secrets shorter than 32 non-whitespace characters and rejects an empty `ALGORITHM`; neither has an empty default. Signing and verification now call shared configured values. Missing required configuration fails settings creation; invalid-length errors use a generic message without echoing the value.
- Secret length validation runs after the value is represented as a secret and raises a fixed message, avoiding Pydantic's raw-input error context. A generated test-only invalid value is asserted absent from the error text.
- The old `SECRET_KEY` setting is removed. Deployments that configured only `SECRET_KEY` must set `JWT_SECRET` explicitly; no automatic copying or key rotation is performed.
- Added `decode_access_token` in the security module and made request authentication use it. JWT rejection logging is generic; PyJWT still verifies signature and expiration, and Pydantic still validates the subject claim.
- Removed `VerifiedPaymentFailure` and its mutating transition. `record_payment_failure` accepts no status/evidence value and raises `PaymentVerificationUnavailable` without querying or mutating the session. Checkout remains closed. Reservation, user cancellation and expiry behavior remain active and transactional.
- No replacement Python evidence type is treated as proof. Future payment orchestration must invoke the configured provider verifier itself and perform any verified transition transactionally. The Paystack adapter and its persistence are deferred.

## Files changed

- `app/core/config.py`
- `app/core/security.py`
- `app/core/deps.py`
- `app/services/orders.py`
- `app/test_security_foundation.py`
- `app/test_order_transactions.py`
- `app/test_orders_postgres.py`
- `README.md`
- `docs/architecture/system-overview.md`
- `docs/architecture/payment-architecture.md`
- `docs/architecture/reservation-lifecycle.md`
- `docs/security/controls-and-verification.md`
- `docs/security/threat-model.md`
- `docs/decisions/0004-payment-evidence-boundary.md`
- `docs/engineering-roadmap.md`
- `docs/phase-3-implementation-plan.md`
- `docs/README.md`
- `docs/postmortems/README.md`
- `docs/postmortems/phase-2-transactional-business-logic.md`
- `docs/postmortems/phase-3-package-1-security-foundation.md`

The pre-existing import consolidation in `app/models/order.py` was not modified, staged or committed.

## Verification evidence

- `UV_CACHE_DIR=/tmp/zetickets-uv-cache JWT_SECRET=<generated test-only value> ALGORITHM=HS256 PYTHONPATH=/home/kali/zetickets uv run --project /home/kali/zetickets --no-sync python -m pytest -q /home/kali/zetickets/app/test_security_foundation.py /home/kali/zetickets/app/test_order_transactions.py /home/kali/zetickets/app/test_model_schema_compatibility.py /home/kali/zetickets/app/test_orders_postgres.py` — **31 passed, 11 skipped**. The PostgreSQL tests skipped because the dedicated disposable test database environment was unavailable. The command ran from `/tmp`, so repository `.env` discovery was avoided. No provider API was called.
- `UV_CACHE_DIR=/tmp/zetickets-uv-cache JWT_SECRET=<generated test-only value> ALGORITHM=HS256 PYTHONPATH=/home/kali/zetickets uv run --project /home/kali/zetickets --no-sync python -m compileall -q /home/kali/zetickets/app/core/config.py /home/kali/zetickets/app/core/security.py /home/kali/zetickets/app/core/deps.py /home/kali/zetickets/app/services/orders.py /home/kali/zetickets/app/test_security_foundation.py /home/kali/zetickets/app/test_order_transactions.py /home/kali/zetickets/app/test_orders_postgres.py` — passed.
- `git diff --check` — passed.
- Ruff — not run; no `ruff` executable is available. Dependencies were not installed.

## Database and migration implications

No ORM model or migration changed. The database-independent suite verifies that the disabled payment-failure operation performs no session I/O and leaves reservation/ticket/inventory state unchanged. PostgreSQL transaction behavior for the unchanged cancellation/expiry code is covered by the existing isolated Phase 2 suite only if its dedicated test cluster is explicitly available; no existing application database is used.

## Residual risks and deferred work

- An initial failing test exposed an ephemeral generated test-only invalid secret in pytest's assertion traceback because Pydantic included the raw field input. No project/provider credential was used or persisted. Validation was changed to raise a fixed message, and the passing regression test verifies that generated invalid values are not included in configuration errors.
- Existing deployments that set only `SECRET_KEY`, or omit `ALGORITHM`, will fail configuration validation until their environment is updated. Existing JWT sessions signed under a different key will not validate; rotation/session invalidation policy remains to be designed.
- The current JWT algorithm remains environment-configured; this package requires it to be non-empty but does not introduce a broader algorithm allowlist.
- Authentication/authorization ownership gaps, router registration, provider verification, successful payment, webhook authentication, payment persistence, refunds and reconciliation remain incomplete.
- `record_payment_failure` intentionally cannot release inventory. Until trusted verification and orchestration are implemented, verified provider failures cannot transition an order; reservation expiry and user cancellation remain available.
