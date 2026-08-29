# ADR-0001: Immutable postings

Status: accepted (2026-02-10)

## Context

Auditors require a tamper-evident money trail.

## Decision

Postings are immutable; corrections are new reversing postings.

## Consequences

No UPDATE path on the postings table; corrections create linked reversals.
