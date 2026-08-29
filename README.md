<div align="center">

<a href="README.zh-CN.md">简体中文</a> · **English**

<img src="./assets/readme/hero.svg" width="100%" alt="Session Docter — a context-cost doctor for coding-agent repos. A terminal card shows a real audit report with severity-tagged findings and the fix loop reducing risk from 8.6 to 3.0.">

[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org)
[![Dependencies](https://img.shields.io/badge/dependencies-0-success)](#requirements)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Audit the context your coding-agent sessions pay for — then thin it out, safely.**

</div>

## Quick start

No install, no dependencies — Python 3.8+ standard library only:

```bash
# option A: one file, ten seconds
curl -fsSL -o session_docter.py https://raw.githubusercontent.com/zj-linjie/session-docter/main/scripts/session_docter.py
python3 session_docter.py audit /path/to/your/repo

# option B: clone and try the high-risk sample repo
git clone https://github.com/zj-linjie/session-docter && cd session-docter
python3 scripts/session_docter.py audit fixtures/fixture_a_issue_heavy
```

`audit` is strictly read-only. A high-risk repo looks like this:

```text
Session Docter v0.1.0
Repo: ./orion-platform
Overall risk: 8.6 / 10  [high]

HIGH   SD001  Mandatory startup context chain
       AGENTS.md:1  AGENTS.md -> docs/agents/domain.md -> CONTEXT.md (10.4 KB)
       Why: every session force-reads context docs before any real work.
       Fix: make CONTEXT/ADR task-conditional; start from the current issue.

HIGH   SD002  Heavy issue/PR discovery queries
       docs/agents/workflows.md:3  list call loads full payloads for every item
       Fix: list metadata only; fetch the selected item's body on demand.

MEDIUM SD003  Instruction file carries mutable state / fixed input tax
LOW    SD004  Large content files present (not auto-read)
```

Every finding carries severity, rule id, evidence (file + line), why it costs
context, the recommended change, and whether it is auto-fixable.

## What it does

Multi-step agent work gets slow and expensive not because business code is
complex, but because of **context amplification**: rule files that force-read
half the docs folder, issue queries that pull every body and comment,
instruction files that accumulate milestones and machine state, sessions that
never reset across tickets, and verification loops that replay the working
set after every micro edit.

Session Docter diagnoses this with six explainable rules and offers three
modes:

<img src="./assets/readme/workflow.svg" width="100%" alt="Pipeline: any git repo → read-only audit → scored report with evidence → docs-only fix patch → re-audit to verify the delta. New repos can bootstrap instead.">

| Mode | Command | Guarantee |
| --- | --- | --- |
| **audit** | `python3 scripts/session_docter.py audit <repo>` | strictly read-only, text or `--json` |
| **fix** | `... fix <repo> --dry-run` → `--apply` | touches only agent-facing Markdown (`.md/.markdown/.mdx/.mdc`); shows diffs first; never deletes knowledge; never touches business code |
| **bootstrap** | `... bootstrap <new-repo> --dry-run` → `--apply` | new projects only; never overwrites existing docs; refuses mature context systems; re-audits low after apply |

`fix` automates the safe wins — lighten issue-list payloads, convert
mandatory-read chains into task-conditional routing, replace bulk reads with
targeted discovery, append session-boundary and verification-discipline
rules. What it cannot safely automate (e.g. splitting mutable status into a
replace-in-place `STATUS.md`) is reported as a manual proposal instead.

Bootstrap generates a minimal `AGENTS.md + docs/PRD.md + docs/ROADMAP.md +
docs/STATUS.md` skeleton with thin-context routing baked in, so new projects
never grow the fixed tax in the first place.

## Why "high cache hit" is not "low cost"

Prompt caches make repeated prefixes cheap per token, but the prefix still
gets processed and attended to on every turn:

- the fixed startup tax is paid by every session, retry, and child agent;
- every edit invalidates the cache tail, so long mutable prefixes get
  re-billed constantly;
- attention degrades as irrelevant material accumulates — more context means
  more chances to miss the one relevant line.

The cheapest context is the one you never load. Caching lowers the price of
waste; Session Docter lowers the waste. Skills may be heavy — **context must
stay thin**: knowledge lives in routed, on-demand files; only the current
task's inputs belong in the session.

## Risk scoring

Each finding contributes a weight — high 3.5, medium 2.5, low 0.5 — capped at
10:

- **high (≥ 6.5)**: large fixed or repeated cost; fix the P0s first.
- **medium (3.0–6.4)**: bounded taxes worth scheduling.
- **low (< 3.0)**: healthy; remaining items are informational.

The score is a conversation starter, not a grade: every point is traceable to
evidence, and sometimes the right fix is "leave it, the cost is worth it".

## Use as a skill (Codex & friends)

Copy or symlink this repo into the directory your agent scans for skills
(typically `~/.codex/skills/`). Then just ask:

> audit this repo's context cost
> bootstrap project docs for this new repo

The skill routes intent to the right subcommand, reviews the report with you,
and applies fixes only after your approval. After any applied fix, do an A/B
check: run one real small task in a fresh session and compare input size and
session feel.

## What it will not do

- No bill prediction, no private telemetry, no hidden-prompt analysis.
- No deleting project knowledge — PRD/CONTEXT/ADR/ROADMAP are facts to route,
  not garbage to clean.
- No business-code changes, ever.
- No one-size-fits-all agent architecture.

## Development

```bash
python3 -m unittest discover -s tests -v      # 36 tests
python3 scripts/session_docter.py audit .     # dogfood: this repo audits low
```

Layout: `scripts/session_docter.py` (engine, single file) · `rules/` (per-rule
docs) · `fixtures/` (synthetic sample repos used by tests) · `assets/readme/`
(visuals) · `SKILL.md` (agent procedure).

## License

[MIT](LICENSE)
