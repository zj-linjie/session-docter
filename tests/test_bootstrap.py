"""Bootstrap-mode tests: fixture D (new), E (light docs), F (heavy), plus safety."""

import shutil
import unittest
from pathlib import Path

from helpers import sd, ROOT

FIXTURES = ROOT / "fixtures"


def copy_fixture(name: str) -> Path:
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="sd-boot-"))
    dst = tmp / name
    shutil.copytree(FIXTURES / name, dst)
    return dst


def run_cli(*args):
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = sd.main(list(args))
    return code, buf.getvalue()


class TestBootstrapDNewProject(unittest.TestCase):
    def test_dry_run_proposes_minimal_skeleton_without_writing(self):
        root = copy_fixture("fixture_d_new_project")
        before = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
        code, out = run_cli("bootstrap", str(root), "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("[ create ] AGENTS.md", out)
        self.assertIn("[ create ] docs/PRD.md", out)
        self.assertIn("[ create ] docs/ROADMAP.md", out)
        self.assertIn("[ create ] docs/STATUS.md", out)
        after = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
        self.assertEqual(before, after)

    def test_apply_creates_skeleton_and_reaudits_low(self):
        root = copy_fixture("fixture_d_new_project")
        code, out = run_cli("bootstrap", str(root), "--apply")
        self.assertEqual(code, 0)
        self.assertIn("Re-audit", out)
        self.assertIn("[low]", out)
        for rel_path in ("AGENTS.md", "docs/PRD.md", "docs/ROADMAP.md", "docs/STATUS.md"):
            self.assertTrue((root / rel_path).is_file(), rel_path)

        agents = (root / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("one coherent working set", agents)
        self.assertIn("Read only the sections a task actually touches", agents)
        self.assertLess(len(agents), 4096, "AGENTS template should stay thin")

        # generated structure must audit clean
        res = sd.audit_repo(root)
        self.assertEqual(res.level, "low")


class TestBootstrapELightDocs(unittest.TestCase):
    def test_existing_docs_never_overwritten(self):
        root = copy_fixture("fixture_e_light_docs")
        originals = {
            rel: (root / rel).read_text(encoding="utf-8")
            for rel in ("AGENTS.md", "docs/PRD.md", "docs/STATUS.md")
        }
        code, out = run_cli("bootstrap", str(root), "--apply")
        self.assertEqual(code, 0)
        for rel, content in originals.items():
            self.assertEqual((root / rel).read_text(encoding="utf-8"), content, rel)
            self.assertNotIn(f"[ create ] {rel}", out)
        # missing piece proposed, nothing else
        self.assertIn("[ create ] docs/ROADMAP.md", out)


class TestBootstrapFHeavy(unittest.TestCase):
    def test_refuses_and_suggests_audit(self):
        root = copy_fixture("fixture_f_heavy")
        before = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
        code, out = run_cli("bootstrap", str(root), "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("NO BOOTSTRAP NEEDED", out)
        self.assertIn("audit", out)
        code2, out2 = run_cli("bootstrap", str(root), "--apply")
        self.assertEqual(code2, 0)
        self.assertIn("NO BOOTSTRAP NEEDED", out2)
        after = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
        self.assertEqual(before, after)


class TestBootstrapSafety(unittest.TestCase):
    def test_audit_never_bootstraps_or_writes(self):
        # fixture G spirit: an empty repo with no user intent gets nothing written,
        # even when audited; bootstrap is only reachable via explicit command.
        root = copy_fixture("fixture_d_new_project")
        before = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
        run_cli("audit", str(root))
        after = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
        self.assertEqual(before, after)

    def test_does_not_modify_business_code(self):
        root = copy_fixture("fixture_d_new_project")
        pkg_before = (root / "package.json").read_text(encoding="utf-8")
        run_cli("bootstrap", str(root), "--apply")
        self.assertEqual((root / "package.json").read_text(encoding="utf-8"), pkg_before)


if __name__ == "__main__":
    unittest.main()
