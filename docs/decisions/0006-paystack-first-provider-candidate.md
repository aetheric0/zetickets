# ADR 0006: Paystack as the initial payment provider

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

The owner reports a verified Paystack account and API access from an earlier project. That does not establish Zetickets merchant eligibility, live status, enabled payment channels, settlement configuration or applicable commercial terms. Paystack official docs describe card channels across markets and Kenya M-PESA support; account and dashboard settings still govern actual availability.

## Decision

Paystack is the first provider implementation target, subject to account-specific readiness checks before production. Initial scope is KES transactions only. Build a provider-neutral internal boundary. Daraja remains a future independent provider option, not part of the initial implementation.

## Alternatives considered

- Daraja first: direct M-PESA path but does not supply the planned card channels.
- Both providers simultaneously: expands testing and operational burden before one flow is stable.
- No provider: conflicts with the owner-approved Phase 3 direction.

## Consequences

One adapter may cover Kenya M-PESA and supported card channels, but Zetickets depends on Paystack behavior, account settings, fees, verification, refunds and settlement. No public price or settlement statement is a guaranteed account quote.

## Security and operations

Use server-side initialization/verification; authenticate webhooks; reconcile missing/late events; separate test/live keys and accounts. Before launch verify in Paystack dashboard/agreement: Kenyan M-PESA/card enablement, live eligibility, merchant entity, webhook signing setup, settlement destination/currency, fees, refund eligibility/status behavior, disputes and limits. Never inspect or expose keys in documentation.

## Evidence and references

Owner account status is reported, not independently inspected. Official [Payment Channels](https://paystack.com/docs/payments/payment-channels/), [Verify Payments](https://paystack.com/docs/payments/verify-payments/), [Webhooks](https://paystack.com/docs/payments/webhooks/), [Kenya pricing](https://paystack.com/ke/pricing) and [Kenya terms](https://paystack.com/ke/terms) reviewed 2026-11-19. Public prices and general terms do not establish this merchant's contractual charges or eligibility.

## Open account/commercial checks

Confirm eligible channels, live onboarding, account and settlement currency/destination, fees and taxes, refund and chargeback terms, transfer capabilities and merchant agreement. These checks gate launch, not the accepted Paystack-first direction.
