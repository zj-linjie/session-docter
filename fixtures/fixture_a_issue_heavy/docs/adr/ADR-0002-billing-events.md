# ADR-0002: Billing event store

Status: accepted (2026-03-27)

## Context

Billing needs an append-only, replayable event stream with strict ordering per account.

## Decision

Use the existing Postgres cluster with logical replication to the warehouse;
do not introduce a second datastore for MVP.

## Consequences

Retention: 400 days hot, then archive to object storage.
