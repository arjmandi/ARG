#!/usr/bin/env python3
"""probe_arg_release — the §7 release gate: exemplar scrub + vocabulary lint.

Read-only. Operationalizes docs_arg_design.md §7 ("one gate, two lints") plus a
short release-readiness check, so the discipline is a command rather than a
promise:

  (1) Exemplar scrub — model-facing strings (organ prompts, render templates,
      seeds) are audited for task-specific exemplars. Nothing above the
      environment adapter may name or assume a specific game; one isomorphic
      exemplar voids the generality claim even with zero behavioral echo.

  (2) Vocabulary lint — model-facing strings are linted against the closed
      operational glossary. A mental-state predicate used as a bare mental verb
      (conscious / understands / knows / believes / aware / realizes /
      hallucinates) must be glossary-bound or rewritten to its operational form.

  (3) Release readiness — LICENSE present, README declares it, and no stale
      affiliation string remains on a public surface.

FAIL (exit 1): a known game id on a model-facing surface; the word "conscious"
anywhere in the agent code (the design renamed the organ to Surveyor, switch
ARG_SEARCH); or a missing LICENSE. Everything else prints as a REVIEW item for
author sign-off — the semantic half of both lints is deliberately human-
confirmed, enumerated here with file:line so nothing is left to memory.

Usage: uv run python probe_arg_release.py [--root .]
"""
from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path

# Model-facing surfaces: the strings an LLM organ actually reads.
MODEL_FACING = ("agents/arg/organs.py", "agents/arg/renderer.py", "agents/arg/seeds.py")
# The only file permitted to be game-specific (the generality contract, §7).
ADAPTER = "agents/arg/adapter.py"

KNOWN_GAMES = ("ls20", "tn36", "su15", "cd82", "ft09")
GAME_ID_RE = re.compile(r"\b[a-z]{2}\d{2}\b")
MENTAL_RE = re.compile(
    r"\b(conscious|understand(?:s|ing)?|knows?|believes?|aware|"
    r"realiz(?:e|es|ing)|hallucinat\w*)\b",
    re.IGNORECASE,
)
CONSCIOUS_RE = re.compile(r"conscious", re.IGNORECASE)
STALE_AFFILIATION_RE = re.compile(r"evolution\s*id", re.IGNORECASE)


class Finding:
    def __init__(self, level: str, lint: str, where: str, detail: str) -> None:
        self.level = level      # FAIL | REVIEW
        self.lint = lint        # EXEMPLAR | VOCAB | READINESS
        self.where = where
        self.detail = detail

    def line(self) -> str:
        return f"  [{self.level:6}] {self.lint:9} {self.where}  —  {self.detail}"


def _string_literals(path: Path) -> list[tuple[int, str]]:
    """(lineno, value) for every string constant in a Python file (model-facing
    strings are prompts/templates/seeds, not comments or identifiers)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append((node.lineno, node.value))
    return out


def _snippet(text: str, span: tuple[int, int]) -> str:
    lo = max(0, span[0] - 24)
    hi = min(len(text), span[1] + 24)
    return re.sub(r"\s+", " ", text[lo:hi]).strip()


def scrub_exemplars(root: Path) -> list[Finding]:
    """Model-facing strings must carry no game exemplar; the broader above-adapter
    net is REVIEW (harness defaults like a CLI game are allowed off the surface)."""
    found: list[Finding] = []
    for rel in MODEL_FACING:
        path = root / rel
        for lineno, val in _string_literals(path):
            low = val.lower()
            for g in KNOWN_GAMES:
                if g in low:
                    found.append(Finding(
                        "FAIL", "EXEMPLAR", f"{rel}:{lineno}",
                        f"model-facing string names game '{g}': “{_snippet(val, (low.index(g), low.index(g) + len(g)))}”"))
            for m in GAME_ID_RE.finditer(low):
                if m.group(0) not in KNOWN_GAMES:
                    found.append(Finding(
                        "REVIEW", "EXEMPLAR", f"{rel}:{lineno}",
                        f"looks like a game id '{m.group(0)}' — confirm not an exemplar"))
    # Above-adapter awareness scan (REVIEW only): everything in agents/ except the adapter.
    for path in sorted((root / "agents").rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if rel == ADAPTER or rel in MODEL_FACING:
            continue
        for lineno, val in _string_literals(path):
            low = val.lower()
            for g in KNOWN_GAMES:
                if g in low:
                    found.append(Finding(
                        "REVIEW", "EXEMPLAR", f"{rel}:{lineno}",
                        f"game id '{g}' above the adapter (ok if a harness default, not a model surface)"))
    return found


def lint_vocabulary(root: Path) -> list[Finding]:
    """Mental-state terms on model-facing surfaces must be operational. 'conscious'
    anywhere in the agent code is a FAIL (renamed to Surveyor, §7 amendment 13)."""
    found: list[Finding] = []
    for rel in MODEL_FACING:
        path = root / rel
        for lineno, val in _string_literals(path):
            for m in MENTAL_RE.finditer(val):
                term = m.group(0)
                lvl = "FAIL" if term.lower() == "conscious" else "REVIEW"
                found.append(Finding(
                    lvl, "VOCAB", f"{rel}:{lineno}",
                    f"mental-state term '{term}' on a model surface — glossary-bind or rewrite: “{_snippet(val, m.span())}”"))
    # 'conscious' regression scan across ALL agent code (identifiers + strings + comments).
    for path in sorted((root / "agents").rglob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for i, ln in enumerate(text.splitlines(), 1):
            if CONSCIOUS_RE.search(ln):
                rel = path.relative_to(root).as_posix()
                found.append(Finding(
                    "FAIL", "VOCAB", f"{rel}:{i}",
                    "'conscious' survives in code — the organ is Surveyor (ARG_SEARCH)"))
    return found


def check_readiness(root: Path) -> list[Finding]:
    found: list[Finding] = []
    lic = root / "LICENSE"
    if not lic.exists():
        found.append(Finding("FAIL", "READINESS", "LICENSE", "no LICENSE file — pick one before publishing"))
    else:
        txt = lic.read_text(encoding="utf-8", errors="replace")
        readme = (root / "README.md").read_text(encoding="utf-8", errors="replace")
        if "MIT" in txt and "MIT" not in readme:
            found.append(Finding("REVIEW", "READINESS", "README.md",
                                 "LICENSE is MIT but README does not say so"))
    # No stale affiliation on any public doc.
    for path in sorted(root.glob("docs_arg_*.md")) + [root / "README.md"]:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for i, ln in enumerate(text.splitlines(), 1):
            if STALE_AFFILIATION_RE.search(ln):
                found.append(Finding("REVIEW", "READINESS", f"{path.name}:{i}",
                                     "affiliation string 'Evolution ID' on a public surface — confirm intended"))
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    root = Path(a.root).resolve()

    findings = scrub_exemplars(root) + lint_vocabulary(root) + check_readiness(root)
    fails = [f for f in findings if f.level == "FAIL"]
    reviews = [f for f in findings if f.level == "REVIEW"]

    print(f"§7 release gate over {root}\n")
    for lint in ("EXEMPLAR", "VOCAB", "READINESS"):
        rows = [f for f in findings if f.lint == lint]
        nf = sum(1 for f in rows if f.level == "FAIL")
        print(f"  {lint:9} {len(rows):3d} finding(s), {nf} FAIL")
    print()
    if fails:
        print(f"FAIL — {len(fails)} blocking finding(s):")
        for f in fails:
            print(f.line())
        print()
    if reviews:
        print(f"REVIEW — {len(reviews)} item(s) for author sign-off "
              "(the semantic half of both lints):")
        for f in reviews:
            print(f.line())
        print()
    if fails:
        print("RESULT: FAIL — do not make an external claim until the blocking findings clear.")
        return 1
    print("RESULT: PASS (blocking checks) — clear the REVIEW list by eye before release.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
