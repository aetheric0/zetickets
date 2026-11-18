# ADR 0001: Preserve Unknown Historical Values

- **Status:** Accepted
- **Date:** 2026-11-18

## Context

The initial schema did not record order quantity, ticket-type linkage, purchase unit price/currency, reservation expiry, inventory counters, ticket activation or event publication state. Guessing values during schema evolution could create incorrect financial records or permit overselling.

## Decision

New schema fields remain nullable where legacy values cannot be recovered from authoritative evidence. Application paths must reject unsafe operations when required values are unknown. New records receive explicit values through application logic where the values are known. Do not infer currency or translate ambiguous legacy order statuses.

## Alternatives considered

- Backfill constants such as quantity one, zero inventory, a default currency or an expiry based on creation time.
- Infer quantities or sales from related ticket rows.
- Translate `SUCCESSFUL`/`FAILED` into newer order statuses.

These alternatives were rejected because they could fabricate purchase history or change business meaning.

## Consequences and evidence

Responses must tolerate null historical fields. Reservation/checkout paths need explicit guards. Database-independent tests cover nullable legacy response values. The migration remains unverified against PostgreSQL.

## Open questions

- Which currency is authoritative for a ticket type/order?
- What do legacy `SUCCESSFUL` and `FAILED` represent relative to the new order lifecycle?
- What trusted process will reconcile existing inventory and pending reservations?
