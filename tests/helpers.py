"""Shared helpers for session-docter tests."""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "session_docter.py"

_spec = importlib.util.spec_from_file_location("session_docter", SCRIPT)
sd = importlib.util.module_from_spec(_spec)
sys.modules["session_docter"] = sd
_spec.loader.exec_module(sd)


def make_repo(files: dict) -> Path:
    """Create a throwaway repo from {relative_path: content} and return its root."""
    import tempfile

    root = Path(tempfile.mkdtemp(prefix="sd-test-"))
    for rel_path, content in files.items():
        p = root / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    return root


def audit(root: Path):
    return sd.audit_repo(root)


def by_rule(res, rule_id):
    return [f for f in res.findings if f.rule_id == rule_id]
