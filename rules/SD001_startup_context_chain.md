# SD001 — Startup context chain

## What it detects

A mandatory reading chain that pulls context-heavy docs into every session:
instruction file → intermediate rule docs → CONTEXT / ADR / PRD / ROADMAP /
STATUS / history / map docs. The report shows the full chain, not just "the
instruction file is big", including each target's size and line count.

Triggers include imperative startup phrasing ("before any task…", "start every
session by reading…", and Chinese must-read phrasing) combined with references
to docs that resolve inside the repo (backticks, Markdown links, bare paths,
globs).

## Why it costs context

Every session pays the chain's full size before doing any real work, whatever
the task is. Multi-level hops make it worse: the tax hides behind intermediate
rule docs and grows as docs accumulate.

## Recommended change

- Convert the chain into task-conditional routing: ordinary tasks start from
  the current issue/requirement plus relevant code.
- Read CONTEXT/ADR/PRD/ROADMAP/STATUS sections only when the task touches them.
- Keep the instruction file as a routing map, not as a mandatory reading list.

## Fix behavior

High-confidence: mandatory-read lines are rewritten into task-conditional
routing lines (diff shown in dry-run). Heavy docs referenced on-demand are only
flagged as low-severity potential risk.

## Positive / negative examples

See `fixtures/fixture_a_issue_heavy` (positive) and
`fixtures/fixture_c_healthy` (negative).
