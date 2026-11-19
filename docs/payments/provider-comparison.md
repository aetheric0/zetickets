# Payment provider comparison: Paystack and Safaricom Daraja

**Reviewed against official public documentation:** 2026-11-19. The owner has selected Paystack as the initial integration target and KES as the initial currency. Daraja is a future option only. Public documentation does not prove Zetickets account activation, eligibility, merchant-specific terms or production readiness.

## Evidence categories

- **Documented:** stated in official public documentation accessed on the date above.
- **Account-dependent:** eligibility, KYB, merchant agreement, dashboard activation or shortcode configuration must be checked for Zetickets.
- **Owner-reported:** project owner reports a verified Paystack account and API access from an earlier project; credentials/dashboard were not inspected.
- **Unresolved:** requires account-specific or commercial confirmation.

## Decision matrix

| Dimension | Paystack (initial target) | Safaricom Daraja (future option) |
|---|---|---|
| Kenyan customer experience | Official channels docs list M-PESA and cards for Kenya; M-PESA includes customer phone authorization. Hosted checkout/redirect selection depends on enabled dashboard methods. Actual Zetickets enablement is account-dependent. | Direct M-PESA STK Push asks the customer to authorize on their phone; Daraja merchant integration and shortcode are required. |
| International customers | Visa/Mastercard listed across Paystack markets; Amex availability includes Kenya. Acceptance, issuer/risk rules, merchant eligibility and available currencies need account confirmation. | Daraja APIs reviewed are M-PESA business APIs; no card checkout. Cross-border applicability is not assumed. |
| M-PESA support | Kenya payment channel documented. Initial use is subject to merchant channel activation and account checks. | Direct Safaricom M-PESA API option including STK Push and status/reversal APIs. |
| Card support | Visa/Mastercard documented; Amex includes Kenya. Prefer provider-hosted checkout so Zetickets avoids raw PAN/CVV. Custom card API requires PCI compliance. | Not available from the Daraja M-PESA APIs reviewed; separate provider required. |
| Integration complexity | One provider boundary can cover planned M-PESA/card methods; still requires merchant setup, server initialization/verification, callback authentication, refunds, disputes, reconciliation and secret rotation. | OAuth credentials, shortcode/passkey, callbacks, status/reversal workflows, production onboarding and operational reconciliation are Zetickets responsibilities. |
| Verification/webhook security | Server-side transaction verify API exists. Current webhook docs specify raw-body HMAC-SHA512 signature, timestamp/key IDs, freshness checks and retries. Current verify docs say webhook events are currently sent for successful transactions, so polling/reconciliation resolves other and missing outcomes. | Asynchronous callbacks and transaction status query are documented. Exact callback authentication and retry guarantees for the chosen product/account require confirmation. |
| Refund and reconciliation | Full/partial refund API and asynchronous notifications/statuses are documented. API capability does not guarantee every channel/account can refund or establish charges/time. | Reversal and status-query APIs exist in official developer references. Eligibility, roles, timing and costs require Safaricom merchant confirmation. |
| Settlement/currency | Zetickets transaction currency is KES initially. Provider settlement currency/destination, clearing evidence and eligibility must be confirmed in dashboard/agreement; do not infer from public marketing. | Expected Kenya flow is KES merchant M-PESA, but settlement route/timing and fees depend on shortcode/account agreement. |
| Fees and operating cost | Public pricing is mutable and not a Zetickets quote. Confirm applicable processing, transfer, refund, dispute, tax and volume terms in merchant agreement/dashboard. No fee values or settlement-time assumptions are adopted here. | Current merchant-specific tariffs, reversal and settlement costs are unresolved; obtain written provider terms. |
| Onboarding/readiness | Owner reports an existing verified account/API access. This review did not inspect it or confirm Zetickets entity, live eligibility, channel settings, settlement or keys. Test/live setup must be separate. | Production onboarding and live shortcode/admin access remain unverified for Zetickets. |
| Vendor dependence/flexibility | Adapter boundary and internal ledger reduce domain coupling but do not erase provider migration costs. | Future adapter enables direct M-PESA option but adds separate support, security and reconciliation burden. |

## Paystack implementation requirements

- Initialize transactions server-side from immutable order/payment amount snapshot and explicit KES currency; use application-generated unique reference.
- Verify transaction server-side. Require terminal success and exact account/environment/reference/amount/currency match before persisting success.
- Verify webhook signature on original raw bytes using current official format, timestamp freshness and active signing-key rotation rules; constant-time comparison. A signature authenticates origin/integrity, not order or amount correctness.
- Persist and deduplicate events. A webhook triggers verification; never fulfill directly from payload or client redirect.
- Make refund requests use stable local idempotency/reference; query ambiguous timeout outcomes before retry; reconcile until provider confirms completion.
- Reconcile missing callbacks and pending/failure states; current Paystack Verify docs say webhook events currently cover successful transactions.
- Keep test/live credentials and merchant identities separate; store secrets externally, restrict access, rotate and redact. Never inspect `.env` during this review.
- Check account dashboard/agreement before release: M-PESA and card channels, live eligibility, settlement configuration, fees/taxes, payout options, refund channel capabilities, transaction limits, disputes and webhook signing configuration.

## Owner-approved direction and open questions

The owner-approved direction is Paystack first, KES only initially, provider-independent internal architecture, platform collection/reconciliation, separate organizer payout, and refund for verified late success without inventory. Account-specific channel availability, live readiness, merchant terms, settlement clearing evidence, refund capabilities and fees remain unverified. Commercial policies for commissions, tax, reserves, payout schedules, fee allocation and dispute recovery remain undefined.

## Official references (accessed 2026-11-19)

- Paystack [Payment Channels](https://paystack.com/docs/payments/payment-channels/)
- Paystack [Accept Payments](https://paystack.com/docs/payments/accept-payments/) and [Transaction API](https://paystack.com/docs/api/transaction/)
- Paystack [Verify Payments](https://paystack.com/docs/payments/verify-payments/)
- Paystack [Webhooks](https://paystack.com/docs/payments/webhooks/)
- Paystack [Refunds](https://paystack.com/docs/payments/refunds/) and [Refund API](https://paystack.com/docs/api/refund/)
- Paystack [Kenya pricing](https://paystack.com/ke/pricing) and [Kenya terms](https://paystack.com/ke/terms)
- Safaricom [Daraja Developer Portal](https://developer.safaricom.co.ke/) and [Transaction Status API](https://developer.safaricom.co.ke/apis/TransactionStatus)
