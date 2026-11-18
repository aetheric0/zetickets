# Agent Execution Policy

## Operating model

Use milestone-level delegation. The user should not need to relay every routine implementation response between agents. When a phase is authorized, execute its safe sub-phases as one coherent workstream and return one consolidated report.

The agent may make reversible, conventional engineering decisions within the approved scope. Record material decisions in `docs/decisions/`.

## Autonomy boundaries

**Proceed autonomously**
- Targeted code inspection.
- Break authorized phases into sub-phases with acceptance criteria.
- Implementation within the approved phase.
- Routine refactoring required for correctness.
- Unit and integration test creation.
- Running tests and diagnosing failures.
- Formatting, lint and type corrections.
- Updating documentation and post-mortems.
- Maintaining a decision log for material design choices.
- Reviewing diffs and preparing verified commits.
- Producing one consolidated milestone report and creating verified checkpoints.

Do not interrupt the user for ordinary implementation choices, predictable refactoring, formatting/lint corrections, routine test failures that can be diagnosed safely, or non-destructive changes inside the authorized scope. Finish all safe independent work when one item is blocked.

**Pause for user approval**
- Destructive or irreversible data operations.
- Migrations against an existing or unknown persistent database.
- Business decisions affecting currency, price, fees, refunds or payment-provider selection.
- New paid services or material infrastructure costs.
- Security weakening.
- Deleting or overwriting user work.
- Materially changing public contracts where the intended behaviour is unclear.

Do not use a pause as a reason to abandon safe independent work. Isolate the blocked item and continue other authorized work where possible.

## Verification discipline

For each sub-phase, define what success means before implementation. Execute the relevant checks and record their exact outcomes.

Never convert an unavailable check into an implied pass. Label unexecuted checks as blocked or not run and explain why. Explicitly distinguish mocked, database-independent, SQLite and PostgreSQL verification.

## Git checkpoint discipline

A checkpoint is permitted only after:
- Relevant tests have passed.
- The full diff has been reviewed.
- Secrets and unrelated files have been excluded.
- Documentation is updated.
- Remaining limitations are recorded.

Stage specific files, not the entire working tree by default. Never rewrite existing history or push without authorization.

## Decision records

Create a short Markdown record in `docs/decisions/` for decisions that materially affect data models, state transitions, transaction strategy, API contracts, security boundaries or operational architecture. Include context, decision, alternatives considered, consequences and unresolved questions.

## Post-mortems

Create one post-mortem per completed phase under `docs/postmortems/`. Include defects, root causes, impact, correction, files, verification evidence, migration implications and residual risks.

## Milestone report format

Return one consolidated report containing:
1. Executive summary.
2. Sub-phase status.
3. Key design decisions.
4. Defects corrected.
5. Files changed.
6. Tests and exact results.
7. Blocked/not-run checks.
8. Data and migration risks.
9. Residual defects.
10. Documentation created.
11. Git commit hash and working-tree state.
12. Explicit completion status and next authorized step.
