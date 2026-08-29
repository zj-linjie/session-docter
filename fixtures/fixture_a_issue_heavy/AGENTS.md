# AGENTS.md

Orion Platform — multi-tenant analytics backend.

## Startup

Before any task, read docs/agents/domain.md, then follow it to CONTEXT.md and docs/adr/*.
Start every session by reading PROJECT_MAP.md in full.

## Workflows

See docs/agents/workflows.md for the issue workflow and triage loop.

## Domain rules

docs/agents/domain.md is the entrypoint for all domain rules and glossary lookups.

## Session policy

The dispatcher session stays alive across tickets and collects each worker's full transcript in context.
Do not restart the main session between tickets; keep everything in one place for continuity.

## Environment

- Machine: orion-dev-04 (Mac Studio, 64 GB)
- Device: paired iPad for on-call paging
- Last updated: 2026-08-11
- Python 3.12.1, Postgres 16.2 (local docker), Redis 7.2
- Deploy target: eu-west-1 staging, credentials in vault entry orion/staging

## Milestones

- [x] 2026-03-02 M1: ingestion pipeline shipped to first customer
- [x] 2026-03-19 M1.1: backfill tooling, 4.2B rows migrated
- [x] 2026-04-18 M2: billing alpha behind flag
- [x] 2026-05-06 M2.1: invoice PDF service
- [x] 2026-06-30 M3: EU region launch
- [x] 2026-07-14 M3.1: data residency controls audit passed
- [x] 2026-08-11 M4: usage-based billing GA
- [x] 2026-03-05 retro: ingestion throughput 3x after partitioning (see ADR-0001)
- [x] 2026-03-22 retro: backfill worker OOM fixed by chunked reads
- [x] 2026-04-21 retro: billing alpha onboarding friction noted, Pricing table v2 drafted
- [x] 2026-05-09 retro: invoice PDF latency p99 8.1s -> 1.9s after cache
- [x] 2026-07-02 retro: EU launch runbook rehearsed, two gaps fixed
- [x] 2026-07-16 retro: residency audit findings closed
- [x] 2026-08-13 retro: GA launch postmortem draft, alert noise 40% down
- [x] 2026-03-11 M1.2: schema registry v1, 42 event types registered
- [x] 2026-04-02 M1.3: dead-letter queue dashboard
- [x] 2026-04-28 M2.2: proration engine spike, chosen approach documented
- [x] 2026-06-11 M2.3: dunning emails v1
- [x] 2026-07-21 M3.2: Frankfurt cluster cutover
- [x] 2026-08-02 M3.3: residency docs published for enterprise buyers
- [x] 2026-08-20 M4.1: overage alerts, budget guardrails
- [x] 2026-03-09 on-call rotation v3 adopted, paging thresholds tuned
- [x] 2026-03-27 vendor eval: ClickHouse vs TimescaleDB, decision recorded in ADR-0002
- [x] 2026-04-15 security review: ingestion endpoints pen-tested, 3 findings closed
- [x] 2026-05-12 pricing committee: usage tiers finalized
- [x] 2026-06-18 SOC2 evidence collection started
- [x] 2026-07-25 SOC2 phase 1 complete
- [x] 2026-08-16 enterprise pilot: 3 logos, feedback in docs/pilots
- [x] 2026-03-15 data model freeze for M1, migration playbook written
- [x] 2026-04-05 ingestion SLA defined: 5 min end-to-end p95
- [x] 2026-04-24 cost review: warehouse spend down 22% after tiering
- [x] 2026-05-20 billing QA pack: 214 cases automated
- [x] 2026-06-25 EU data transfer assessments signed
- [x] 2026-07-28 Frankfurt DR drill passed (RTO 41 min)
- [x] 2026-08-18 GA pricing page live
- [x] 2026-03-29 M1 closeout: 11 follow-up tickets filed to backlog review
- [x] 2026-04-30 M2 closeout: billing alpha NPS +12 in pilot cohort
- [x] 2026-07-01 M3 closeout: EU latency p95 84ms from Frankfurt edge
- [x] 2026-08-21 M4 closeout: GA conversion 3.8%, target 4.5% next quarter
- [x] 2026-03-08 platform hiring: 2 ingestion engineers started
- [x] 2026-04-10 billing engineer offer accepted
- [x] 2026-06-05 EU ops contractor onboarded
- [x] 2026-03-04 incident 2026-03-04 (ingest lag 55 min): RCA published
- [x] 2026-04-07 incident 2026-04-07 (dup charges in sandbox): RCA published
- [x] 2026-06-14 incident 2026-06-14 (EU DNS): RCA published, runbook updated
- [x] 2026-03-18 partner webhook rate limits negotiated
- [x] 2026-04-20 partner sandbox: 14 integrators onboarded
- [x] 2026-06-28 partner GA: webhook retries with idempotency keys
