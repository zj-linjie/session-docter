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

## False-positive guards

Prose (natural-language) patterns apply a negation guard: when a marker like
不要 / 禁止 / 不含 / don't / never / without appears just before the match, the
hit is skipped (a rule that *prohibits* bulk reads is healthy, not risky).
Structural `gh` command patterns stay shape-precise instead: the field list
after `--json` is matched with a bounded identifier class, so trailing prose
on the same line cannot bridge into a hit. Chinese full-log patterns require
a reading verb (读取/查看/下载/获取/拉取) so content policies like “不含完整
日志” or test-matrix rows are not mistaken for loop mandates. SD002 also
calibrates severity: one structural hit outside instruction files is medium;
two or more, or any hit in the startup file, is high.
