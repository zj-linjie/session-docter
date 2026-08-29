"""Fixture-level direction tests + dogfood self-audit."""

import unittest

from helpers import sd, ROOT

FIXTURES = ROOT / "fixtures"


class TestFixtureDirections(unittest.TestCase):
    def test_fixture_a_issue_heavy_is_high_risk(self):
        res = sd.audit_repo(FIXTURES / "fixture_a_issue_heavy")
        self.assertEqual(res.level, "high")
        self.assertGreaterEqual(res.overall, 6.5)
        rule_ids = {f.rule_id for f in res.findings}
        for expected in ("SD001", "SD002", "SD003", "SD004", "SD005"):
            self.assertIn(expected, rule_ids)

    def test_fixture_b_visual_is_medium_risk(self):
        res = sd.audit_repo(FIXTURES / "fixture_b_visual")
        self.assertEqual(res.level, "medium")
        self.assertGreaterEqual(res.overall, 3.0)
        self.assertLess(res.overall, 6.5)
        # the big deck exists but is NOT auto-read: no medium/high SD004
        sd004 = [f for f in res.findings if f.rule_id == "SD004"]
        for f in sd004:
            self.assertEqual(f.severity, "low")

    def test_fixture_c_healthy_is_low_risk(self):
        res = sd.audit_repo(FIXTURES / "fixture_c_healthy")
        self.assertEqual(res.level, "low")
        self.assertLess(res.overall, 3.0)

    def test_fixture_e_light_docs_is_low_risk(self):
        res = sd.audit_repo(FIXTURES / "fixture_e_light_docs")
        self.assertEqual(res.level, "low")


class TestSelfAudit(unittest.TestCase):
    def test_session_docter_repo_itself_audits_low(self):
        """Dogfood: our own docs must not trip our own rules."""
        res = sd.audit_repo(ROOT)
        self.assertEqual(
            res.level, "low",
            "self-audit regressed:\n" + sd.render_report(res),
        )
        self.assertFalse([f for f in res.findings if f.severity in {"high", "medium"}])

    def test_json_report_shape(self):
        res = sd.audit_repo(FIXTURES / "fixture_a_issue_heavy")
        d = res.to_dict()
        for key in ("tool", "version", "repo", "overall_risk", "risk_level", "summary", "findings"):
            self.assertIn(key, d)
        f0 = d["findings"][0]
        for key in ("id", "title", "severity", "confidence", "why", "recommendation",
                    "auto_fixable", "evidence"):
            self.assertIn(key, f0)


if __name__ == "__main__":
    unittest.main()
