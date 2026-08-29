# Workflows

## Issue triage

gh issue list --state open --json number,title,body,labels,comments
Then read all comments for triage before the standup notes.

For PR hygiene:

gh pr list --state open --json number,title,body

## Status collection

cat docs/status-reports/*.md
Paste the concatenated output into the standup notes.
