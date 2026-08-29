---
name: session-docter
description: Context-cost doctor for coding-agent repositories. Audit (read-only) to find context amplification — mandatory startup chains, heavy issue/PR list payloads, instruction-file fixed taxes, bulk file reads, missing session boundaries, dense verification loops — then propose/apply thin fixes, or bootstrap a lightweight doc skeleton for a NEW project. Use when sessions feel slow or expensive, when a repo's agent docs have grown heavy, or when the user asks to initialize project docs for a new repo.
---

# Session Docter

Keep this skill thin. The script is the engine; this file is only the operating
procedure. Do not read the whole repo before auditing.

## Route by user intent

- "diagnose / audit context cost / sessions are expensive" → `audit`
- "optimize / fix context usage" → `audit` → propose fixes → approval → `fix --apply`
- "create a new project / initialize project docs / set up agent rules here" → `bootstrap`

Never bootstrap an existing mature repo. Never create docs just because a repo
is empty — bootstrap requires explicit project-creation intent or an explicit
command. Running `audit` must never create files.

## audit (read-only)

```bash
python3 scripts/session_docter.py audit <repo>            # text report
python3 scripts/session_docter.py audit <repo> --json     # machine-readable
```

1. Treat the result as a low-resolution map: confirm by reading only the
   flagged files and lines, never the whole repo.
2. Explain root causes, classify each problem as startup fixed tax /
   repeated replay / long-session history / task working set / loop
   amplification, and report P0 (high) / P1 (medium) / P2 (low) with evidence.
3. Static results are potential risks, not verdicts — say so.

## fix

```bash
python3 scripts/session_docter.py fix <repo> --dry-run    # default
python3 scripts/session_docter.py fix <repo> --apply      # only after approval
```

- Show the target files and unified diffs before any apply; get explicit user
  approval.
- `--apply` touches only agent-facing Markdown (.md/.markdown/.mdx/.mdc). It
  never modifies business code and never deletes knowledge (no CONTEXT/ADR/
  PRD/ROADMAP deletion, no history rewrites).
- Re-run `audit` after applying; fixes it cannot make safely appear as manual
  suggestions (e.g. splitting mutable status into STATUS.md).

## bootstrap (new projects only)

```bash
python3 scripts/session_docter.py bootstrap <repo> --dry-run
python3 scripts/session_docter.py bootstrap <repo> --apply
```

1. Look at the repo top level first; do not scan a whole new repo.
2. Fill templates only with what the user already provided; leave TODO
   otherwise. Do not invent product semantics.
3. Existing docs are never overwritten (keep/conflict states); a repo with a
   mature context system is refused and routed to `audit`.
4. After `--apply` the tool re-audits automatically; the generated structure
   must audit as low risk. It may append session boundaries to AGENTS.md
   (one coherent working set per session) when missing.

## After any change

Suggest verifying with one real small task in a fresh session and comparing
the input size and session feel (A/B). Warn the user if the skill itself is
accumulating weight — skills may be heavy, context must stay thin.
