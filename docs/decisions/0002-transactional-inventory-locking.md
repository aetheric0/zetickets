# ADR 0002: Transactional Inventory Locking and Expiry

- **Status:** Accepted; disposable PostgreSQL runtime verification passed
- **Date:** 2026-11-18

## Context

Reservation creation, cancellation, trusted payment failure and expiry cleanup must update an order, its tickets and the ticket-type inventory together. The production database is PostgreSQL. A temporary PostgreSQL 18.6 cluster is available for isolated integration verification; no existing application database may be accessed.

## Decision

- Lock a ticket-type row with `SELECT ... FOR UPDATE` before checking/decrementing inventory for reservations.
- Lock the order before ticket-type inventory for cancellation and cleanup paths. Expiry workers claim bounded batches with `FOR UPDATE SKIP LOCKED`.
- Commit each complete service operation once; roll back on every exception.
- Keep expiry cleanup callable as a bounded service operation. Do not add a scheduler or route in this phase.
- Treat inventory counters that are NULL or inconsistent as requiring reconciliation; never clamp or infer their values.

## Alternatives considered

- Conditional inventory updates without row locks. This could be viable but requires PostgreSQL-specific predicate/update tests and was not selected for the smallest correction to the existing locking design.
- Expiry background infrastructure. Deferred because the phase does not authorize a scheduler or deployment work.

## Consequences and evidence

The service operations are transaction-scoped and use explicit locks. PostgreSQL 18.6 integration tests verified reservations, rollback, cancellation, expiry, capacity contention, order row locking and `SKIP LOCKED`. These results apply to a fresh disposable schema only, not an existing database or production environment.

## Open questions

- Select and document how/when the expiry service is invoked in the deployed application.
- Rehearse future upgrades against a backup or production-like copy before applying them to an existing application database.
