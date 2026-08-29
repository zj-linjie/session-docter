# SD006 — Tool loop amplification

## What it detects

Verification rules that fire per micro change:

- per-micro-change rebuild/full-suite mandates;
- per-step capture/review mandates (a capture-and-review round per small change);
- full build/CI log reads on any failure;
- redundant independent reviewers re-modeling the same context;
- (or, inversely) a visual project with no batching boundary at all.

Two or more dense mandates rate high; one rates medium; a visual project with
capture signals but no batching boundary rates medium.

## Why it costs context

Each verification round replays the working set again. Dense loops multiply an
already large context, and full-log reads on failure replace a 20-line error
excerpt with thousands of lines.

## Recommended change

- Run builds/tests once a set of edits is stable, not per micro edit.
- On failure, read the relevant error excerpt first; pull full logs only when
  the excerpt is insufficient.
- Do visual checks when the interface reaches a stable state; iterate only on
  concrete visual issues.
- Never drop the final verification — this rule is about loop density, not
  about skipping verification.

## Fix behavior

High-confidence auto-fix: appends a short "Verification discipline" block to
AGENTS.md when absent (diff shown first).

## Positive / negative examples

`fixtures/fixture_b_visual/AGENTS.md` (visual, no batching boundary);
`fixtures/fixture_c_healthy/AGENTS.md` (negative — batched verification).
