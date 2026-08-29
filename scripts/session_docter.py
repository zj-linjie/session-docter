#!/usr/bin/env python3
"""Session Docter — a context-cost doctor for coding-agent repositories.

Modes:
  audit      read-only diagnosis: risk score + evidence + recommendations
  fix        propose (default) or apply high-confidence fixes to agent-facing docs
  bootstrap  initialize a lightweight doc skeleton for a NEW project

Design rules:
  * `audit` never writes anything.
  * `fix` only touches agent-facing Markdown (.md/.markdown/.mdx/.mdc);
    it never deletes knowledge and never modifies business code.
  * `bootstrap` is conservative: it never overwrites existing docs and refuses
    repos that already carry a mature context system.

Python 3.8+ standard library only. No third-party dependencies.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Set, Tuple

VERSION = "0.1.0"

# ---------------------------------------------------------------------------
# constants
# ---------------------------------------------------------------------------

DEFAULT_EXCLUDE_DIRS: Set[str] = {
    ".git", ".hg", ".svn", "node_modules", "dist", "build", "out", "target",
    ".venv", "venv", "__pycache__", ".next", ".nuxt", "coverage",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".idea", ".vscode",
    # session-docter's own synthetic samples / test suites are never scanned
    # when auditing a repo that contains them:
    "fixtures", "tests", "test",
}
ALLOWED_DOT_DIRS = {".github", ".cursor", ".claude"}

INSTRUCTION_FILE_NAMES = [
    "AGENTS.md", "CLAUDE.md", "GEMINI.md", "CODEX.md",
    ".cursorrules", ".windsurfrules", ".clinerules",
]
INSTRUCTION_GLOBS = [
    ".github/copilot-instructions.md",
    ".cursor/rules/*.mdc",
    ".cursor/rules/*.md",
    ".claude/rules/*.md",
]

DOC_SUFFIXES = {".md", ".markdown", ".mdx", ".mdc", ".txt", ".rst"}
CMD_SCAN_SUFFIXES = DOC_SUFFIXES | {".sh", ".bash", ".zsh", ".yaml", ".yml"}
LARGE_FILE_SUFFIXES = {
    ".md", ".markdown", ".mdx", ".mdc", ".html", ".htm", ".txt", ".json",
    ".yaml", ".yml", ".log", ".csv", ".rst", ".adoc",
}
LOG_LIKE_SUFFIXES = {".log", ".csv"}
LARGE_FILE_BYTES = 32 * 1024
LOG_LIKE_BYTES = 16 * 1024
HEAVY_OPTIONAL_BYTES = 16 * 1024

FIXABLE_SUFFIXES = {".md", ".markdown", ".mdx", ".mdc"}

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}
SEVERITY_WEIGHT = {"high": 3.5, "medium": 2.5, "low": 0.5, "info": 0.0}
HIGH_RISK = 6.5
MEDIUM_RISK = 3.0

# ---------------------------------------------------------------------------
# data model
# ---------------------------------------------------------------------------


@dataclass
class Evidence:
    file: str
    line: int
    text: str


@dataclass
class Finding:
    rule_id: str
    title: str
    severity: str  # high | medium | low | info
    confidence: str  # high | medium | low
    why: str
    recommendation: str
    evidence: List[Evidence] = field(default_factory=list)
    auto_fixable: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.rule_id,
            "title": self.title,
            "severity": self.severity,
            "confidence": self.confidence,
            "why": self.why,
            "recommendation": self.recommendation,
            "auto_fixable": self.auto_fixable,
            "evidence": [
                {"file": e.file, "line": e.line, "text": e.text} for e in self.evidence
            ],
        }


@dataclass
class RefEdge:
    src: Path
    dst: Path
    line_no: int
    line: str
    mandatory: bool


@dataclass
class AuditResult:
    root: Path
    findings: List[Finding]
    overall: float
    level: str
    files_scanned: int
    instruction_count: int
    large_count: int

    def to_dict(self) -> dict:
        return {
            "tool": "session-docter",
            "version": VERSION,
            "repo": str(self.root),
            "overall_risk": self.overall,
            "risk_level": self.level,
            "summary": {
                "files_scanned": self.files_scanned,
                "instruction_files": self.instruction_count,
                "large_files": self.large_count,
            },
            "findings": [f.to_dict() for f in self.findings],
        }


@dataclass
class PlannedChange:
    path: Path
    rule_id: str
    description: str
    original: str
    modified: str


@dataclass
class BootstrapItem:
    rel_path: str
    action: str  # create | keep | conflict
    note: str = ""
    template: str = ""
    existing: str = ""


@dataclass
class RepoCtx:
    root: Path
    instruction_files: List[Path]
    scan_files: List[Path]
    texts: Dict[Path, str]


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------


def rel(root: Path, p: Path) -> str:
    try:
        return str(p.relative_to(root))
    except ValueError:
        return str(p)


def human_bytes(n: int) -> str:
    if n >= 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n} B"


def has_cjk(s: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in s)


def estimate_tokens(text: str) -> int:
    """Rough token estimate (clearly labeled as an estimate everywhere)."""
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    other = len(text) - cjk
    return int(other / 3.8) + int(cjk / 1.4)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def iter_files(root: Path, suffixes: Optional[Set[str]] = None) -> List[Path]:
    out: List[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in DEFAULT_EXCLUDE_DIRS
            and (not d.startswith(".") or d in ALLOWED_DOT_DIRS)
        )
        for name in sorted(filenames):
            p = Path(dirpath) / name
            if suffixes is not None and p.suffix.lower() not in suffixes:
                if name not in INSTRUCTION_FILE_NAMES:
                    continue
            out.append(p)
    return out


def find_instruction_files(root: Path) -> List[Path]:
    found: List[Path] = []
    for name in INSTRUCTION_FILE_NAMES:
        p = root / name
        if p.is_file():
            found.append(p)
    for g in INSTRUCTION_GLOBS:
        for p in sorted(root.glob(g)):
            if p.is_file():
                found.append(p)
    seen: Set[Path] = set()
    out: List[Path] = []
    for p in found:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            out.append(p)
    return out


def build_ctx(root: Path) -> RepoCtx:
    root = Path(root).resolve()
    instruction = find_instruction_files(root)
    scan: List[Path] = list(instruction)
    seen = {p.resolve() for p in scan}
    for p in iter_files(root, CMD_SCAN_SUFFIXES):
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            scan.append(p)
    texts = {p: read_text(p) for p in scan}
    return RepoCtx(root=root, instruction_files=instruction, scan_files=scan, texts=texts)


def count_large_files(root: Path) -> int:
    n = 0
    for p in iter_files(root, LARGE_FILE_SUFFIXES):
        try:
            s = p.stat().st_size
        except OSError:
            continue
        thr = LOG_LIKE_BYTES if p.suffix.lower() in LOG_LIKE_SUFFIXES else LARGE_FILE_BYTES
        if s >= thr:
            n += 1
    return n


# ---------------------------------------------------------------------------
# detection patterns
# ---------------------------------------------------------------------------

MANDATORY_RE = re.compile(
    r"(?i)(?:"
    r"\bmust\s+(?:first\s+)?(?:read\b|start\s+by\s+reading\b|be\s+read\b)"
    r"|\brequired\s+reading\b"
    r"|\balways\s+read\b"
    r"|\bread\s+(?:all|every)\b"
    r"|\bbefore\s+(?:any|every|each)\s+(?:task|session|ticket|work)\b"
    r"|\bread\b[^.\n]{0,60}\bbefore\s+(?:any|every|each|starting|you\s+start|doing|touching)\b"
    r"|\bstart(?:s|ing)?\s+(?:every|each|any|a)?\s*(?:task|session|ticket)\s+by\s+reading\b"
    r"|\bfirst\s+(?:step|thing)\s+is\s+to\s+read\b"
    r"|\bdo\s+not\s+(?:start|begin)\b[^.\n]{0,30}\bwithout\s+reading\b"
    r"|\bnever\s+(?:start|begin)\b[^.\n]{0,30}\bwithout\s+reading\b"
    r"|\bwithout\s+first\s+reading\b"
    r"|\b\u5fc5\u8bfb\b"
    r"|\b\u5fc5\u987b(?:\u5148)?\u9605\u8bfb\b"
    r"|\u5148(?:\u901a)?\u8bfb"
    r"|\u901a\u8bfb"
    r"|\u5f00\u59cb[^\n]{0,20}(?:\u4e4b?\u524d)[^\n]{0,20}(?:\u9605\u8bfb|\u8bfb)"
    r"|\u9605\u8bfb[^\n]{0,30}(?:\u4e4b\u540e|\u540e\u518d|\u624d\u80fd|\u65b9\u53ef)"
    r")"
)

BACKTICK_REF_RE = re.compile(r"`([^`\n]+?\.(?:md|markdown|mdx|mdc|txt))`", re.I)
MDLINK_REF_RE = re.compile(r"\]\(([^)\n]+?\.(?:md|markdown|mdx|mdc))\)", re.I)
BARE_REF_RE = re.compile(r"(?<![\w./-])((?:[\w.-]+/)*[\w.-]+\.(?:md|markdown|mdx|mdc|txt))(?![\w/])", re.I)
GLOB_REF_RE = re.compile(r"(?<![\w*./-])((?:[\w.-]+/)+\*(?:/\*)*)")

CONTEXT_DOC_RE = re.compile(
    r"(?i)(context|adr|decision|prd|roadmap|status|history|journal|project[_-]?map|wayfinder|glossary|onboarding)"
)


def is_context_doc(p: Path) -> bool:
    s = str(p).replace("\\", "/").lower()
    if CONTEXT_DOC_RE.search(Path(s).name):
        return True
    if "/adr/" in s or s.startswith("adr/") or s.endswith("/adr"):
        return True
    return False


SD002_CMD_RULES: List[Tuple[re.Pattern, str, str]] = [
    (
        re.compile(r"(?i)gh\s+(?:issue|pr)\s+list\b[^|\n]*--json[^\n]*\b(?:body|comments)\b"),
        "high",
        "list call loads full bodies/comments for every item",
    ),
    (
        re.compile(r"(?i)gh\s+(?:issue|pr)\s+list\b[^|\n]*--json[^\n]*\bfiles\b"),
        "medium",
        "list call loads changed-file payloads for every item",
    ),
    (
        re.compile(r"(?i)gh\s+(?:issue|pr)\s+list\b[^|\n]*--json[^\n]*\b(?:reviews|diff)\b"),
        "medium",
        "list call loads review/diff payloads for every item",
    ),
    (
        re.compile(r"(?i)gh\s+run\s+(?:view|watch)\b[^|\n]*--log\b"),
        "medium",
        "full CI log fetched by default",
    ),
    (
        re.compile(r"(?i)gh\s+api\b[^|\n]*\bcomments\b[^|\n]*--paginate\b"),
        "medium",
        "paginated API walk over all comments",
    ),
    (
        re.compile(r"(?i)gh\s+pr\s+diff\b[^|\n]*\b(?:for|each|all|every)\b"),
        "medium",
        "full PR diff inside a loop over PRs",
    ),
]
SD002_NL_RULES: List[Tuple[re.Pattern, str, str]] = [
    (
        re.compile(r"(?i)\b(?:read|fetch|load|pull)\b[^.\n]{0,30}\ball\b[^.\n]{0,30}\b(?:comments|bodies|full\s+bodies|descriptions)\b"),
        "medium",
        "rule asks to read every comment/body in bulk",
    ),
    (
        re.compile(r"(?:\u6240\u6709|\u5168\u90e8)[^\n]{0,12}(?:issue|\u8bc4\u8bba|\u6b63\u6587)[^\n]{0,20}(?:\u8bfb\u53d6|\u62c9\u53d6|\u83b7\u53d6)|(?:\u8bfb\u53d6|\u62c9\u53d6|\u83b7\u53d6)[^\n]{0,10}\u6240\u6709[^\n]{0,12}(?:issue|\u8bc4\u8bba|\u6b63\u6587)"),
        "medium",
        "\u89c4\u5219\u8981\u6c42\u8bfb\u53d6\u5168\u90e8 issue \u6b63\u6587/\u8bc4\u8bba",
    ),
]

MUTABLE_LINE_RE = re.compile(
    r"(?im)(?:"
    r"^\s*#{1,6}\s+(?:the\s+)?(?:current|latest)\s+(?:status|state|phase|environment)\b"
    r"|^\s*#{1,6}\s+(?:status|state|environment|machine|device|setup|milestones?|progress|changelog|history|updates?|release|log)\b"
    r"|^\s*#{1,6}\s+.*(?:\u5f53\u524d|\u72b6\u6001|\u73af\u5883|\u8bbe\u5907|\u672c\u673a|\u91cc\u7a0b\u7891|\u8fdb\u5c55|\u5386\u53f2|\u6d41\u6c34|\u65e5\u5fd7)"
    r"|\blast\s+updated(?:\s+at)?\s*[:\d]"
    r"|\bas\s+of\b"
    r"|\b20\d{2}-\d{1,2}-\d{1,2}\b"
    r"|\b20\d{2}/\d{1,2}/\d{1,2}\b"
    r"|\[x\]"
    r"|\b(?:signature|signed\s+off)\b"
    r"|\u7b7e\u540d"
    r"|\bthis\s+machine\b"
    r"|\bdevice\s*:"
    r"|\u8bbe\u5907[:\uff1a]"
    r")"
)

BULK_READ_RES: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"(?i)\bcat\s+\S*\*\S*"), "cat with a glob"),
    (re.compile(r"(?i)\bfind\s+\S+[^;\n|]*-exec\s+cat\b"), "find -exec cat"),
    (re.compile(r"(?i)\bcat\s+(?:content|docs?|notes|posts|pages|chapters|src)/"), "cat over a docs directory"),
    (re.compile(r"(?i)\bread\s+(?:all|every)\s+(?:files?|docs?|documents?|markdown\s+files?)\b"), "read-every-file rule"),
    (re.compile(r"(?i)\bread\s+the\s+entire\s+(?:directory|folder)\b"), "read entire directory"),
    (
        re.compile(r"\u901a\u8bfb|\u5168\u6587\u8bfb\u53d6|\u8bfb\u53d6\u5168\u90e8(?:\u6587\u4ef6|\u6587\u6863)|(?:\u8bfb\u53d6|\u8bfb\u5b8c)(?:\u76ee\u5f55\u4e0b)?\u6240\u6709(?:\u6587\u4ef6|\u6587\u6863)"),
        "\u5168\u76ee\u5f55\u6b63\u6587\u8bfb\u53d6\u89c4\u5219",
    ),
]

ORCH_RE = re.compile(
    r"(?i)\b(?:dispatch(?:er|ers)?|workers?|coordinators?|orchestrat(?:e|es|or|ion))\b"
    r"|\u5de5\u5355|\u6d3e\u53d1|\u5206\u53d1\u4efb\u52a1|\u534f\u8c03\u8005"
)
MULTI_TASK_RE = re.compile(
    r"(?i)\btask\s+(?:list|queue)\b|\bbacklog\b|\u4efb\u52a1\u5217\u8868|\u4efb\u52a1\u961f\u5217"
    r"|\b(?:next|another)\s+task\b"
)
BOUNDARY_RE = re.compile(
    r"(?i)one\s+(?:coherent\s+)?working\s+set"
    r"|one\s+task\s+per\s+session|single\s+(?:task|working\s+set)\s+per\s+session"
    r"|stop\s+after\s+(?:the\s+|this\s+)?(?:task|ticket|working\s+set)"
    r"|do\s+not\s+(?:automatically\s+)?(?:pick|take|start|continue)\b[^.\n]{0,30}\bnext"
    r"|new\s+session\s+(?:for|per)\b|fresh\s+session\s+per\b"
    r"|\breceipts?\b"
    r"|\u5b8c\u6210\u540e(?:\u505c\u6b62|\u7ed3\u675f)"
    r"|\u4e0d\u81ea\u52a8(?:\u9886\u53d6|\u7ee7\u7eed|\u5f00\u59cb)"
    r"|\u4e00\u4e2a\u4f1a\u8bdd|\u65b0(?:\u7684)?\u4f1a\u8bdd"
)
LONG_LIVED_RE = re.compile(
    r"(?i)long[-\s]?lived"
    r"|keep\s+(?:the\s+)?(?:main\s+|dispatcher\s+)?session\s+(?:alive|running|open)"
    r"|persistent\s+(?:main\s+|dispatcher\s+)?session\b"
    r"|session\s+stays?\s+alive"
    r"|do\s+not\s+restart\s+the\s+(?:main\s+)?session"
    r"|\u4e0d\u91cd\u542f"
    r"|\u957f\u671f(?:\u8fd0\u884c|\u4fdd\u6301|\u9a7b\u7559)"
)
TRANSCRIPT_RE = re.compile(
    r"(?i)\btranscripts?\b"
    r"|\bfull\s+(?:logs?|diffs?|outputs?)\b"
    r"|\u5b8c\u6574(?:\u65e5\u5fd7|\u8f93\u51fa|diff)"
)

DENSE_RES: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"(?i)\b(?:re)?builds?\b[^.\n]{0,40}\bafter\s+(?:every|each)\b"), "build after every edit"),
    (re.compile(r"(?i)\bafter\s+(?:every|each)\b[^.\n]{0,30}\b(?:edit|change|tweak|fix|line)\b[^.\n]{0,40}\b(?:build|compile|test)\b"), "per-edit rebuild mandate"),
    (re.compile(r"(?i)\b(?:screenshot|screen\s+capture|browser)\b[^.\n]{0,50}\b(?:every|each|per)\b"), "capture after every step"),
    (re.compile(r"(?i)\b(?:every|each)\b[^.\n]{0,25}\b(?:step|change|edit|iteration|screen|page|view)\b[^.\n]{0,40}\b(?:screenshot|review|browser|screen\s+capture)\b"), "capture/review every step"),
    (re.compile(r"(?i)\bread\s+(?:the\s+)?full\s+(?:build|compile|ci|test|error)\s+logs?\b"), "full log read on failure"),
    (re.compile(r"(?i)\balways\s+run\s+(?:the\s+)?full\s+(?:build|test\s+suite)\b"), "always run the full build"),
    (re.compile(r"(?i)\breview\s+(?:every|each)\s+(?:change|edit|diff|pr)\b"), "review every change"),
    (
        re.compile(r"(?:\u6bcf\u6b21|\u6bcf\u4e00\u6b65|\u6bcf\u4e2a)[^\n]{0,15}(?:\u7f16\u8f91|\u4fee\u6539|\u6b65\u9aa4)(?:\u4e4b\u540e|\u540e)?[^\n]{0,25}(?:\u6784\u5efa|\u7f16\u8bd1|\u622a\u56fe|\u6d4b\u8bd5)|(?:\u6784\u5efa|\u7f16\u8bd1|\u6d4b\u8bd5)[^\n]{0,10}\u6bcf\u6b21"),
        "\u6bcf\u6b65\u6784\u5efa/\u622a\u56fe\u89c4\u5219",
    ),
    (
        re.compile(r"(?:\u5b8c\u6574|\u5168\u90e8)(?:\u7f16\u8bd1|\u6784\u5efa|CI)?\u65e5\u5fd7"),
        "\u8bfb\u53d6\u5b8c\u6574\u65e5\u5fd7\u89c4\u5219",
    ),
]
VISUAL_RE = re.compile(r"(?i)\bscreenshots?\b|\bplaywright\b|\bpuppeteer\b|\u622a\u56fe|\bbrowsers?\b")
BATCH_RE = re.compile(
    r"(?i)\bbatch"
    r"|\u96c6\u4e2d"
    r"|\u7a33\u5b9a\u540e"
    r"|stabilis?e?|stabiliz"
    r"|(?:once|after|when)\s+(?:the\s+)?(?:ui|changes?|edits?|feature)\s+(?:are\s+|is\s+)?stabl"
    r"|collect(?:ed)?\s+(?:verif|review|check)"
    r"|milestone\s+(?:check|review)"
)

# ---------------------------------------------------------------------------
# reference graph (SD001)
# ---------------------------------------------------------------------------


def extract_doc_refs(line: str) -> List[str]:
    refs: List[str] = []
    for rx in (BACKTICK_REF_RE, MDLINK_REF_RE, BARE_REF_RE, GLOB_REF_RE):
        for m in rx.finditer(line):
            refs.append(m.group(1))
    seen: Set[str] = set()
    out: List[str] = []
    for r in refs:
        k = r.strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(r.strip())
    return out


def resolve_ref(root: Path, src: Path, ref: str) -> List[Path]:
    ref = ref.strip().strip("<>").replace("\\", "/")
    if not ref or "://" in ref or ref.startswith("#"):
        return []
    root_s = str(root.resolve())
    if "*" in ref:
        base = ref.split("*", 1)[0]
        base_dir = base.rsplit("/", 1)[0] if "/" in base else ""
        cand = (root / base_dir).resolve() if base_dir else root.resolve()
        if str(cand) == root_s or str(cand).startswith(root_s + os.sep):
            if cand.is_dir():
                files = sorted(
                    p for p in cand.iterdir()
                    if p.is_file() and p.suffix.lower() in DOC_SUFFIXES
                )
                return files[:20]
        return []
    ref = ref.lstrip("./")
    for base in (root, src.parent):
        cand = (base / ref).resolve()
        if (str(cand) == root_s or str(cand).startswith(root_s + os.sep)) and cand.is_file():
            if cand.suffix.lower() in DOC_SUFFIXES:
                return [cand]
    return []


def build_ref_graph(ctx: RepoCtx) -> Dict[Path, List[RefEdge]]:
    edges: Dict[Path, List[RefEdge]] = {}
    frontier: List[Path] = list(ctx.instruction_files)
    scanned: Set[Path] = set(frontier)
    hops = 0
    while frontier and hops < 6:
        nxt: List[Path] = []
        for f in frontier:
            if f in edges:
                continue
            text = ctx.texts.get(f) or read_text(f)
            elist: List[RefEdge] = []
            for i, line in enumerate(text.splitlines(), 1):
                mandatory = bool(MANDATORY_RE.search(line))
                for ref in extract_doc_refs(line):
                    for dst in resolve_ref(ctx.root, f, ref):
                        elist.append(RefEdge(f, dst, i, line.strip()[:160], mandatory))
            edges[f] = elist
            for e in elist:
                rp = e.dst.resolve()
                if rp not in scanned and e.dst.suffix.lower() in DOC_SUFFIXES:
                    scanned.add(rp)
                    nxt.append(e.dst)
        frontier = nxt
        hops += 1
    return edges


def mandatory_chains(
    ctx: RepoCtx, edges: Dict[Path, List[RefEdge]]
) -> Tuple[List[List[Path]], Dict[Path, List[Path]]]:
    chains: List[List[Path]] = []
    reachable: Dict[Path, List[Path]] = {}
    for inst in ctx.instruction_files:
        stack: List[Tuple[Path, List[Path]]] = [(inst, [inst])]
        visited = {inst}
        while stack:
            cur, path = stack.pop()
            for e in edges.get(cur, []):
                if not e.mandatory or e.dst in visited:
                    continue
                visited.add(e.dst)
                newpath = path + [e.dst]
                chains.append(newpath)
                reachable.setdefault(e.dst, newpath)
                stack.append((e.dst, newpath))
    return chains, reachable


# ---------------------------------------------------------------------------
# rules
# ---------------------------------------------------------------------------


def rule_sd001(
    ctx: RepoCtx,
    edges: Dict[Path, List[RefEdge]],
    chains: List[List[Path]],
    mandatory_reachable: Dict[Path, List[Path]],
) -> List[Finding]:
    findings: List[Finding] = []
    root = ctx.root

    def fsize(p: Path) -> int:
        try:
            return p.stat().st_size
        except OSError:
            return 0

    def chain_str(path: List[Path]) -> str:
        return " -> ".join(rel(root, p) for p in path)

    context_hits = {p: ch for p, ch in mandatory_reachable.items() if is_context_doc(p)}

    if context_hits:
        evidence: List[Evidence] = []
        for p in sorted(context_hits, key=lambda x: rel(root, x)):
            ch = mandatory_reachable[p]
            detail = f"{rel(root, p)} ({human_bytes(fsize(p))}, {len(read_text(p).splitlines())} lines)"
            evidence.append(
                Evidence(rel(root, ch[0]), 1, chain_str(ch) + "   [" + detail + "]")
            )
        multi = sum(1 for c in chains if len(c) >= 3)
        note = ""
        if multi:
            note = f" {multi} mandatory chain(s) hop through intermediate rule docs (multi-level jump)."
        findings.append(Finding(
            rule_id="SD001",
            title="Mandatory startup context chain",
            severity="high",
            confidence="high",
            why=("Instruction files force context/history/decision docs (directly or transitively) into "
                 "every session startup, so every task pays this fixed context cost before any real work. "
                 "The tax grows as the docs accumulate."),
            recommendation=("Convert the mandatory chain into task-conditional routing: ordinary tasks start "
                            "from the current issue/requirement plus relevant code; read CONTEXT/ADR/PRD/"
                            "ROADMAP/STATUS sections only when the task touches them.") + note,
            evidence=evidence,
            auto_fixable=True,
        ))
    elif mandatory_reachable:
        evidence = []
        for p in sorted(mandatory_reachable, key=lambda x: rel(root, x))[:8]:
            ch = mandatory_reachable[p]
            evidence.append(
                Evidence(rel(root, ch[0]), 1, chain_str(ch) + f"   [{human_bytes(fsize(p))}]")
            )
        findings.append(Finding(
            rule_id="SD001",
            title="Mandatory doc reads at startup",
            severity="medium",
            confidence="high",
            why=("Every session is required to read additional docs before working, adding a fixed cost "
                 "to all tasks even while the docs are still small."),
            recommendation=("Prefer task-conditional routing over blanket mandatory reads; keep startup to "
                            "the instruction file plus the current task inputs."),
            evidence=evidence,
            auto_fixable=True,
        ))

    if not context_hits:
        heavy_optional: List[Tuple[Path, Path]] = []
        for src, elist in edges.items():
            for e in elist:
                if not e.mandatory and is_context_doc(e.dst) and fsize(e.dst) > HEAVY_OPTIONAL_BYTES:
                    heavy_optional.append((src, e.dst))
        if heavy_optional:
            evidence = [
                Evidence(
                    rel(root, s), 1,
                    f"{rel(root, s)} references {rel(root, d)} ({human_bytes(fsize(d))}) — on-demand reference to a heavy doc",
                )
                for s, d in heavy_optional[:8]
            ]
            findings.append(Finding(
                rule_id="SD001",
                title="Heavy docs referenced (verify they stay on-demand)",
                severity="low",
                confidence="medium",
                why=("Heavy context/history docs are referenced from startup files; if any rule turns these "
                     "references into mandatory reads, every session pays for them."),
                recommendation="Keep references explicitly on-demand and section-scoped (search/heading/line-range).",
                evidence=evidence,
                auto_fixable=False,
            ))
    return findings


def rule_sd002(ctx: RepoCtx) -> List[Finding]:
    hits: List[Evidence] = []
    worst = "low"
    rank = {"high": 0, "medium": 1, "low": 2, "info": 3}
    for p in ctx.scan_files:
        text = ctx.texts.get(p, "")
        for i, line in enumerate(text.splitlines(), 1):
            for rx, sev, label in SD002_CMD_RULES + SD002_NL_RULES:
                if rx.search(line):
                    hits.append(Evidence(rel(ctx.root, p), i, f"{label}: {line.strip()[:140]}"))
                    if rank[sev] < rank[worst]:
                        worst = sev
                    break
    if not hits:
        return []
    return [Finding(
        rule_id="SD002",
        title="Heavy issue/PR discovery queries",
        severity=worst,
        confidence="high",
        why=("Issue/PR discovery becomes a context dump: each list call pulls full payloads for every "
             "item, and the loop replays all of it in the transcript. Token cost scales with the whole "
             "tracker, not with the one ticket being worked."),
        recommendation=("List metadata only (e.g. --json number,title,labels,assignees), fetch the selected "
                        "item's body with `gh issue view <n>`, and read comments only when the body is "
                        "insufficient. Same for PR diffs and CI logs: fetch per item on demand."),
        evidence=hits[:12],
        auto_fixable=True,
    )]


def rule_sd003(ctx: RepoCtx) -> List[Finding]:
    findings: List[Finding] = []
    for f in ctx.instruction_files:
        text = ctx.texts.get(f, "")
        lines = text.splitlines()
        try:
            nbytes = f.stat().st_size
        except OSError:
            nbytes = len(text.encode("utf-8", "replace"))
        hits = [(i, ln) for i, ln in enumerate(lines, 1) if MUTABLE_LINE_RE.search(ln)]
        ratio = len(hits) / max(1, len(lines))
        severity = None
        if ratio >= 0.30 or (nbytes > 8192 and ratio >= 0.15) or nbytes > 32768:
            severity = "high"
        elif ratio >= 0.10 or nbytes > 16384:
            severity = "medium"
        elif nbytes > 4096:
            severity = "low"
        if not severity:
            continue
        evidence = [
            Evidence(
                rel(ctx.root, f), 0,
                f"{rel(ctx.root, f)}: {human_bytes(nbytes)}, {len(lines)} lines, "
                f"~{estimate_tokens(text)} tokens (estimate), mutable-looking lines: {len(hits)} ({ratio:.0%})",
            )
        ]
        for i, ln in hits[:5]:
            evidence.append(Evidence(rel(ctx.root, f), i, ln.strip()[:140]))
        if severity == "low":
            findings.append(Finding(
                rule_id="SD003",
                title="Large instruction file",
                severity=severity,
                confidence="medium",
                why=("This file is loaded in every session. Size alone is not a verdict, but above ~4 KB it "
                     "is worth checking that every section is truly needed by every task."),
                recommendation=("Keep the instruction file to: project map, core invariants, verify commands, "
                                "on-demand routing. Move anything task-specific or mutable out to reference docs."),
                evidence=evidence,
                auto_fixable=False,
            ))
        else:
            findings.append(Finding(
                rule_id="SD003",
                title="Instruction file carries mutable state / fixed input tax",
                severity=severity,
                confidence="high",
                why=("Instruction files are loaded in every session. Mutable status, machine/environment "
                     "details, milestones and history here are paid by every task, churn provider-side "
                     "caches, and grow without bound as the project progresses."),
                recommendation=("Split by volatility: keep the project map, core invariants and verify "
                                "commands in the instruction file; move environment/status/milestones into "
                                "STATUS.md (replace entries in place, never append history). "
                                "See rules/SD003_agents_fixed_tax.md."),
                evidence=evidence,
                auto_fixable=False,
            ))
    return findings


def rule_sd004(
    ctx: RepoCtx, mandatory_reachable: Dict[Path, List[Path]]
) -> List[Finding]:
    findings: List[Finding] = []
    bulk: List[Evidence] = []
    bulk_worst = "low"
    rank = {"high": 0, "medium": 1, "low": 2, "info": 3}
    for p in ctx.scan_files:
        text = ctx.texts.get(p, "")
        for i, line in enumerate(text.splitlines(), 1):
            for rx, label in BULK_READ_RES:
                if rx.search(line):
                    bulk.append(Evidence(rel(ctx.root, p), i, f"{label}: {line.strip()[:140]}"))
                    if p in ctx.instruction_files or p in mandatory_reachable:
                        if rank["high"] < rank[bulk_worst]:
                            bulk_worst = "high"
                    elif rank["medium"] < rank[bulk_worst]:
                        bulk_worst = "medium"
                    break
    if bulk:
        findings.append(Finding(
            rule_id="SD004",
            title="Bulk full-content reads in rules",
            severity=bulk_worst,
            confidence="high",
            why=("Rules that read whole directories or glob-wide file contents pull large payloads into the "
                 "session regardless of the task, then replay them on every retry or review round."),
            recommendation=("Replace bulk reads with targeted discovery: list files, search by keyword/heading, "
                            "then read only the relevant files or line ranges."),
            evidence=bulk[:10],
            auto_fixable=True,
        ))

    # large files on disk: distinguish "exists" from "on the default reading path"
    larges: List[Tuple[Path, int]] = []
    for p in iter_files(ctx.root, LARGE_FILE_SUFFIXES):
        try:
            s = p.stat().st_size
        except OSError:
            continue
        thr = LOG_LIKE_BYTES if p.suffix.lower() in LOG_LIKE_SUFFIXES else LARGE_FILE_BYTES
        if s >= thr:
            larges.append((p, s))
    if not larges:
        return findings

    haystacks: List[Tuple[str, str]] = [
        (rel(ctx.root, f), ctx.texts.get(f, "")) for f in ctx.instruction_files
    ]
    for p in mandatory_reachable:
        rp = rel(ctx.root, p)
        if all(rp != src for src, _ in haystacks):
            haystacks.append((rp, read_text(p)))

    referenced: List[Evidence] = []
    unreferenced: List[str] = []
    for p, n in sorted(larges, key=lambda x: -x[1]):
        rp = rel(ctx.root, p)
        name = p.name
        src_hit = ""
        for src, t in haystacks:
            if name in t or rp in t:
                src_hit = src
                break
        if src_hit:
            referenced.append(Evidence(rp, 0, f"{rp} ({human_bytes(n)}) — on the default reading path via {src_hit}"))
        else:
            unreferenced.append(f"{rp} ({human_bytes(n)})")

    if referenced:
        findings.append(Finding(
            rule_id="SD004",
            title="Large file(s) on the default reading path",
            severity="medium",
            confidence="high",
            why=("These large files are reachable from startup rules, so sessions may load them wholesale "
                 "even when a heading or a line range would answer the task."),
            recommendation=("Keep large assets out of mandatory startup chains; read them via search/heading/"
                            "line-range on demand."),
            evidence=referenced[:8],
            auto_fixable=False,
        ))
    if unreferenced:
        findings.append(Finding(
            rule_id="SD004",
            title="Large content files present (not auto-read)",
            severity="low",
            confidence="high",
            why=("Large files exist but are not referenced by startup rules — they only cost context if a "
                 "rule or habit bulk-reads them. This is informational, not a verdict."),
            recommendation=("Prefer search/heading/line-range reads when working with these files; never "
                            "bulk-cat whole directories."),
            evidence=[Evidence(rp, 0, txt) for rp, txt in
                      [(u.split(" (")[0], u) for u in unreferenced[:8]]],
            auto_fixable=False,
        ))
    return findings


def rule_sd005(ctx: RepoCtx) -> List[Finding]:
    orch: List[Evidence] = []
    multi: List[Evidence] = []
    boundary: List[Evidence] = []
    longlived: List[Evidence] = []
    transcript: List[Evidence] = []
    for p in ctx.scan_files:
        text = ctx.texts.get(p, "")
        for i, line in enumerate(text.splitlines(), 1):
            if ORCH_RE.search(line):
                orch.append(Evidence(rel(ctx.root, p), i, line.strip()[:140]))
            if MULTI_TASK_RE.search(line):
                multi.append(Evidence(rel(ctx.root, p), i, line.strip()[:140]))
            if BOUNDARY_RE.search(line):
                boundary.append(Evidence(rel(ctx.root, p), i, line.strip()[:140]))
            if LONG_LIVED_RE.search(line):
                longlived.append(Evidence(rel(ctx.root, p), i, line.strip()[:140]))
            if TRANSCRIPT_RE.search(line):
                transcript.append(Evidence(rel(ctx.root, p), i, line.strip()[:140]))

    if not orch and not multi:
        return []

    if boundary:
        if not longlived:
            return []
        return [Finding(
            rule_id="SD005",
            title="Long-lived main session explicitly allowed",
            severity="medium",
            confidence="high",
            why=("Session boundaries exist, but the rules also explicitly allow one session to persist across "
                 "tickets. Combined with dispatch-style work, worker outputs accumulate in the parent context "
                 "across unrelated tasks."),
            recommendation=("Require a fresh session per coherent working set (or at least per ticket); the "
                            "coordinator should collect only small receipts, never transcripts or full diffs."),
            evidence=(longlived + orch)[:8],
            auto_fixable=bool((ctx.root / "AGENTS.md").is_file()),
        )]

    severity = "high" if longlived else "medium"
    title = "Long-lived session without working-set boundary" if longlived else "No one-task-per-session boundary"
    evidence = (longlived + orch + multi)[:4] + transcript[:4]
    return [Finding(
        rule_id="SD005",
        title=title,
        severity=severity,
        confidence="medium",
        why=("The project runs multi-task flows but no rule bounds a session to one coherent "
             "working set. Without a stop-after-task rule, each session's working set grows across unrelated "
             "tickets and earlier task outputs replay in the parent context."),
        recommendation=("Add explicit session boundaries: one coherent working set per session; stop when the "
                        "current task is done; independent tasks go to new sessions; coordinators collect only "
                        "small worker receipts (issue/status/pr/tests/blockers), never full transcripts or logs."),
        evidence=evidence[:8],
        auto_fixable=bool((ctx.root / "AGENTS.md").is_file()),
    )]


def rule_sd006(ctx: RepoCtx) -> List[Finding]:
    dense: List[Evidence] = []
    visual_files: List[str] = []
    batch_anywhere = False
    for p in ctx.scan_files:
        text = ctx.texts.get(p, "")
        if BATCH_RE.search(text):
            batch_anywhere = True
        if VISUAL_RE.search(text):
            visual_files.append(rel(ctx.root, p))
        for i, line in enumerate(text.splitlines(), 1):
            for rx, label in DENSE_RES:
                if rx.search(line):
                    dense.append(Evidence(rel(ctx.root, p), i, f"{label}: {line.strip()[:140]}"))
                    break

    if dense:
        severity = "medium" if len(dense) == 1 else "high"
        return [Finding(
            rule_id="SD006",
            title="Dense build/review loop mandates",
            severity=severity,
            confidence="high",
            why=("Rules force verification after every micro change (full rebuilds, per-step captures, "
                 "full-log reads on failure). Each round replays the whole working set again, multiplying "
                 "an already large context."),
            recommendation=("Batch verification: run builds/tests once a set of edits is stable; on failure "
                            "read the relevant error excerpt first; do visual checks when the interface reaches "
                            "a stable state and iterate only on concrete issues. Keep final verification."),
            evidence=dense[:10],
            auto_fixable=bool((ctx.root / "AGENTS.md").is_file()),
        )]

    if visual_files and not batch_anywhere:
        return [Finding(
            rule_id="SD006",
            title="Visual loop has no batching boundary",
            severity="medium",
            confidence="medium",
            why=("The project does visual/UI verification but no rule says when to stop iterating or batch "
                 "checks, so screenshot-review rounds tend to multiply on an already large context."),
            recommendation=("Add a boundary: capture visual checks once the interface is stable; iterate only "
                            "on concrete visual issues; batch builds around stable edit sets."),
            evidence=[Evidence(rp, 0, "visual/UI verification signal") for rp in visual_files[:6]],
            auto_fixable=bool((ctx.root / "AGENTS.md").is_file()),
        )]
    return []


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------


def score(findings: List[Finding]) -> Tuple[float, str]:
    total = sum(SEVERITY_WEIGHT.get(f.severity, 0.0) for f in findings)
    total = min(10.0, round(total, 1))
    if total >= HIGH_RISK:
        level = "high"
    elif total >= MEDIUM_RISK:
        level = "medium"
    else:
        level = "low"
    return total, level


def audit_repo(root: Path, only_rules: Optional[Set[str]] = None) -> AuditResult:
    root = Path(root).resolve()
    if not root.is_dir():
        raise NotADirectoryError(str(root))
    ctx = build_ctx(root)
    edges = build_ref_graph(ctx)
    chains, reachable = mandatory_chains(ctx, edges)

    def want(rid: str) -> bool:
        return only_rules is None or rid in only_rules

    findings: List[Finding] = []
    if want("SD001"):
        findings.extend(rule_sd001(ctx, edges, chains, reachable))
    if want("SD002"):
        findings.extend(rule_sd002(ctx))
    if want("SD003"):
        findings.extend(rule_sd003(ctx))
    if want("SD004"):
        findings.extend(rule_sd004(ctx, reachable))
    if want("SD005"):
        findings.extend(rule_sd005(ctx))
    if want("SD006"):
        findings.extend(rule_sd006(ctx))

    findings.sort(key=lambda f: (
        SEVERITY_ORDER.get(f.severity, 9),
        f.rule_id,
        f.evidence[0].file if f.evidence else "",
    ))
    overall, level = score(findings)
    return AuditResult(
        root=root,
        findings=findings,
        overall=overall,
        level=level,
        files_scanned=len(ctx.scan_files),
        instruction_count=len(ctx.instruction_files),
        large_count=count_large_files(root),
    )


def render_report(res: AuditResult) -> str:
    out: List[str] = []
    out.append(f"Session Docter v{VERSION}")
    out.append("=" * 24)
    out.append(f"Repo: {res.root}")
    out.append(f"Scanned: {res.files_scanned} candidate file(s), {res.instruction_count} instruction file(s)")
    out.append(f"Overall risk: {res.overall} / 10  [{res.level}]")
    out.append("")
    if not res.findings:
        out.append("No context-cost findings.")
        return "\n".join(out) + "\n"
    for f in res.findings:
        out.append(f"{f.severity.upper():6} {f.rule_id}  {f.title}")
        for ev in f.evidence[:8]:
            loc = f"{ev.file}:{ev.line}" if ev.line else f"{ev.file}:"
            out.append(f"       {loc}  {ev.text}")
        if len(f.evidence) > 8:
            out.append(f"       ... {len(f.evidence) - 8} more evidence line(s)")
        out.append(f"       Why: {f.why}")
        out.append(f"       Fix: {f.recommendation}")
        out.append(f"       Auto-fixable: {'yes' if f.auto_fixable else 'no'}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


# ---------------------------------------------------------------------------
# fix mode
# ---------------------------------------------------------------------------

SESSION_BLOCK = """
## Session boundaries
- One session handles one coherent working set; when the current task is done, stop.
- Split independent tasks into separate sessions; do not pick up the next task automatically.
- Coordinators keep worker receipts small (issue, status, pr, tests, blockers) — no full transcripts, diffs, or logs in the parent context.
"""

VERIFY_BLOCK = """
## Verification discipline
- Run builds/tests once a set of edits is stable instead of rebuilding per micro edit.
- On failure, read the relevant error excerpt first; pull full logs only when the excerpt is insufficient.
- Do visual/UI checks when the interface reaches a stable state; continue iterating only on concrete visual issues.
"""

GHLIST_FIELDS_RE = re.compile(r"(?i)(gh\s+(?:issue|pr)\s+list\b[^|\n]*?--json\s+)([A-Za-z0-9_,\t ]+)")
HEAVY_FIELDS_RE = re.compile(r"(?i)\b(?:body|comments|files)\b")

BULK_CAT_LINE_RE = re.compile(r"(?m)^(?P<lead>\s*(?:[-*]\s+)?)cat\s+(?P<glob>\S*\*\S*)\s*$")


def tf_lighten_lists(content: str) -> Tuple[str, int]:
    count = 0

    def sub(m: "re.Match") -> str:
        nonlocal count
        fields = m.group(2)
        if not HEAVY_FIELDS_RE.search(fields):
            return m.group(0)
        toks = [t for t in re.split(r"[,\s]+", fields) if t]
        kept = [t for t in toks if not HEAVY_FIELDS_RE.fullmatch(t)]
        if not kept:
            kept = ["number", "title", "labels", "assignees"]
        count += 1
        return m.group(1) + ",".join(kept)

    return GHLIST_FIELDS_RE.sub(sub, content), count


def tf_mandatory_lines(content: str) -> Tuple[str, int]:
    out: List[str] = []
    changed = 0
    for line in content.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        eol = line[len(body):]
        stripped = body.lstrip()
        if (
            not stripped.startswith("#")
            and MANDATORY_RE.search(body)
            and extract_doc_refs(body)
        ):
            docs = sorted(set(extract_doc_refs(body)))
            pronoun = "it" if len(docs) == 1 else "them"
            if has_cjk(body):
                new = ("\u4ec5\u5f53\u4efb\u52a1\u6d89\u53ca " + ", ".join(docs) +
                       " \u65f6\u6309\u9700\u9605\u8bfb\uff1b\u666e\u901a\u4efb\u52a1\u4ece\u5f53\u524d Issue/\u9700\u6c42\u4e0e\u76f8\u5173\u4ee3\u7801\u5f00\u59cb\u3002")
            else:
                new = ("Read " + ", ".join(docs) +
                       " only when the current task touches " + pronoun +
                       "; ordinary tasks start from the current issue/requirement plus relevant code.")
            out.append(new + eol)
            changed += 1
        else:
            out.append(line)
    return "".join(out), changed


def tf_bulk_cat(content: str) -> Tuple[str, int]:
    count = 0

    def sub(m: "re.Match") -> str:
        nonlocal count
        count += 1
        return (f"{m.group('lead')}ls {m.group('glob')}   "
                f"# then read only the files relevant to the current task")

    return BULK_CAT_LINE_RE.sub(sub, content), count


def build_fix_changes(
    ctx: RepoCtx,
    findings: List[Finding],
    mandatory_reachable: Dict[Path, List[Path]],
) -> Tuple[List[PlannedChange], List[str]]:
    notes: List[str] = []
    rules_present = {f.rule_id for f in findings}
    contents: Dict[Path, str] = dict(ctx.texts)
    changes: List[PlannedChange] = []

    def run_transform(paths: Iterable[Path], rule_id: str, description: str,
                      fn: Callable[[str], Tuple[str, int]]) -> None:
        for p in paths:
            if p.suffix.lower() not in FIXABLE_SUFFIXES:
                continue
            if p not in contents:
                continue
            original = contents[p]
            new, n = fn(original)
            if n and new != original:
                changes.append(PlannedChange(p, rule_id, f"{description} ({n} line(s))", original, new))
                contents[p] = new

    if "SD002" in rules_present:
        run_transform(ctx.scan_files, "SD002",
                      "lighten gh list --json field set (drop full-payload fields)", tf_lighten_lists)
        for p in ctx.scan_files:
            if p.suffix.lower() not in FIXABLE_SUFFIXES:
                text = ctx.texts.get(p, "")
                if any(rx.search(text) for rx, _, _ in SD002_CMD_RULES):
                    notes.append(f"{rel(ctx.root, p)}: heavy list payload fields found; "
                                 f"lighten manually (not an agent-facing Markdown file).")

    # Mandatory-read lines are rewritten whenever they match the pattern class,
    # regardless of whether SD001 produced a finding: the pattern itself is the
    # signal, even when the referenced docs do not resolve inside the repo.
    run_transform(ctx.instruction_files, "SD001",
                  "convert mandatory-read lines into task-conditional routing", tf_mandatory_lines)
    if "SD001" in rules_present:
        targets = list(mandatory_reachable.keys())
        run_transform(targets, "SD001",
                      "convert mandatory-read lines into task-conditional routing", tf_mandatory_lines)

    if "SD004" in rules_present:
        run_transform(ctx.scan_files, "SD004",
                      "replace bulk cat with targeted reading guidance", tf_bulk_cat)

    agents = ctx.root / "AGENTS.md"
    if "SD005" in rules_present and agents.is_file():
        orig = contents.get(agents, read_text(agents))
        if "## Session boundaries" not in orig:
            new = orig.rstrip("\n") + "\n" + SESSION_BLOCK
            changes.append(PlannedChange(agents, "SD005", "add session-boundary rules", orig, new))
            contents[agents] = new

    if "SD006" in rules_present and agents.is_file():
        orig = contents.get(agents, read_text(agents))
        if "## Verification discipline" not in orig:
            new = orig.rstrip("\n") + "\n" + VERIFY_BLOCK
            changes.append(PlannedChange(agents, "SD006", "add verification-discipline rules", orig, new))
            contents[agents] = new

    if "SD003" in rules_present:
        notes.append(
            "Manual proposal: split mutable status/history out of the instruction file into STATUS.md "
            "(keep map, invariants and verify commands in place). See rules/SD003_agents_fixed_tax.md."
        )

    return changes, notes


def change_diff(ch: PlannedChange) -> str:
    relpath = str(ch.path)
    return "\n".join(difflib.unified_diff(
        ch.original.splitlines(),
        ch.modified.splitlines(),
        fromfile="a/" + relpath,
        tofile="b/" + relpath,
        lineterm="",
    ))


def render_fix(changes: List[PlannedChange], notes: List[str], apply_mode: bool) -> str:
    mode = "apply" if apply_mode else "dry-run (no files modified)"
    out: List[str] = []
    out.append(f"Session Docter fix — {mode}")
    out.append("=" * 40)
    if not changes:
        out.append("No high-confidence auto fixes for the current findings.")
    else:
        files = sorted({str(c.path) for c in changes})
        out.append(f"Target files ({len(files)}):")
        for fp in files:
            out.append(f"  - {fp}")
        out.append("")
        out.append(f"Proposed changes ({len(changes)}):")
        for ch in changes:
            out.append("")
            out.append(f"# [{ch.rule_id}] {ch.description}")
            out.append(change_diff(ch))
    if notes:
        out.append("")
        out.append("Manual suggestions (not auto-applied):")
        for n in notes:
            out.append(f"  - {n}")
    if not apply_mode and changes:
        out.append("")
        out.append("Next: review the diff, then re-run with --apply.")
    return "\n".join(out) + "\n"


def apply_fix_changes(changes: List[PlannedChange], root: Path) -> Tuple[int, int]:
    root_s = str(root.resolve())
    applied = 0
    files_touched: Set[str] = set()
    for ch in changes:
        p = ch.path
        if p.suffix.lower() not in FIXABLE_SUFFIXES:
            continue
        try:
            ps = str(p.resolve())
        except OSError:
            continue
        if not (ps == root_s or ps.startswith(root_s + os.sep)):
            continue
        p.write_text(ch.modified, encoding="utf-8")
        applied += 1
        files_touched.add(str(p))
    return applied, len(files_touched)


# ---------------------------------------------------------------------------
# bootstrap mode
# ---------------------------------------------------------------------------

BOOTSTRAP_AGENTS_TEMPLATE = """# AGENTS.md — {name}

## What this is
TODO: one-sentence product description.

## Stack
- Runtime/language: TODO (e.g. Python 3.12 / Node 22)
- Package manager: TODO
- Platforms: TODO (if relevant)

## Map
- `AGENTS.md` — this startup map. Keep it short: no history, no machine state, no milestone logs.
- `docs/PRD.md` — product requirements. Read only the sections a task actually touches.
- `docs/ROADMAP.md` — phases and sequencing. Read for planning/scheduling tasks only.
- `docs/STATUS.md` — current environment, phase, blockers. Replace entries; never append history.
- TODO: main source directory — one line about what lives there.

## Verify
- Build/test: TODO (canonical command)
- Lint/format: TODO (if used)

## Working rules
- Ordinary tasks start from the current issue/requirement plus relevant code — not from a full docs sweep.
- One session handles one coherent working set; when the current task is done, stop.
- Split independent tasks into separate sessions; do not pick up the next task automatically.
- Large files: search / heading / line-range first; read in full only when clearly needed.
- Run builds and visual checks once a set of edits is stable; on failure read the relevant error excerpt first.
"""

BOOTSTRAP_PRD_TEMPLATE = """# PRD — {name}

> Product source of truth. Not default startup context: read only the sections a task touches.
> Only record what is actually known; leave TODO instead of inventing product semantics.

## Problem
TODO

## Users
TODO

## Goals
TODO

## Non-goals
TODO

## Core flows
TODO

## Requirements
TODO

## Acceptance criteria
TODO
"""

BOOTSTRAP_ROADMAP_TEMPLATE = """# Roadmap — {name}

> Current plan only. Completed items stay as one-line pointers (issue/PR/commit); details live there, not here.

## Now
- TODO

## Next
- TODO

## Later
- TODO

## Blocked
- TODO
"""

BOOTSTRAP_STATUS_TEMPLATE = """# Current status — {name}

> Snapshot of the current state. Update/replace entries when status changes; do not append history logs.
> Ordinary tasks do not need this file; read it for continuation, environment, release, phase or blocker questions.

## Environment
TODO

## Current phase
TODO

## Active blockers
- None

## External dependencies
TODO

## Release / deployment state
TODO
"""

HEAVY_DOC_NAMES = {"context.md", "context-map.md", "contextmap.md", "decisions.md"}


def detect_heavy(ctx: RepoCtx) -> Optional[str]:
    for dirpath, dirnames, filenames in os.walk(ctx.root):
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in DEFAULT_EXCLUDE_DIRS
            and (not d.startswith(".") or d in ALLOWED_DOT_DIRS)
        )
        for fn in filenames:
            rp = Path(dirpath) / fn
            low = fn.lower()
            if low in HEAVY_DOC_NAMES:
                return f"existing context system detected ({rel(ctx.root, rp)})"
            relp = rel(ctx.root, rp).lower()
            parts = relp.split("/")
            if len(parts) >= 2 and parts[-2] in {"adr", "adrs", "decisions"} and low.endswith(".md"):
                return f"existing ADR directory ({rel(ctx.root, rp)})"
    agents = ctx.root / "AGENTS.md"
    if agents.is_file() and agents.stat().st_size > 4096:
        return "AGENTS.md is larger than 4 KB — likely an established context system"
    for f in ctx.instruction_files:
        if f.name != "AGENTS.md" and read_text(f).strip():
            return f"existing instruction file ({rel(ctx.root, f)})"
    return None


def plan_bootstrap(ctx: RepoCtx) -> Tuple[Optional[str], List[BootstrapItem]]:
    heavy = detect_heavy(ctx)
    if heavy:
        return heavy, []
    name = ctx.root.name
    templates: Dict[str, str] = {
        "AGENTS.md": BOOTSTRAP_AGENTS_TEMPLATE.format(name=name),
        "docs/PRD.md": BOOTSTRAP_PRD_TEMPLATE.format(name=name),
        "docs/ROADMAP.md": BOOTSTRAP_ROADMAP_TEMPLATE.format(name=name),
        "docs/STATUS.md": BOOTSTRAP_STATUS_TEMPLATE.format(name=name),
    }
    items: List[BootstrapItem] = []
    for relp, tpl in templates.items():
        p = ctx.root / relp
        if p.is_file():
            existing = read_text(p)
            if existing.strip() == tpl.strip():
                items.append(BootstrapItem(relp, "keep", "already matches template", tpl, existing))
            else:
                items.append(BootstrapItem(
                    relp, "conflict",
                    "exists — NOT overwritten; existing content preserved; manual merge review suggested",
                    tpl, existing,
                ))
        else:
            items.append(BootstrapItem(relp, "create", "new file", tpl, ""))
    return None, items


def render_bootstrap(heavy: Optional[str], items: List[BootstrapItem], apply_mode: bool) -> str:
    mode = "apply" if apply_mode else "dry-run (no files written)"
    out: List[str] = []
    out.append(f"Session Docter bootstrap — {mode}")
    out.append("=" * 40)
    if heavy:
        out.append(f"NO BOOTSTRAP NEEDED: {heavy}")
        out.append("Run `audit` instead to diagnose the existing context system, then consider `fix --dry-run`.")
        return "\n".join(out) + "\n"
    for it in items:
        out.append(f"[{it.action:^8}] {it.rel_path} — {it.note}")
    out.append("")
    for it in items:
        if it.action == "create":
            out.append(f"--- new file: {it.rel_path} " + "-" * max(1, 50 - len(it.rel_path)))
            out.append(it.template.rstrip())
            out.append("")
        elif it.action == "conflict":
            out.append(f"--- merge proposal for {it.rel_path} (template vs existing) " + "-" * 10)
            out.append("\n".join(difflib.unified_diff(
                it.existing.splitlines(),
                it.template.splitlines(),
                fromfile="a/" + it.rel_path + " (existing, kept)",
                tofile="b/" + it.rel_path + " (template, for manual merge)",
                lineterm="",
            )))
            out.append("")
    creates = sum(1 for it in items if it.action == "create")
    out.append(f"Plan: {creates} file(s) to create, "
               f"{sum(1 for i in items if i.action == 'keep')} kept, "
               f"{sum(1 for i in items if i.action == 'conflict')} conflict(s) kept as-is.")
    if not apply_mode:
        out.append("Next: run with --apply to create the listed new files.")
    return "\n".join(out) + "\n"


def apply_bootstrap(ctx: RepoCtx, items: List[BootstrapItem]) -> int:
    created = 0
    for it in items:
        if it.action != "create":
            continue
        p = ctx.root / it.rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(it.template, encoding="utf-8")
        created += 1
    return created


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def cmd_audit(args: argparse.Namespace) -> int:
    try:
        res = audit_repo(Path(args.repo), only_rules=parse_rules_arg(args.rules))
    except NotADirectoryError:
        print(f"error: not a directory: {args.repo}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(res.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(render_report(res))
    return 0


def parse_rules_arg(raw: str) -> Optional[Set[str]]:
    raw = (raw or "").strip()
    if not raw:
        return None
    return {tok.strip().upper() for tok in raw.split(",") if tok.strip()}


def cmd_fix(args: argparse.Namespace) -> int:
    apply_mode = bool(args.apply)
    root = Path(args.repo)
    if not root.is_dir():
        print(f"error: not a directory: {args.repo}", file=sys.stderr)
        return 2
    res = audit_repo(root)
    ctx = build_ctx(root)
    edges = build_ref_graph(ctx)
    _, reachable = mandatory_chains(ctx, edges)
    changes, notes = build_fix_changes(ctx, res.findings, reachable)
    if args.json:
        payload = {
            "tool": "session-docter",
            "version": VERSION,
            "mode": "apply" if apply_mode else "dry-run",
            "repo": str(ctx.root),
            "changes": [
                {"file": str(c.path), "rule": c.rule_id, "description": c.description,
                 "applied": False, "diff": change_diff(c)}
                for c in changes
            ],
            "manual_notes": notes,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        if apply_mode:
            applied, nfiles = apply_fix_changes(changes, ctx.root)
            print(f"applied {applied} change(s) across {nfiles} file(s)", file=sys.stderr)
        return 0
    print(render_fix(changes, notes, apply_mode))
    if apply_mode:
        applied, nfiles = apply_fix_changes(changes, ctx.root)
        print(f"Applied {applied} change(s) across {nfiles} file(s).")
        print(f"Re-run audit to verify: python3 scripts/session_docter.py audit {args.repo}")
    return 0


def cmd_bootstrap(args: argparse.Namespace) -> int:
    apply_mode = bool(args.apply)
    root = Path(args.repo)
    if not root.exists():
        if not apply_mode:
            print(f"note: directory does not exist yet: {root} (will be created on --apply)")
        root = root.resolve()
    elif root.is_file():
        print(f"error: not a directory: {args.repo}", file=sys.stderr)
        return 2
    else:
        root = root.resolve()
    if apply_mode and not root.exists():
        root.mkdir(parents=True, exist_ok=True)
    ctx = build_ctx(root)
    heavy, items = plan_bootstrap(ctx)
    if args.json:
        payload = {
            "tool": "session-docter",
            "version": VERSION,
            "mode": "apply" if apply_mode else "dry-run",
            "repo": str(ctx.root),
            "heavy_reason": heavy,
            "items": [
                {"path": it.rel_path, "action": it.action, "note": it.note}
                for it in items
            ],
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(render_bootstrap(heavy, items, apply_mode))
    if heavy:
        return 0
    if apply_mode:
        created = apply_bootstrap(ctx, items)
        print(f"Applied bootstrap: created {created} file(s).")
        res = audit_repo(root)
        print(f"Re-audit: Overall risk {res.overall} / 10 [{res.level}]")
        if res.level != "low":
            print("warning: generated structure did not audit as low risk; review the report above.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="session_docter",
        description="Context-cost doctor for coding-agent repos: audit (read-only), fix (dry-run/apply), bootstrap (new projects).",
    )
    parser.add_argument("--version", action="version", version=f"session-docter {VERSION}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_audit = sub.add_parser("audit", help="read-only context-cost audit")
    p_audit.add_argument("repo", help="path to the target repository")
    p_audit.add_argument("--json", action="store_true", help="emit JSON report")
    p_audit.add_argument("--rules", default="", help="comma-separated rule filter, e.g. SD001,SD002")
    p_audit.set_defaults(func=cmd_audit)

    p_fix = sub.add_parser("fix", help="propose (default) or apply fixes to agent-facing docs")
    p_fix.add_argument("repo", help="path to the target repository")
    g = p_fix.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", help="show the patch plan and diffs (default)")
    g.add_argument("--apply", action="store_true", help="write the proposed changes")
    p_fix.add_argument("--json", action="store_true", help="emit JSON plan")
    p_fix.set_defaults(func=cmd_fix)

    p_boot = sub.add_parser("bootstrap", help="initialize a lightweight doc skeleton for a NEW project")
    p_boot.add_argument("repo", help="path to the (new) repository")
    g2 = p_boot.add_mutually_exclusive_group()
    g2.add_argument("--dry-run", action="store_true", help="show the creation plan (default)")
    g2.add_argument("--apply", action="store_true", help="write the new files, then re-audit")
    p_boot.add_argument("--json", action="store_true", help="emit JSON plan")
    p_boot.set_defaults(func=cmd_bootstrap)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
