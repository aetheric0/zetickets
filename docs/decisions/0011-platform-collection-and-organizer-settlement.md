# ADR 0011: Platform collection and separate organizer settlement

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

The owner has approved platform-controlled collection and reconciliation of customer payments, with organizers paid separately. Existing `OrganizerProfile` contains legacy Paystack subaccount/bank fields, but no implemented provider transaction ledger, organizer balance ledger or payout workflow. Those fields do not establish a settlement policy.

## Decision

Zetickets collects customer payments into its platform merchant account and is responsible for reconciling provider transactions and settlements. Customer payment and organizer payout are distinct financial events. Maintain auditable organizer liabilities in internal accounting records, separate from provider transaction records and provider-specific metadata.

Create payout records with organizer, currency, amount, idempotency/reference, destination reference protected as sensitive data, status, timestamps, audit actor and provider reference. Model states such as prepared, submitted/pending, confirmed paid, failed and reconciliation-required. An initiated payout is not paid: only independently confirmed/reconciled payout evidence may reduce organizer payable. Keep payout provider operations behind an extensible adapter boundary. Do not imply an organizer balance is cleared or payable before underlying funds and policy adjustments are evidenced.

## Alternatives considered

- Pay organizers through direct provider subaccounts/splits: rejected as initial accounting direction because it conflicts with the approved platform collection/independent payout model and obscures internal liabilities.
- Store organizer balance as a mutable scalar: weak auditability and difficult reconciliation.
- Treat customer payment as organizer payout: conflates different counterparties and settlement events.

## Consequences

The system needs a traceable per-currency journal/ledger, settlement evidence, payout lifecycle and reconciliation. Payment processor capture, processor settlement to the platform and platform payout to an organizer remain separate facts. Future payout providers/arrangements can be added without changing the customer payment model.

## Security and operations

Restrict payout creation/approval, use least privilege and auditable actor/reason/reference; consider separation of duties for execution. Protect payout destinations, use idempotency and unique provider references, reconcile duplicate/failed/ambiguous transfers, and never provide a manual “paid” override without evidence.

## Evidence and references

Owner instruction in the Phase 3 architecture mandate. Current source review: [`OrganizerProfile`](../../app/models/profile.py) contains unused legacy Paystack-related fields; no payout ledger/service exists. Paystack [Kenya pricing](https://paystack.com/ke/pricing) documents transfer options, but does not establish Zetickets’ merchant eligibility or terms.

## Open commercial decisions

Commission/rates, provider fee allocation, tax treatment, reserves, payout schedule, minimums, payout destinations, organizer contracts, dispute/chargeback recovery and whether/when liabilities become payable require commercial/legal definition. No values are assumed by this ADR.
