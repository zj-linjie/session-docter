# Rules

Session Docter ships six explainable detection rules. The script
(`scripts/session_docter.py`) is the source of truth for the exact patterns;
these docs explain intent, evidence, and the recommended change for each rule.

| ID | Rule | Typical severity |
| --- | --- | --- |
| SD001 | Startup context chain | high |
| SD002 | Heavy issue/PR discovery queries | high |
| SD003 | Instruction file fixed tax / mutable state | medium-high |
| SD004 | Large files & bulk reads | low-medium |
| SD005 | Session lifecycle / working set | medium-high |
| SD006 | Tool loop amplification | medium |

Severity is per-finding; the overall risk score is the capped sum of finding
weights (high 3.5, medium 2.5, low 0.5, max 10).

Every finding carries: severity, rule id, evidence (file + line + matched
text), why it costs context, the recommended change, and whether it is
auto-fixable. Static analysis cannot know everything (e.g. the real length of
remote issues) — such cases are reported as lower-confidence or lower-severity
potential risks instead of fabricated conclusions.
