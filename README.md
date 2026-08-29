# Session Docter

A context-cost doctor for coding-agent repositories.

Multi-step agent work on real projects often gets slow and expensive not
because the business code is complex, but because of **context
amplification**: project rule files that force-read half the docs folder,
issue queries that pull every body and comment, instruction files that
accumulate milestones and machine state, multi-ticket sessions that never
reset, and verification loops that replay the whole working set after every
micro edit.

Session Docter audits a repo (read-only), explains where the fixed context
cost comes from, proposes thin fixes, and — for new projects — bootstraps a
lightweight doc skeleton so the problem never starts.

```text
repo
  ↓ audit (read-only)
risk score + evidence + root causes
  ↓ fix --dry-run
patch plan (unified diffs)
  ↓ fix --apply   (only agent-facing Markdown, only after approval)
  ↓ re-audit
verify the delta
```

## Why "high cache hit" is not "low cost"

Prompt caches make repeated prefixes cheap per token, but the prefix still
has to be **processed and attended to** by the model on every turn:

- the fixed startup tax is paid on every session, every retry, every subagent;
- cached context still ages out, and every edit invalidates the tail of the
  cache anyway — long mutable prefixes get re-billed constantly;
- attention quality degrades as irrelevant material accumulates: more
  context means more chances to miss the one relevant line;
- mutable content (status, milestones, machine details) churns the prefix,
  so the "cache-friendly" ordering never actually sticks.

The cheapest context is the one you never load. Caching reduces the price of
waste; Session Docter reduces the waste.

## Principle: the skill can be heavy, the context must stay thin

Knowledge belongs in the repo, in files that are **routed to on demand**.
Only the current task's inputs belong in the session. Session Docter's own
SKILL.md is deliberately thin: the detailed rules live in `rules/*.md` and in
the script, which are read only when needed.

## Requirements

- Python 3.8+ (standard library only, zero third-party dependencies).
- The target repo can be anything; `audit` never writes to it.

## Usage

### 1. Audit (read-only)

```bash
python3 scripts/session_docter.py audit /path/to/repo
python3 scripts/session_docter.py audit /path/to/repo --json   # machine-readable
python3 scripts/session_docter.py audit /path/to/repo --rules SD001,SD002
```

Example report (trimmed):

```text
Session Docter v0.1.0
========================
Repo: ./orion-platform
Scanned: 31 candidate file(s), 2 instruction file(s)
Overall risk: 8.6 / 10  [high]

HIGH   SD001  Mandatory startup context chain
       AGENTS.md:1  AGENTS.md -> docs/agents/domain.md -> CONTEXT.md   [CONTEXT.md (10.4 KB, 91 lines)]
       Why: Instruction files force context/history/decision docs ...
       Fix: Convert the mandatory chain into task-conditional routing ...
       Auto-fixable: yes

HIGH   SD002  Heavy issue/PR discovery queries
       docs/agents/workflows.md:3  list call loads full payloads for every item
       Fix: List metadata only; fetch the selected item's body on demand.
       Auto-fixable: yes

MEDIUM SD003  Instruction file carries mutable state / fixed input tax
       ...
```

Every finding includes: severity, rule id, evidence (file + line + matched
text), why it costs context, the recommended change, and whether it is
auto-fixable. Where static analysis cannot know the truth (e.g. how long a
remote issue actually is), the finding says so instead of inventing a
verdict.

### 2. Fix (dry-run first, apply after review)

```bash
python3 scripts/session_docter.py fix /path/to/repo --dry-run   # default
python3 scripts/session_docter.py fix /path/to/repo --apply
```

- `--dry-run` prints the target files and unified diffs; nothing is written.
- `--apply` writes only after you have seen the plan, and only touches
  agent-facing Markdown (`.md/.markdown/.mdx/.mdc`).
- It will **never** delete CONTEXT/ADR/PRD/ROADMAP files or project history,
  **never** rewrite product semantics, **never** touch business code.
  Findings it cannot fix safely become manual suggestions (e.g. splitting
  mutable status out of AGENTS.md into STATUS.md).
- Re-run `audit` afterwards to verify the delta.

### 3. Bootstrap (new projects only)

```bash
python3 scripts/session_docter.py bootstrap /path/to/new/repo --dry-run
python3 scripts/session_docter.py bootstrap /path/to/new/repo --apply
```

Generates a minimal, healthy skeleton: `AGENTS.md` + `docs/PRD.md` +
`docs/ROADMAP.md` + `docs/STATUS.md`, with thin-context routing rules baked
in (on-demand PRD/ROADMAP/STATUS, one working set per session, batched
verification, targeted reading for large files). Design properties:

- **Intent-gated**: bootstrap is for explicit project-creation moments. It is
  never triggered merely because a repo is empty; `audit` never creates files.
- **Conservative & idempotent**: existing docs are reported as
  `keep`/`conflict` and never overwritten (a merge proposal is printed);
  only missing files are created.
- **Refuses mature repos**: if CONTEXT/ADR systems or a heavy AGENTS.md
  already exist, it prints "no bootstrap needed" and routes you to `audit`.
- **Self-checking**: after `--apply` it re-audits automatically; the
  generated structure must come back low risk.
- Optional docs (ARCHITECTURE, CONTEXT-MAP, ADR, DESIGN) are **not**
  pre-generated — add them when the project actually needs them.

## Risk scoring

Each finding contributes a weight: high 3.5, medium 2.5, low 0.5. The overall
score is the capped sum (0–10):

- **high (≥ 6.5)** — sessions pay a large fixed or repeated cost; fix the P0s
  first (startup chain, heavy issue queries).
- **medium (3.0–6.4)** — meaningful but bounded taxes (missing session
  boundaries, large files on the reading path, loop mandates).
- **low (< 3.0)** — healthy; remaining items are informational.

The score is a conversation starter, not a grade: every point is traceable to
evidence, and the right fix is sometimes "leave it, the cost is worth it".

## Installing as a skill (Codex & friends)

The CLI works standalone — no installation needed beyond cloning:

```bash
git clone https://github.com/zj-linjie/session-docter
python3 session-docter/scripts/session_docter.py audit /path/to/repo
```

To make your coding agent *proactively* use it:

1. Copy (or symlink) this repo into the directory your agent scans for
   skills — for Codex-style runtimes that is typically `~/.codex/skills/`,
   so the agent discovers `SKILL.md` by name.
2. Then just ask: *"audit this repo's context cost"* or *"bootstrap project
   docs for this new repo"* — the skill routes the intent to the right
   subcommand, reviews the report with you, and only applies fixes after
   your approval.
3. After any applied fix, do an A/B check: run one real small task in a
   fresh session and compare the input size and session feel against a task
   from before the change.

## What it will not do

- No bill prediction, no private telemetry imports, no hidden-prompt analysis.
- No deleting project knowledge: PRD/CONTEXT/ADR/ROADMAP/history are facts to
  route, not garbage to clean.
- No business-code changes, ever.
- No one-size-fits-all agent architecture: it diagnoses cost; you keep the
  workflow that suits your project.

## Development

```bash
python3 -m unittest discover -s tests -v          # test suite (36 tests)
python3 scripts/session_docter.py audit .         # dogfood: this repo audits low
```

Layout: `scripts/session_docter.py` (engine), `rules/` (per-rule docs),
`fixtures/` (synthetic sample repos A–F used by tests), `tests/`,
`SKILL.md` (agent procedure), `AGENTS.md` (repo dev rules).

## License

MIT — see [LICENSE](LICENSE).
