"""Fix-mode tests: dry-run safety, apply scope, allowed-file restrictions."""

import unittest

from helpers import sd, make_repo

AGENTS_BAD = """# AGENTS.md

## Triage

gh issue list --state open --json number,title,body,labels,comments

## Context

Before any task, read CONTEXT.md and docs/adr/*.
"""

AGENTS_CLEAN = """# AGENTS.md

## Triage

gh issue list --state open --json number,title,labels,assignees

## Context

Read CONTEXT.md only when the current task touches it; ordinary tasks start from the current issue/requirement plus relevant code.
"""


def snapshot(root):
    return {
        str(p.relative_to(root)): p.read_text(encoding="utf-8", errors="replace")
        for p in root.rglob("*")
        if p.is_file()
    }


class TestFix(unittest.TestCase):
    def setUp(self):
        self.root = make_repo({
            "AGENTS.md": AGENTS_BAD,
            "scripts/agent.sh": "#!/bin/sh\ngh issue list --state open --json number,title,body,comments\n",
            "src/main.py": "print('business code')\n",
        })

    def _run_fix(self, *extra):
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            sd.main(["fix", str(self.root), *extra])
        return buf.getvalue()

    def test_dry_run_does_not_modify_files(self):
        before = snapshot(self.root)
        out = self._run_fix("--dry-run")
        self.assertEqual(before, snapshot(self.root))
        self.assertIn("dry-run", out)
        self.assertIn("--- a/", out)  # unified diff shown
        self.assertIn("AGENTS.md", out)

    def test_apply_only_touches_agent_markdown(self):
        before = snapshot(self.root)
        out = self._run_fix("--apply")
        after = snapshot(self.root)

        # business code untouched
        self.assertEqual(before["src/main.py"], after["src/main.py"])
        # non-markdown workflow script untouched (manual suggestion instead)
        self.assertEqual(before["scripts/agent.sh"], after["scripts/agent.sh"])
        self.assertIn("scripts/agent.sh", out)  # surfaced as manual note

        # agent markdown rewritten
        self.assertNotEqual(before["AGENTS.md"], after["AGENTS.md"])
        self.assertNotIn("number,title,body,labels,comments", after["AGENTS.md"])
        self.assertNotIn("Before any task, read", after["AGENTS.md"])
        self.assertIn("only when the current task touches", after["AGENTS.md"])

    def test_apply_is_idempotent(self):
        self._run_fix("--apply")
        first = snapshot(self.root)
        out = self._run_fix("--apply")
        self.assertEqual(first, snapshot(self.root))
        self.assertIn("No high-confidence auto fixes", out)

    def test_no_findings_means_no_changes(self):
        root = make_repo({"AGENTS.md": AGENTS_CLEAN, "README.md": "# hi\n"})
        self.root = root
        out = self._run_fix("--dry-run")
        self.assertIn("No high-confidence auto fixes", out)


if __name__ == "__main__":
    unittest.main()
