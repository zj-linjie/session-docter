# SD002 — Heavy issue/PR discovery queries

## What it detects

List commands that pull full payloads for every item, in shell code blocks or
prose rules, for example (split here so this doc is not itself a sample):

```text
gh issue list \
  --json number,title,body,labels,comments
```

Equivalent variants: the same shape for pull requests, changed-file or review
payloads in list calls, full CI log fetches by default, paginated API walks
over comment collections, full PR diffs inside loops, and natural-language
rules like "fetch every comment before triage" (English and Chinese).

## Why it costs context

Discovery becomes a context dump: the transcript replays every body and
comment thread of the whole tracker, while the task only needs one ticket.
Token cost scales with the tracker, not with the work.

## Recommended change

```bash
gh issue list --state open --json number,title,labels,assignees
gh issue view 56 --json number,title,body,labels   # after picking one
```

Comments are read only when the body is insufficient. The same discipline
applies to PR diffs and CI logs: fetch per item, on demand.

## Fix behavior

High-confidence auto-fix: the `--json` field list is rewritten to drop the
full-payload fields (body/comments/files). Non-Markdown files get a manual
note instead of an edit.

## Positive / negative examples

`fixtures/fixture_a_issue_heavy/docs/agents/workflows.md` (positive);
`fixtures/fixture_c_healthy` (negative).
