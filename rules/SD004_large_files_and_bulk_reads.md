# SD004 — Large files and bulk reads

## What it detects

Two distinct risks that must not be conflated:

1. **Bulk-read rules** — commands or prose that read whole directories at once
   (cat with a glob, find -exec pipelines, whole-directory read phrasing, and
   their Chinese equivalents). Severity is higher when they live in the
   instruction file or a mandatory-chain doc.
2. **Large files on disk** — big Markdown/HTML/JSON/log-like files. The report
   distinguishes:
   - *on the default reading path* (referenced by startup rules or the
     mandatory chain) → medium;
   - *present but not auto-read* → low, informational only.

A large file merely existing is not a startup cost. The verdict depends on
whether rules or habits route it into sessions wholesale.

## Why it costs context

Bulk reads pull payloads proportional to a whole directory, then replay them
on every retry/review round. Large files on the default path tax every session
even when a heading would have answered the task.

## Recommended change

- List files, search by keyword or heading, then read only the relevant file
  or line range.
- Keep large assets out of mandatory startup chains.
- Never wire whole-directory reads into rules.

## Fix behavior

High-confidence auto-fix in Markdown: a bulk cat-with-glob line becomes an
`ls` of the same glob plus a targeted-reading comment. Everything else is
advice.

## Positive / negative examples

`fixtures/fixture_a_issue_heavy/docs/agents/workflows.md` (bulk positive; the
same fixture's large map file shows the referenced-large-file case),
`fixtures/fixture_b_visual/content/presentations/` (large, not auto-read).
