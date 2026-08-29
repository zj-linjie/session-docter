# SD003 — Instruction file fixed tax / mutable state

## What it detects

Instruction files (AGENTS.md, CLAUDE.md, copilot-instructions, cursor rules…)
that mix in volatile content: status sections, machine/device details,
milestones, dated checklists, changelogs, history entries. The finding reports
bytes, lines, a clearly-labeled token estimate, the mutable-line ratio, and
sample evidence lines.

Size alone is never a verdict: a large-but-clean map stays "low", while a
small file stuffed with dated status lines rates "medium/high".

## Why it costs context

The instruction file is loaded by every task. Volatile sections are paid by
all of them, churn provider-side prompt caches, and grow without bound as the
project progresses — the definition of a fixed input tax.

## Recommended change

Split by volatility:

- instruction file keeps: project map, core invariants, verify commands,
  on-demand routing;
- STATUS.md receives: environment, current phase, blockers — updated by
  replacing entries, never by appending history.

## Fix behavior

Proposal only (never auto-applied): the fix output includes a manual split
proposal. The bootstrap templates show the target shape
(`docs/STATUS.md` is replace-in-place by design).

## Positive / negative examples

`fixtures/fixture_a_issue_heavy/AGENTS.md` (positive);
`fixtures/fixture_c_healthy/AGENTS.md` (negative).
