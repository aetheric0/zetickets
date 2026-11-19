# Engineering documentation

This index links to the canonical engineering documents. The roadmap controls phase ordering; decision records capture decisions and proposals; architecture and security documents explain the current source and proposed Phase 3 design.

## Architecture

- [System overview](architecture/system-overview.md) — runtime composition and current route registration.
- [Domain model](architecture/domain-model.md) — ORM entities, relationships and recorded uncertainty.
- [Reservation lifecycle](architecture/reservation-lifecycle.md) — current Phase 2 transaction behavior.
- [Payment architecture](architecture/payment-architecture.md) — accepted provider-neutral design; implementation not started.

## Security

- [Threat model](security/threat-model.md) — assets, threats, controls, detection/recovery and tests.
- [Controls and verification strategy](security/controls-and-verification.md) — proposed release gates and test evidence.

## Payments

- [Provider comparison](payments/provider-comparison.md) — Paystack and Daraja comparison based on official documentation.
- [Payment lifecycle and reconciliation](payments/lifecycle-and-reconciliation.md) — accepted states, trust, refund and accounting requirements.
- [Phase 3 implementation plan](phase-3-implementation-plan.md) — bounded work packages, dependencies, tests and rollback.

## Decisions

See the [ADR index](decisions/README.md). ADRs 0005–0011 capture accepted provider, currency, lifecycle, late-refund and platform-settlement direction; account-specific and commercial details remain open.

## Delivery records

- [Engineering roadmap](engineering-roadmap.md)
- [Agent execution policy](agent-execution-policy.md)
- [Phase 1 post-mortem](postmortems/phase-1-canonical-models.md)
- [Phase 2 post-mortem](postmortems/phase-2-transactional-business-logic.md)
- [Phase 2 execution log](phase-2-execution-log.md)
- [Post-mortem index](postmortems/README.md)

Official Paystack sources were reviewed on 2026-11-19 and linked from the provider comparison. Provider features, prices, account settings and terms can change.
