"""Per-rule positive/negative tests for SD001-SD006."""

import unittest

from helpers import sd, make_repo, audit, by_rule


class TestSD001StartupChain(unittest.TestCase):
    def test_mandatory_multi_level_chain_is_high(self):
        root = make_repo({
            "AGENTS.md": "# AGENTS\n\nBefore any task, read docs/guide.md.\n",
            "docs/guide.md": "# Guide\n\nYou must read CONTEXT.md before any schema change.\n",
            "CONTEXT.md": "# CONTEXT\n\nglossary\n",
        })
        res = audit(root)
        hits = by_rule(res, "SD001")
        self.assertTrue(hits)
        self.assertEqual(hits[0].severity, "high")
        joined = "\n".join(e.text for e in hits[0].evidence)
        self.assertIn("AGENTS.md -> docs/guide.md -> CONTEXT.md", joined)

    def test_on_demand_reference_is_not_flagged(self):
        root = make_repo({
            "AGENTS.md": "# AGENTS\n\nRead CONTEXT.md when the task touches product semantics.\n",
            "CONTEXT.md": "# CONTEXT\n\nsmall\n",
        })
        res = audit(root)
        self.assertFalse([f for f in by_rule(res, "SD001") if f.severity in {"high", "medium"}])

    def test_single_level_mandatory_read_is_medium(self):
        root = make_repo({
            "AGENTS.md": "# AGENTS\n\nStart every session by reading docs/playbook.md.\n",
            "docs/playbook.md": "# Playbook\n\nhello\n",
        })
        res = audit(root)
        hits = by_rule(res, "SD001")
        self.assertTrue(hits)
        self.assertEqual(hits[0].severity, "medium")


class TestSD002IssueQuery(unittest.TestCase):
    def test_list_with_body_and_comments_is_high(self):
        root = make_repo({
            "AGENTS.md": (
                "# AGENTS\n\n"
                "gh issue list --state open --json number,title,body,labels,comments\n"
            ),
        })
        res = audit(root)
        hits = by_rule(res, "SD002")
        self.assertTrue(hits)
        self.assertEqual(hits[0].severity, "high")
        self.assertTrue(hits[0].auto_fixable)

    def test_metadata_only_list_is_clean(self):
        root = make_repo({
            "AGENTS.md": (
                "# AGENTS\n\n"
                "gh issue list --state open --json number,title,labels,assignees\n"
                "Pick one, then `gh issue view 12 --json number,title,body,labels`.\n"
            ),
        })
        res = audit(root)
        self.assertFalse(by_rule(res, "SD002"))

    def test_natural_language_bulk_comments_is_flagged(self):
        root = make_repo({
            "docs/runbook.md": "# Runbook\n\nFetch all comments for open tickets before triage.\n",
        })
        res = audit(root)
        hits = by_rule(res, "SD002")
        self.assertTrue(hits)
        self.assertEqual(hits[0].severity, "medium")


class TestSD003InstructionTax(unittest.TestCase):
    def _big_agents(self, lines=60):
        body = ["# AGENTS.md", "", "## Milestones"]
        for i in range(lines):
            body.append(f"- [x] 2026-{(i % 12) + 1:02d}-14 M{i}: shipped iteration {i} with details")
        return "\n".join(body) + "\n"

    def test_mutable_history_is_flagged(self):
        root = make_repo({"AGENTS.md": self._big_agents()})
        res = audit(root)
        hits = by_rule(res, "SD003")
        self.assertTrue(hits)
        self.assertIn(hits[0].severity, {"medium", "high"})

    def test_small_clean_agents_is_not_flagged(self):
        root = make_repo({
            "AGENTS.md": (
                "# AGENTS.md\n\n## Map\n\n- `src/` — code\n\n## Verify\n\n- `pytest -q`\n"
            ),
        })
        res = audit(root)
        self.assertFalse(by_rule(res, "SD003"))

    def test_large_but_clean_file_is_low_only(self):
        filler = "\n".join(
            f"- module {i}: utilities for parsing, cleaning and exporting datasets"
            for i in range(220)
        )
        root = make_repo({"AGENTS.md": "# AGENTS.md\n\n## Map\n\n" + filler + "\n"})
        res = audit(root)
        hits = by_rule(res, "SD003")
        for f in hits:
            self.assertEqual(f.severity, "low")


class TestSD004LargeFiles(unittest.TestCase):
    BIG = "x" * (40 * 1024)

    def test_bulk_cat_is_flagged(self):
        root = make_repo({
            "AGENTS.md": "# AGENTS\n\n## Refresh\n\nRun:\n\ncat content/*.md\n",
            "content/a.md": "a\n",
        })
        res = audit(root)
        hits = by_rule(res, "SD004")
        self.assertTrue(any("Bulk" in f.title for f in hits))
        self.assertTrue(any(f.auto_fixable for f in hits))

    def test_large_file_not_referenced_is_low_and_not_auto_read(self):
        root = make_repo({
            "AGENTS.md": "# AGENTS\n\n- `src/` — code\n",
            "content/presentations/big-deck.md": "# Deck\n\n" + self.BIG,
        })
        res = audit(root)
        hits = by_rule(res, "SD004")
        self.assertTrue(hits)
        self.assertTrue(all(f.severity == "low" for f in hits))
        self.assertTrue(any("not auto-read" in f.title for f in hits))

    def test_large_file_referenced_from_startup_is_medium(self):
        root = make_repo({
            "AGENTS.md": "# AGENTS\n\nStart every session by reading PROJECT_MAP.md.\n",
            "PROJECT_MAP.md": "# Map\n\n" + self.BIG,
        })
        res = audit(root)
        hits = by_rule(res, "SD004")
        self.assertTrue(any("default reading path" in f.title for f in hits))
        self.assertTrue(any(f.severity == "medium" for f in hits))


class TestSD005SessionBoundary(unittest.TestCase):
    def test_dispatcher_without_boundary_is_flagged(self):
        root = make_repo({
            "AGENTS.md": (
                "# AGENTS\n\n## Flow\n\nThe coordinator hands tickets to a worker pool.\n"
            ),
        })
        res = audit(root)
        hits = by_rule(res, "SD005")
        self.assertTrue(hits)
        self.assertEqual(hits[0].severity, "medium")

    def test_long_lived_session_is_high(self):
        root = make_repo({
            "AGENTS.md": (
                "# AGENTS\n\n## Flow\n\nThe dispatcher session stays alive across tickets; "
                "do not restart the main session.\n"
            ),
        })
        res = audit(root)
        hits = by_rule(res, "SD005")
        self.assertTrue(hits)
        self.assertEqual(hits[0].severity, "high")

    def test_boundary_present_is_clean(self):
        root = make_repo({
            "AGENTS.md": (
                "# AGENTS\n\n## Flow\n\nThe coordinator hands tickets to a worker pool.\n\n"
                "## Sessions\n\nOne session handles one coherent working set; when the current "
                "task is done, stop. Coordinators keep worker receipts small.\n"
            ),
        })
        res = audit(root)
        self.assertFalse(by_rule(res, "SD005"))


class TestSD006ToolLoop(unittest.TestCase):
    def test_build_after_every_edit_is_flagged(self):
        root = make_repo({
            "AGENTS.md": "# AGENTS\n\n## Discipline\n\nRun the full build after every edit.\n",
        })
        res = audit(root)
        hits = by_rule(res, "SD006")
        self.assertTrue(hits)
        self.assertEqual(hits[0].severity, "medium")

    def test_visual_without_batching_boundary_is_flagged(self):
        root = make_repo({
            "AGENTS.md": (
                "# AGENTS\n\n## UI\n\nVerify layout changes with screenshots before merging.\n"
            ),
        })
        res = audit(root)
        hits = by_rule(res, "SD006")
        self.assertTrue(hits)
        self.assertEqual(hits[0].severity, "medium")

    def test_batched_verification_is_clean(self):
        root = make_repo({
            "AGENTS.md": (
                "# AGENTS\n\n## UI\n\nVerify layout changes with screenshots before merging.\n\n"
                "## Discipline\n\nBatch builds and visual checks once a set of edits is stable; "
                "on failure read the relevant error excerpt first.\n"
            ),
        })
        res = audit(root)
        self.assertFalse(by_rule(res, "SD006"))


class TestAuditSafety(unittest.TestCase):
    def test_audit_is_read_only(self):
        # fixture G spirit: running audit on an empty-ish repo must not create anything
        root = make_repo({
            "README.md": "# empty-ish\n",
            "package.json": "{}\n",
        })
        before = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
        res = audit(root)
        after = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
        self.assertEqual(before, after)
        self.assertEqual(res.findings, [])

    def test_scoring_and_levels(self):
        root = make_repo({
            "AGENTS.md": (
                "# AGENTS\n\n"
                "Before any task, read docs/guide.md.\n\n"
                "gh issue list --state open --json number,title,body,comments\n"
            ),
            "docs/guide.md": "You must read CONTEXT.md before any schema change.\n",
            "CONTEXT.md": "glossary\n",
        })
        res = audit(root)
        self.assertEqual(res.level, "high")
        self.assertGreaterEqual(res.overall, 6.5)


if __name__ == "__main__":
    unittest.main()
