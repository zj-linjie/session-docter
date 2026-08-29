# AGENTS.md

quiet-inbox — a small CLI for triaging newsletter mail into a reading queue.

## Stack

- Python 3.12, stdlib + imaplib; packaging via pyproject.toml.

## Map

- `src/quiet_inbox/` — package code.
- `docs/PRD.md` — product requirements. Read the relevant section when a task
  touches product scope.
- `docs/STATUS.md` — current state snapshot. Read for continuation, environment,
  release or blocker questions.

## Verify

- `python3 -m pytest -q`
- `python3 -m quiet_inbox --help` smoke check

## Working rules

- One session handles one coherent working set; when the current task is done, stop.
- Split unrelated tasks into separate sessions; do not pick up the next task automatically.
- Batch builds and reviews once a set of edits stabilizes; on failure read the
  relevant error excerpt first.
- Large files: search and read by heading or line range before reading in full.
