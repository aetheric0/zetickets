# Zetickets Engineering Roadmap

## Purpose

The roadmap establishes the engineering foundations before product expansion. It is both an implementation plan and a structured learning curriculum for professional backend engineering.

## Current repository status (reviewed 2026-11-19)

- **Phase 1 — Complete at repository level.** Model/schema tests pass. The complete migration chain was also exercised on a fresh disposable PostgreSQL 18.6 database during Phase 2 verification; compatibility with any pre-existing application database remains unverified.
- **Phase 2 — Complete at repository/test-environment level.** Transactional reservation behavior and PostgreSQL integration checks passed on the fresh disposable PostgreSQL 18.6 environment. Existing database migration compatibility and production runtime operations are not established.
- **Phase 3 — In progress.** Architecture direction is accepted. Package 1 implements validated, consistent JWT configuration and disables caller-asserted payment failure transitions. Package 2 adds payment persistence and has passed fresh PostgreSQL migration/schema tests. Provider verification, authentication/authorization hardening, webhook handling, payment orchestration and reconciliation behavior remain incomplete. See [Package 1 post-mortem](postmortems/phase-3-package-1-security-foundation.md), [Package 2 post-mortem](postmortems/phase-3-package-2-payment-data-model.md), and the [implementation plan](phase-3-implementation-plan.md).
- **Phases 4 and 5 — Not started.**

For Phase 3 architecture, provider evidence and approval gates, see the [payment architecture](architecture/payment-architecture.md), [provider comparison](payments/provider-comparison.md), [threat model](security/threat-model.md), and [accepted ADRs](decisions/README.md).

## Phase 1 — Canonical data model and schemas

**Scope**
- Normalize ORM entities, relationships, foreign keys and cardinality.
- Align SQLAlchemy models and Pydantic request/response schemas.
- Establish consistent enums, roles and state representations.
- Model users, profiles, events, ticket types, orders, tickets and reservations coherently.
- Add constraints and indexes that express domain invariants.
- Evolve the schema through controlled Alembic migrations while preserving historical uncertainty.

**Study**
Relational modelling, normalization, SQLAlchemy 2.x, Pydantic, referential integrity, constraints, enum persistence and schema evolution.

**Exit criteria**
- Model relationships and foreign keys are internally consistent.
- Schemas accurately represent supported model fields and API contracts.
- Enum storage and migration definitions are reconciled.
- Historical unknowns are not fabricated.
- Database-independent compatibility tests pass.
- Migration review is documented; live application is separately verified only in an authorized test database.
- Post-mortem and Git checkpoint exist.

## Phase 2 — Transactional business logic

**Scope**
- Define order and reservation state machines.
- Reserve inventory atomically and prevent overselling.
- Persist and enforce reservation expiry.
- Release inventory safely on expiry, cancellation and failed checkout.
- Make order operations transactional and retry-safe.
- Handle concurrent requests and duplicate operations.
- Establish a trusted boundary between order state and payment evidence.

**Study**
ACID properties, transaction isolation, row-level locking, race conditions, optimistic versus pessimistic concurrency, state machines, idempotency, rollback and consistency invariants.

**Exit criteria**
- Reservation and order transitions are explicit and validated.
- Inventory cannot be oversold under supported concurrency.
- Expiry and release behaviour is deterministic and safe to retry.
- Duplicate requests do not double-reserve, double-release or duplicate transitions.
- Cancellation and failure paths preserve inventory invariants.
- Automated tests cover normal, boundary, failure and concurrency cases to the extent supported by the test environment.
- PostgreSQL-specific behaviour is verified on PostgreSQL or explicitly marked blocked.
- Payment completion cannot be asserted without trusted payment evidence.
- Post-mortem and Git checkpoint exist.

## Phase 3 — Security and payments

**Architecture direction (2026-11-19):** ADRs 0005–0011 accept Paystack first, KES only initially with future currency extensibility, platform collection with separate organizer settlement, and refund of verified late success when reservation/inventory is invalid. Packages 1 and 2 are implemented; Package 2's new revision and tests have been exercised on fresh disposable PostgreSQL 18.6. Provider integration, payment orchestration, full authorization, webhook handling and reconciliation behavior remain unimplemented. Account-specific Paystack readiness and commercial terms remain unverified/undefined. See the [Phase 3 implementation plan](phase-3-implementation-plan.md).

**Scope**
- Authentication and authorization.
- Password hashing and token lifecycle.
- Ownership checks and role-based access control.
- Payment-provider integration and server-side verification.
- Webhook signature validation, replay protection and idempotent processing.
- Payment/order reconciliation and refund boundaries.

**Study**
JWT and OAuth concepts, RBAC/ABAC, OWASP risks, secrets management, webhook security, payment state machines and reconciliation.

**Exit criteria**
- Protected operations enforce authentication, authorization and ownership.
- Payment status is based on trusted server-side evidence.
- Webhooks are authenticated, replay-safe and idempotent.
- Sensitive configuration is externalized.
- Security tests cover relevant negative paths.
- Provider-specific behaviour is tested in an appropriate sandbox.

## Phase 4 — API integration and automated testing

**Scope**
- Router registration and dependency injection.
- Stable endpoint contracts and response semantics.
- Unit, service, integration and API tests.
- PostgreSQL-compatible test setup and isolation.
- CI checks for tests, formatting, linting and migrations.

**Study**
REST design, dependency injection, test pyramids, fixtures, contract testing, test doubles, CI pipelines and test isolation.

**Exit criteria**
- Intended endpoints are registered and documented.
- API contracts match service and schema behaviour.
- Automated test suite is reproducible.
- CI runs the agreed checks.
- PostgreSQL-specific tests run against PostgreSQL.

## Phase 5 — Deployment and portfolio readiness

**Scope**
- Reproducible dependency installation and lockfiles.
- Docker and deployment configuration.
- Safe migration execution.
- Environment configuration and secret handling.
- Logging, health checks, monitoring and operational documentation.
- Backup/recovery strategy and portfolio presentation.

**Study**
Containers, 12-factor application principles, CI/CD, observability, deployment strategies, backup/recovery and technical communication.

**Exit criteria**
- A fresh clone can be configured using documented steps.
- Build and deployment processes are reproducible.
- Migrations have a documented, controlled release process.
- Secrets are not committed.
- Health checks and useful operational logs exist.
- README and architecture documentation accurately describe the system.
- Portfolio evidence is verifiable and does not overstate production readiness.

## Standard phase execution cycle

1. Targeted inspection.
2. Define sub-phase acceptance criteria.
3. Implement.
4. Verify with appropriate tests.
5. Review defects and regressions.
6. Correct.
7. Document decisions and post-mortem.
8. Create a Git checkpoint.
9. Report phase status and residual risks.

## Required post-mortem structure

For each material defect or phase:
- Defect / observed behaviour.
- Root cause.
- Impact and affected invariants.
- Correction and rationale.
- Files affected.
- Verification commands and actual results.
- Migration and historical-data implications.
- Residual risks and follow-up work.

## Product expansion — after engineering foundations

Potential later capabilities include organizer profiles, follows and audience relationships, event discovery, personalized updates, email/in-app notifications, optional paid SMS, ticket tiers, early-bird pricing, promo codes, region-targeted promotion and organizer analytics.

These are product opportunities, not permission to bypass the engineering phases or introduce unapproved paid services.
