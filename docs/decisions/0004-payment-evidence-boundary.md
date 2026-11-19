# ADR 0004: Payment Evidence Boundary

- **Status:** Accepted; amended by Phase 3 Package 1
- **Date:** 2026-11-18

## Context

The existing checkout operation marked an order complete based only on an authenticated client request. No trusted payment verifier or currency source exists.

## Decision

- Client checkout requests cannot complete an order; the existing operation returns a conflict until trusted payment evidence is available.
- The former `VerifiedPaymentFailure` object and service path were removed in Phase 3 Package 1 because ordinary callers could construct the object and trigger an inventory release. Payment failure recording now fails closed without accepting an outcome/evidence argument or touching database state. A future application-owned verification orchestration must verify provider status before introducing a transactional payment transition.
- Preserve legacy `FAILED` without assigning it new meaning. Use explicit `PAYMENT_FAILED` for the new trusted-failure path.
- Do not implement successful payment completion until the provider adapter/orchestration package exists. Accepted Phase 3 policy now sets KES-only initial transactions; historical currency remains nullable and is never guessed.

## Alternatives considered

- Continue client-triggered completion. Rejected because it lets a client assert payment success.
- Add payment-provider or currency configuration now. Deferred to Phase 3 and requires a business/provider decision.

## Consequences and evidence

Checkout rejection and the fail-closed payment failure operation are covered by database-independent tests. The former failure transition was covered in Phase 2, but is intentionally disabled after inspection showed that its constructible object did not authenticate provider evidence. No provider integration or new route exists. Successful payment verification and provider-specific security remain unimplemented.

## Open questions

- The owner-approved direction is Paystack first, KES-only initially, and refund of a verified late success when inventory/reservation is invalid; see ADRs 0006, 0009 and 0010. Merchant-specific eligibility and commercial terms remain open.
