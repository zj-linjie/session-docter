# ADR-0001: Postgres partitioning for the events table

Status: accepted (2026-03-05)

## Context

The raw events table grew past 2B rows; queries without a tenant filter timed out.

## Decision

Range-partition by month, sub-partition by tenant hash. All queries must include
the partition key.

## Consequences

Backfills need the chunked worker; see the backfill tooling notes.
