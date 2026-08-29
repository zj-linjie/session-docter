# Fixtures

Synthetic sample repositories used by the test suite. Each fixture is a
standalone fake repo; none of them is real project knowledge.

- `fixture_a_issue_heavy/` — orchestration repo with a mandatory context chain,
  heavy issue-list payloads, history tax, and a persistent dispatcher session.
  Expected audit result: high risk.
- `fixture_b_visual/` — content/visual project: on-demand design docs, one large
  deck source, no working-set boundary, no batching boundary for visual checks.
  Expected audit result: medium risk (the large file is present but NOT auto-read,
  which must not be reported as a startup cost).
- `fixture_c_healthy/` — small maintenance project with thin AGENTS.md, on-demand
  PRD/STATUS, session boundaries and batched verification.
  Expected audit result: low risk.
- `fixture_d_new_project/` — bare new project (README + package.json) used by
  bootstrap tests.
- `fixture_e_light_docs/` — already has a healthy lightweight doc set; bootstrap
  must keep existing files and propose only what is missing.
- `fixture_f_heavy/` — mature context system (CONTEXT.md + ADRs); bootstrap must
  refuse and suggest running `audit` instead.
