# Zetickets — Repository Engineering Instructions

## Mission

Build Zetickets as a reliable, secure, maintainable ticketing platform and a credible professional software-engineering portfolio. Prefer correctness, explicit business rules, data integrity and reproducibility over rapid feature expansion.

## Source of truth

- This file defines repository-wide agent operating rules.
- `docs/engineering-roadmap.md` defines the five-phase engineering sequence and exit criteria.
- `docs/agent-execution-policy.md` defines autonomy, escalation and reporting expectations.
- Record material architectural choices in `docs/decisions/`.
- Record completed phase reviews in `docs/postmortems/`.

Read the relevant instructions and inspect the current repository state before making changes. Do not assume that prior reports describe the current checkout.

## Architecture and conventions

- Preserve the existing FastAPI API, asynchronous SQLAlchemy 2.x ORM, PostgreSQL, Pydantic and Alembic architecture.
- Keep request handling at the API boundary and put reusable business transitions in services. Database writes that update an order and inventory must share one transaction.
- Treat PostgreSQL as the production transaction and migration target. SQLite or mocks can support unit tests but do not establish PostgreSQL locking or enum compatibility.
- Keep persisted unknown historical facts nullable until reconciled from authoritative evidence. Never infer purchase quantity, price, currency or expiry.
- Do not add routes, providers, schedulers or infrastructure unless the active phase explicitly requires them.

## Engineering roadmap

Execute these phases in order:

1. **Canonical data model and schemas** — ORM relationships, foreign keys, Pydantic contracts, enums, constraints and controlled schema evolution. Exit only when models/schemas agree, enum/migration definitions are reconciled, historical unknowns remain unknown, compatibility tests pass, and the post-mortem/checkpoint exist. Report PostgreSQL migration compatibility separately from code inspection.
2. **Transactional business logic** — reservation lifecycle, inventory, expiry, order state transitions, concurrency, cancellation and idempotency. Exit only when transitions are explicit, inventory cannot oversell under supported concurrency, expiry/release are deterministic and retry-safe, duplicates cannot double-apply, completion requires trusted payment evidence, tests pass, PostgreSQL-specific checks pass or are explicitly blocked, and the post-mortem/checkpoint exist.
3. **Security and payments** — authentication, authorization, payment verification, webhook authenticity, replay protection and reconciliation. Exit only when protected operations enforce ownership and authorization, payments use trusted verification, webhooks are authenticated and replay-safe, secrets stay external, and security/provider tests pass in an appropriate sandbox.
4. **API integration and automated testing** — router wiring, dependency injection, endpoint contracts, integration tests, PostgreSQL compatibility and CI. Exit only when intended routes are registered/documented, contracts match services, tests are reproducible, CI runs agreed checks and PostgreSQL-specific tests run against PostgreSQL.
5. **Deployment and portfolio readiness** — reproducible dependencies, containers, controlled migrations, configuration/secrets, observability, documentation and deployment. Exit only when fresh-clone setup and deployment are reproducible, migration release is controlled, secrets are excluded, operational/recovery guidance exists and portfolio claims are evidenced.

Do not skip phases or begin Phase 3 until Phase 2 has passed its exit review. Do not mark a phase complete while mandatory criteria remain unmet.

## Autonomous execution

Within an explicitly authorized phase, the agent is expected to:
1. Inspect the relevant implementation and current Git state.
2. Break the phase into bounded sub-phases and acceptance criteria.
3. Implement coherent changes.
4. Run relevant tests and static checks.
5. Diagnose and correct routine failures without repeatedly asking the user.
6. Review the complete diff for correctness, scope and regressions.
7. Update documentation and decision records.
8. Write a post-mortem.
9. Create a Git checkpoint only after verification.
10. Produce one consolidated milestone report.

Do not stop for ordinary implementation choices, predictable refactoring, formatting, lint corrections or test failures that can safely be diagnosed and fixed within scope.

Do not claim work is running, complete, tested or committed unless the relevant action and result are evidenced in the current session.

## Mandatory approval gates

Stop before:
- Destructive database operations or data deletion.
- Applying migrations to an existing or potentially persistent database.
- Irreversible data transformations or backfills.
- Changing payment-provider, currency, pricing, refund or other financial assumptions.
- Introducing significant paid services or infrastructure.
- Weakening authentication, authorization, validation or other security controls.
- Discarding user work, resetting the repository, or rewriting Git history.

When blocked, preserve the work already completed, finish other safe tasks where possible, and report the exact decision or resource needed.

## Data and environment safety

- Treat `.env`, credentials, tokens, private keys and personal data as confidential.
- Never print secrets or commit secret-bearing files.
- Never assume a database is disposable.
- Never run migrations against an unknown database.
- Never reset, drop, truncate or overwrite database objects without explicit authorization and a verified recovery plan.
- Do not infer missing historical values. Preserve unknown values as unknown.
- Do not treat SQLite results as proof of PostgreSQL-specific behaviour.
- Do not start containers, alter volumes or install system services unless authorized.

## Technical standards

- Preserve existing public API contracts unless a deliberate, documented change is approved.
- Keep business rules in appropriate service/domain layers rather than duplicating them across routes.
- Use explicit state transitions and enforce invariants at transaction boundaries.
- Design writes to be atomic and safe under retries and concurrent requests.
- Validate ownership and authorization on every relevant operation.
- Prefer targeted changes over broad, unrelated refactors.
- Keep dependency declarations and lockfiles consistent when dependencies change.
- Add regression tests for corrected defects.
- Keep tests deterministic and isolated from real user data.

## Testing and evidence

Run the narrowest relevant tests during development, then the full applicable suite at the milestone boundary. Report exact commands and actual outcomes.

Distinguish:
- **Passed**: executed and passed.
- **Failed**: executed and failed.
- **Blocked**: could not be executed, with reason.
- **Not run**: not attempted.

A static inspection is not a runtime test. A mocked test is not a live provider test. A SQLite test is not PostgreSQL verification. A migration that has only been inspected has not been applied or verified against a database.

Never claim migration, concurrency, payment or deployment verification without executing the corresponding test in an appropriate environment.

## Git discipline

- Inspect `git status` before and after work.
- Preserve all pre-existing user changes.
- Do not use `reset --hard`, destructive checkout/clean commands, amend, rebase or force-push unless explicitly authorized.
- Do not commit `.env`, credentials, runtime artifacts, generated logs or unrelated changes.
- Stage only files belonging to the authorized task.
- Create a checkpoint only after tests, diff review and documentation are complete.
- Do not push unless explicitly requested.
- Report the checkpoint commit hash and final working-tree state.

## Completion report

For every phase, report:
- Scope and sub-phases completed.
- Material design decisions and rationale.
- Files changed.
- Defects found, root causes and corrections.
- Tests run, commands and actual results.
- Blocked or unverified checks.
- Migration/database implications.
- Residual risks and outstanding defects.
- Post-mortem location.
- Git checkpoint hash, if created.
- Explicit phase status: complete, provisional, blocked or incomplete.

Do not begin the next phase automatically unless the user has authorized it in the current execution mandate.
