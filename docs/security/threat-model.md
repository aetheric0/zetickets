# Phase 3 payment and security threat model

**Scope:** current source boundary plus proposed payment flow. The controls below are requirements, not claims that they are implemented. Security review date: 2026-11-19. See [verification strategy](controls-and-verification.md).

Current source findings: `app/main.py` only mounts `/health`; the v1 router is not mounted. [`app/core/security.py`](../../app/core/security.py) signs JWTs with `JWT_SECRET`, while [`app/core/deps.py`](../../app/core/deps.py) validates them using `SECRET_KEY`; both default to empty strings in [`app/core/config.py`](../../app/core/config.py). [`app/services/orders.py`](../../app/services/orders.py) exposes an internal `VerifiedPaymentFailure` dataclass that is constructible by any Python caller and is not cryptographic proof. Payment-success/webhook code does not exist. These findings are documented for Phase 3/4; this review does not change application code.

## Threat register

### T1 — Weak, mismatched or missing authentication configuration

- **Asset:** user accounts, orders, payment operations, signing keys.
- **Attack vector:** blank/default secrets, signer/verifier key mismatch, weak algorithm configuration, leaked or stale tokens.
- **Impact:** login tokens fail validation or can be forged if deployment uses weak/misconfigured values; unauthorized actions may follow.
- **Prevention:** fail startup if required secrets are absent/weak; use one explicit validated JWT signing/verification configuration, algorithm allowlist, short-lived tokens and documented rotation. Never include secret values in logs.
- **Detection/recovery:** alert on auth failures/anomalous token use; rotate compromised keys and invalidate affected sessions.
- **Tests:** missing/weak config fails closed; tokens signed by the configured key verify; wrong key/algorithm, expired token and malformed claims are rejected.

### T2 — Insecure direct object reference / order ownership bypass

- **Asset:** customer orders, tickets, contact data and payment evidence.
- **Attack vector:** user guesses or reuses another order/user UUID against a checkout, cancellation, read or refund operation.
- **Impact:** unauthorized order access, cancellation, ticket issuance or refund.
- **Prevention:** scope every order lookup and state transition by authenticated principal/authorized role in the service query; use least-privilege role checks; do not rely on unpredictable IDs.
- **Detection/recovery:** audit denied and privileged accesses; investigate repeated cross-owner probes and revoke sessions if compromised.
- **Tests:** user A cannot view/cancel/checkout/refund user B's order; admin-only actions reject non-admin users.

### T3 — Role confusion and privilege escalation

- **Asset:** user roles, event/ticket administration, payment/refund controls.
- **Attack vector:** inconsistent `role` and `is_superuser` semantics, user-controlled role fields, unprotected admin endpoints.
- **Impact:** attacker gains administrative or financial authority.
- **Prevention:** define one authoritative authorization policy; deny by default; only authorized administration may alter roles; forbid self-escalation and record role changes.
- **Detection/recovery:** immutable audit trail for role changes and refunds; suspend/revoke accounts and review affected actions.
- **Tests:** role matrix, role-field tampering, inactive admins, owner/non-owner matrix, self-escalation attempts.

### T4 — Payment amount or currency tampering

- **Asset:** customer funds and order/ticket value.
- **Attack vector:** client or webhook changes amount/currency, or mutable ticket price changes after checkout initialization.
- **Impact:** underpayment accepted, overcharge, accounting mismatch or financial loss.
- **Prevention:** immutable persisted attempt snapshot; server calculates from order snapshot; compare independently verified provider amount and currency exactly before fulfillment; use decimal/integer minor units, never floats; reject null/unsupported currency.
- **Detection/recovery:** flag all mismatches for review and reconcile provider statements; never fulfill mismatched attempts automatically.
- **Tests:** wrong amount/currency, fractional rounding, changed ticket price after attempt, unsupported currency, null snapshot all fail closed.

### T5 — Forged or modified Paystack webhook

- **Asset:** payment state, inventory and ticket issuance.
- **Attack vector:** public webhook receives forged JSON or altered request; attacker exploits signature parsing/key rotation mistakes.
- **Impact:** false paid order, free ticket issuance or inventory corruption.
- **Prevention:** verify provider's current signature scheme over the original raw bytes, constant-time compare, timestamp bounds/key rotation, HTTPS; use the webhook as a signal and independently verify transaction/reference/amount/currency/account with Paystack before fulfillment.
- **Detection/recovery:** record signature and verification outcomes without logging secrets; quarantine failures and requery provider; rotate compromised webhook/API keys.
- **Tests:** valid/invalid signatures, modified bytes, whitespace mutation, stale/future timestamp, multiple rotation signatures and amount/reference mismatch.

### T6 — Forged or unauthenticated Daraja callback

- **Asset:** payment confirmation and M-PESA-related order fulfillment.
- **Attack vector:** attacker posts callback-shaped data to a public URL or exploits absent/weak callback authenticity controls.
- **Impact:** false payment success or denial of service against callback processing.
- **Prevention:** confirm Safaricom's current callback-authentication guarantees for the exact Daraja product/account; never treat callback JSON alone as proof; use authenticated Daraja transaction-status/STK query where available and match shortcode, receipt/conversation ID, amount and local attempt. Protect endpoint availability and rate-limit safely.
- **Detection/recovery:** reconcile callbacks with status queries and account statements; quarantine unmatched/conflicting callbacks.
- **Tests:** spoofed callback, wrong shortcode/reference/amount, query unavailable and conflicting callback/query outcomes.

### T7 — Webhook replay, duplicate delivery or event reordering

- **Asset:** idempotent order/payment transitions and financial ledger.
- **Attack vector:** provider retries or operator resends an event; attacker replays a previously valid delivery; stale event arrives after terminal state.
- **Impact:** duplicate ticket issue, repeated inventory release, duplicate refund or state regression.
- **Prevention:** durable inbox and deduplication keyed by provider account/environment plus stable event/transaction identity; timestamp/replay checks where supported; lock attempt/order; enforce unique transition/effect constraints; handle terminal conflicts by reconciliation.
- **Detection/recovery:** track duplicate counts and event age; compare event inbox to payment ledger/provider reports; reprocess only idempotently.
- **Tests:** same event multiple times, resend under new signature timestamp, event reordering, duplicate processing under concurrency.

### T8 — Incorrect provider transaction-to-order association

- **Asset:** payment records, customer data, inventory.
- **Attack vector:** client supplies another provider reference/order ID; reference collision across accounts or test/live mode; weak metadata matching.
- **Impact:** payment credited to wrong order/customer or provider payment falsely fulfills an unrelated order.
- **Prevention:** generate local attempt references server-side; persist order/attempt association before provider call; scope unique references by provider account and environment; verify customer/merchant identity and exact expected snapshot.
- **Detection/recovery:** unmatched payments enter a reconciliation queue; retain audit trail and resolve manually under dual control for high-risk actions.
- **Tests:** cross-order reference, cross-account/environment reference, duplicate reference, altered metadata and unknown provider reference.

### T9 — Concurrent payment attempts for one order

- **Asset:** customer funds, single-order fulfillment and inventory.
- **Attack vector:** repeated checkout clicks, browser retries, concurrent clients or timeout recovery start multiple charges.
- **Impact:** multiple successful charges, double refunds or duplicate ticket issuance.
- **Prevention:** persist idempotent payment attempts; serialize attempt creation per order; require definitive failure/expiry or verified reconciliation before another unresolved attempt unless owner policy says otherwise; enforce one fulfillment transaction.
- **Detection/recovery:** alert on more than one success per order; quarantine extra success and apply approved refund workflow.
- **Tests:** concurrent initialize requests, API retry, timeout-after-provider-acceptance, two successful attempts racing fulfillment.

### T10 — Late payment after reservation expiry

- **Asset:** scarce inventory, payment funds and customer entitlement.
- **Attack vector:** customer completes a delayed M-PESA/card flow after the Phase 2 ten-minute reservation expires and inventory is released.
- **Impact:** overselling if order is reactivated; customer loss if money is retained without ticket/refund.
- **Prevention:** retain payment success as a distinct financial fact; do not silently reopen reservation or issue ticket; lock/revalidate inventory only under an owner-approved policy; otherwise enter explicit review/refund state.
- **Detection/recovery:** alert and reconcile late-success queue; support/refund workflow with status tracking.
- **Tests:** payment success after expiry, concurrent expiry and webhook, inventory already re-sold, late event repeated.

### T11 — Success after cancellation

- **Asset:** customer funds, cancelled order and inventory allocation.
- **Attack vector:** cancellation races with provider authorization/callback, or provider settles after cancellation has released inventory.
- **Impact:** customer is charged without entitlement, or reactivation causes oversell.
- **Prevention:** serialize state changes; distinguish order cancellation from payment finality; check verified attempt and order state atomically; never issue automatically after cancellation.
- **Detection/recovery:** alert on successful payment for cancelled order; reconcile and use explicit support/refund policy.
- **Tests:** cancellation-versus-success race, repeated cancellation, success arriving after cancellation commit.

### T12 — Duplicate payment and refund errors

- **Asset:** customer funds and financial records.
- **Attack vector:** retry after ambiguous charge/refund API timeout, repeated operator action or duplicate provider event.
- **Impact:** multiple charges/refunds, accounting loss or customer under/over-refund.
- **Prevention:** stable idempotency references per attempt/refund; query before resubmitting ambiguous operations; append-only payment/refund records; authorization and amount bounds; separate refund lifecycle from payment state.
- **Detection/recovery:** daily provider-to-ledger reconciliation, duplicate reference alerts, auditable refund approval and manual exception resolution.
- **Tests:** duplicate refund submit, timeout then retry, partial-refund sum cap, duplicate payment, refund status webhook repeats.

### T13 — Provider timeout or ambiguous outcome

- **Asset:** payment correctness and customer experience.
- **Attack vector:** network timeout after provider accepts request, API outage, delayed callback or status query outage.
- **Impact:** duplicate charge on naive retry, false failure, held inventory or lost payment.
- **Prevention:** distinguish definite rejection from unknown outcome; persist attempt before call; use provider reference/idempotency where available; reconcile by reference; do not mark failed solely because local request timed out.
- **Detection/recovery:** age-based alerts and retryable reconciliation queue; operator can compare provider portal/statement; preserve original request/response metadata with secrets redacted.
- **Tests:** connect timeout, read timeout after provider accepts, provider 5xx, delayed callback, verification endpoint unavailable, repeated recovery run.

### T14 — Credential leakage or environment crossover

- **Asset:** provider funds, user accounts, merchant configuration.
- **Attack vector:** secrets committed/logged, copied into client code, sandbox/live keys mixed, credentials left in CI or logs.
- **Impact:** unauthorized transactions, refunds, data exposure or production outage.
- **Prevention:** external secret manager/environment injection; distinct test/live credentials and provider-account identity; least-scoped keys; rotation; startup validation; redact headers and payloads; never return keys to clients.
- **Detection/recovery:** secret scanning, provider alerts, access-log review; immediately revoke/rotate exposed credentials and reconcile affected transactions.
- **Tests:** no secret in repository/artifacts/logs; environment separation; invalid mode/account key rejected; rotation overlap behavior.

### T15 — Sensitive customer/payment data exposure

- **Asset:** customer names/emails/phone numbers, bank details, provider payloads and payment evidence.
- **Attack vector:** excessive webhook logging, broad admin access, over-retention, accidental response serialization or database dumps.
- **Impact:** privacy breach, fraud and regulatory/contract consequences.
- **Prevention:** data minimization, access controls, encrypted transport/storage/backups, field-level protections where needed, defined retention/deletion policy, never store PAN/CVV, redact logs and response schemas.
- **Detection/recovery:** access audit, log scanning and incident response; rotate exposed credentials and follow applicable notice/retention process.
- **Tests:** response/schema redaction, log redaction, retention enforcement and role-based access to evidence.

### T16 — Administrative refund/reconciliation abuse

- **Asset:** customer funds, platform/organizer balances and audit integrity.
- **Attack vector:** compromised admin, insufficient separation of duties, IDOR or unaudited manual payment override.
- **Impact:** unauthorized refund, false fulfillment, concealed accounting discrepancy.
- **Prevention:** least privilege, explicit permissions for refund/reconcile actions, dual approval above a threshold, immutable audit actor/reason/reference, no “mark paid” override without provider evidence.
- **Detection/recovery:** monitor administrative actions and unusual amounts; suspend operator credentials; independently reconcile and reverse only via provider-supported process.
- **Tests:** non-admin denied, actor/reason audit required, dual approval gate, no manual paid-state bypass.

## Assumptions and boundaries

- Provider-side technical documentation is not a merchant contract or confirmation of account eligibility.
- The reported Paystack account status was not independently inspected.
- Exact Daraja callback authenticity and retry characteristics must be confirmed with current account-specific documentation.
- Threat controls are not implemented or verified by this documentation milestone. Security tests belong to Phase 3/4.
