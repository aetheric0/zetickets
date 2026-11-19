# ADR 0006: Paystack as first provider candidate

- **Status:** Proposed recommendation; project-owner approval required
- **Date:** 2026-11-19

## Context

The owner reports that the project has a verified Paystack account and API access. Paystack's public documentation describes Kenya M-PESA and card support. Daraja provides direct M-PESA integration but not cards. This review did not inspect the Paystack dashboard, credentials, production mode, merchant eligibility, channel activation or settlement setup.

## Decision

Recommend Paystack as the first adapter candidate, conditional on owner approval and dashboard/agreement checks. Keep the application provider-neutral and retain direct Safaricom Daraja as an independent option. This ADR does not authorize implementation or finalize provider choice.

## Alternatives considered

- Daraja first: appropriate if direct M-PESA control, account ownership or economics take priority; does not cover cards and adds direct onboarding/reconciliation work.
- Both simultaneously: broad coverage but doubles provider-specific test, support, callback and accounting burden before one flow is stable.
- Defer all providers: avoids financial assumptions but blocks the payment milestone.

## Consequences

Paystack could cover Kenyan M-PESA and cards through one integration, subject to live account enablement and merchant terms. It creates vendor fees, settlement and refund dependencies. Daraja remains possible but adds a separate direct integration.

## Security and operations

Use server-side initialization/verification and authenticated webhooks; keep test/live keys separate. Confirm supported event signatures, account activation, callback configuration, fees, settlement destinations, refunds and dispute operations before production use.

## Evidence and references

- [Paystack Kenya payment channels](https://paystack.com/docs/payments/payment-channels/) and [Kenya pricing](https://paystack.com/ke/pricing).
- [Daraja Developer Portal](https://developer.safaricom.co.ke/) and [Transaction Status API](https://developer.safaricom.co.ke/apis/TransactionStatus).
- Project owner account status is reported, not independently verified. Sources reviewed 2026-11-18.

## Owner approval questions

1. Is Paystack approved as Phase 3's first provider?
2. Does the account have live Kenyan M-PESA, local/international card channels and the intended settlement currencies enabled?
3. Do signed merchant terms and payout/refund operations meet the product's requirements?
