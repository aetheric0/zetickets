# ADR 0003: Reservation Idempotency

- **Status:** Accepted
- **Date:** 2026-11-18

## Context

A retried reservation request can create duplicate orders and increment reserved inventory more than once. A server-generated key cannot identify a client retry.

## Decision

Require an `Idempotency-Key` header (1–128 characters) on the existing reservation operation. Persist it with the user ID and enforce uniqueness at the database. A replay with the same key and same ticket type/quantity returns the existing order; a different payload returns a conflict. A unique-constraint race rolls back inventory changes and reloads the winning order.

## Alternatives considered

- Infer duplicates from user, ticket type and quantity. Rejected because two intentional purchases may be identical.
- Store the key only in memory or use a process-local lock. Rejected because retries and concurrency can cross workers/restarts.

## Consequences and evidence

The reservation API contract requires a client key. Historical rows remain NULL. Database-independent tests cover replay, mismatched reuse and a simulated unique-constraint race. PostgreSQL 18.6 integration tests also verified same-key concurrent requests create one order and one inventory reservation. Existing-database upgrade compatibility remains unverified.

## Open questions

- Set a retention policy only if idempotency records are later separated from orders; current keys remain with orders.
