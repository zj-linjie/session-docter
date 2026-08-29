# Domain rules

This file is the entrypoint for all domain rules.

All schema work must read docs/adr/* first, then update the glossary in CONTEXT.md
before proposing any migration.

Event naming follows `<domain>.<entity>.<verb>`; billing events live under `billing.*`.
Tenant isolation is enforced at the repository layer, never in controllers.
