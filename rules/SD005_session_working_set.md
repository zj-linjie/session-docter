# SD005 — Session lifecycle / working set

## What it detects

Missing session boundaries in a project that runs multi-task flows:

- no "one coherent working set per session" rule;
- no stop-after-task rule (sessions picking up the next ticket automatically);
- dispatch-style coordination without small worker receipts;
- an explicit never-restart policy for the main session — raises severity.

If none of the multi-task signals are present, the rule stays silent (small
single-task repos are not nagged). If boundaries exist and no persistent
session is mandated, the rule stays silent too.

## Why it costs context

Without a stop rule, one session accumulates unrelated tickets; worker outputs
and transcripts replay in the coordinator context. The working set grows with
project history instead of with the current task.

## Recommended change

- One session = one coherent working set; stop when the current task is done.
- Independent tasks go to new sessions.
- Coordinators collect only small receipts:

```yaml
issue: 56
status: done
pr: 60
tests: pass
blockers: []
```

No full transcripts, diffs, or logs in the parent context.

## Fix behavior

High-confidence auto-fix: appends a short "Session boundaries" block to
AGENTS.md when absent (diff shown first).

## Positive / negative examples

`fixtures/fixture_a_issue_heavy/AGENTS.md` (positive);
`fixtures/fixture_c_healthy/AGENTS.md` (negative).
