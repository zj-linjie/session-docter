# AGENTS.md — session-docter

Static context-cost doctor for coding-agent repos: `audit` (read-only),
`fix` (dry-run/apply), `bootstrap` (new projects). Python 3.8+ stdlib only,
zero third-party dependencies.

## Map

- `scripts/session_docter.py` — single-file CLI; the source of truth for all
  detection patterns.
- `rules/SD00*.md` — per-rule docs (intent, evidence, recommended change).
- `fixtures/` — synthetic sample repos (A–F) used by tests; excluded from
  audit scans by default.
- `tests/` — stdlib unittest suite; also excluded from audit scans by default.
- `SKILL.md` — agent operating procedure; keep it thin.

## Verify

- `python3 -m unittest discover -s tests -v`
- `python3 scripts/session_docter.py audit fixtures/fixture_a_issue_heavy` (high expected)
- `python3 scripts/session_docter.py audit .` (dogfood: must stay low risk)

## Invariants

- `audit` is strictly read-only; it never creates or modifies files.
- `fix --apply` only touches agent-facing Markdown (.md/.markdown/.mdx/.mdc);
  never business code; never deletes knowledge.
- `bootstrap` never overwrites existing docs and refuses mature context systems.
- No third-party dependencies; single-file script.
- Keep SKILL.md and this file thin; do not copy rule docs into them.
