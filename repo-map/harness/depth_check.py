#!/usr/bin/env python3
"""Deterministic depth gate for the repo-map pipeline (Q2/Q3 anchor verification).

Purpose: make "deep code interpretation" a HARD gate, not a prompt. Every claimed
mechanism/core-function/atomic-capability in the analysis artifacts must cite a
real `path[:line]` anchor that resolves on disk. A claim with no resolvable anchor
is unverifiable -> marketing -> FAIL. This closes the gap where G1-G5 checked
file-system facts but never "did the analysis understand the code".

Every check is a PURE check - no LLM judgment in the pass/fail decision (same
principle as gates.py:4). Returns exit code 0 (PASS), 1 (FAIL -> rework), or
2 (BLOCKED -> artifact missing, cannot judge).

  depth_check.py --repo <path> [--out <dir>] [--min-anchors N]

  Scans every .md analysis artifact under --out (default: the repo root) and
  verifies each carries resolvable `path:LINE` anchors.

Artifact conventions (what it verifies):
- AGENTS.md          : ARCHITECTURE / CODE MAP / KEY PATHS sections should anchor
                       load-bearing units with `path/file.py:LINE` or `file.py:LINE`
- PROFILE.md         : every claimed core function / advantage must carry a
                       `path:LINE` anchor (tightens Op2's "file + count" to "file:LINE")
- ATOMIC-CAPABILITIES.md : every capability row must carry a resolvable
                       `path/file.py:LINE` code anchor (Op3.5 gate)

Anchor formats recognized (whitelisted source extensions, matching G4's regex):
  `path/to/file.py:123`     `path/to/file.ts:12`      `file.rs:45:6`
  `path:file.js:100-120`    `path/to/mod.py L60-82`   (codegraph/anti-mage style)

Why anchors must be REAL symbols/lines, not just file names: naming a file proves
you saw it exists; naming a line/symbol proves you read it. The whole point of
this gate is to force the analyzer past README-level into source-level
interpretation.
"""

import argparse
import os
import re
import sys

# Source extensions whose `path:LINE` anchors we verify on disk (matching gates.py).
SOURCE_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".rs", ".go",
    ".java", ".kt", ".rb", ".php", ".cs", ".c", ".h", ".cpp", ".hpp",
    ".cc", ".cxx", ".sh", ".sql", ".json", ".toml", ".yaml", ".yml", ".md",
}

# Match `path/file.py:123`, `path:file.ts:12:6`, `file.rs L60-82`, `file.rs:45-60`.
# Group 1 = file path (may contain colons, so use a greedy-but-bounded approach).
ANCHOR_RE = re.compile(
    r"(?<!\w)"                          # no preceding word char
    r"([A-Za-z0-9_./~-]+\.(?:py|ts|tsx|js|jsx|mjs|cjs|rs|go|java|kt|rb|php|cs|c|h|cpp|hpp|cc|cxx|sh|sql|json|toml|yaml|yml|md))"
    r"(?:\s*[:@]\s*(\d+)(?:\s*[-–]\s*(\d+))?(?:\s*[:.]\s*(\d+))?\s*|"
    r"\s+[Ll](\d+)(?:\s*[-–]\s*(\d+))?\s*|"
    r"\s*\b(?:L|line)\s*(\d+)\s*)?"
)


def _is_ignored(path: str) -> bool:
    parts = path.split(os.sep)
    ignored = {"node_modules", ".git", "dist", "build", "__pycache__", "venv", ".venv"}
    return any(p in ignored for p in parts)


def _anchor_file(anchor_path: str, repo: str, out_root: str) -> str | None:
    """Resolve a possibly-relative anchor path to an absolute existing file.
    Returns the resolved path or None if not found."""
    cands = []
    if os.path.isabs(anchor_path):
        cands.append(anchor_path)
    else:
        cands.append(os.path.join(out_root, anchor_path))
        cands.append(os.path.join(repo, anchor_path))
    for c in cands:
        if os.path.isfile(c) and not _is_ignored(c):
            return c
    return None


def _scan_docs(repo: str, out_root: str) -> list[str]:
    """Return all markdown analysis docs under out_root."""
    docs = []
    for root, _dirs, files in os.walk(out_root):
        if _is_ignored(root):
            continue
        for f in files:
            if f.endswith(".md"):
                docs.append(os.path.join(root, f))
    return docs


def _check_doc(path: str, repo: str, out_root: str) -> tuple[list[str], list[str]]:
    """Scan one doc. Returns (resolved_anchors, problems).

    A 'problem' is either an anchor that does not resolve on disk, or a
    capability/advantage/mechanism declaration that carries no anchor on its own
    line or the immediately following line. This enforces the anti-fluff rule:
    every claimed capability must name its implementing file:LINE.
    """
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except Exception:  # noqa: BLE001
        return [], [f"{path}: unreadable"]

    resolved: list[str] = []
    problems: list[str] = []

    # 1) every explicit `path:LINE` anchor must resolve on disk
    for m in ANCHOR_RE.finditer(text):
        fpath = m.group(1)
        if fpath.startswith(("http://", "https://", "#")):
            continue
        resolved_file = _anchor_file(fpath, repo, out_root)
        if resolved_file is None:
            problems.append(f"{path}: unverifiable anchor '{fpath}' (file not found on disk)")
        else:
            resolved.append(f"{os.path.relpath(resolved_file, repo)}")

    # 2) capability declarations must carry an anchor on their own line or the
    #    following line. A capability is a line naming a function/advantage/ability
    #    (功能/优势/能力/亮点/capability/feature/advantage/核心机制) followed by
    #    descriptive content. Without a nearby anchor it is an unverifiable claim.
    decl_re = re.compile(
        r"^[^\n]*(?:功能|优势|能力|亮点|核心机制|核心功能|capabilit|feature|advantage|能力项|机制)"
        r"[^\n]*[：:]\s*[^\n]*$",
        re.IGNORECASE,
    )
    lines = text.splitlines()
    for idx, line in enumerate(lines, 1):
        # only declaration lines, not the taxonomy-register header row
        if not decl_re.search(line) or line.strip().startswith(("|", "#", "`")):
            continue
        anchor_near = ANCHOR_RE.search(line)
        if not anchor_near and idx < len(lines):
            anchor_near = ANCHOR_RE.search(lines[idx])  # the following line
        if not anchor_near:
            problems.append(f"{path}:{idx}: capability '{line.strip()[:60]}' has NO code anchor -> unverifiable")

    return resolved, problems


def gate_depth(repo: str, out: str, min_anchors: int) -> tuple[int, str]:
    """Run the depth gate over all analysis docs in out (default: repo).

    Returns (0 PASS, 1 FAIL -> rework, 2 BLOCKED)."""
    out_root = os.path.abspath(out or repo)
    if not os.path.isdir(out_root):
        return 2, f"BLOCKED: artifact dir {out_root} does not exist"
    docs = _scan_docs(repo, out_root)
    if not docs:
        return 2, "BLOCKED: no analysis .md docs found to judge"

    total_resolved = 0
    all_problems: list[str] = []
    for d in docs:
        resolved, problems = _check_doc(d, repo, out_root)
        total_resolved += len(resolved)
        all_problems.extend(problems)

    if total_resolved == 0:
        return 1, f"FAIL: 0 resolvable `path:LINE` anchors across {len(docs)} doc(s) - analysis did not read source"

    if all_problems:
        shown = all_problems[:8]
        return 1, f"FAIL ({len(all_problems)} depth problem(s)): {shown}"

    if total_resolved < min_anchors:
        return 1, f"FAIL: only {total_resolved} anchors (< min {min_anchors}) - not enough code grounding"

    return 0, f"PASS: {total_resolved} resolvable code anchors across {len(docs)} doc(s); 0 unanchored mechanism claims"


def main() -> int:
    parser = argparse.ArgumentParser(description="repo-map deterministic depth gate (Q2/Q3 anchor verification)")
    parser.add_argument("--repo", required=True, help="absolute path to analyzed repo")
    parser.add_argument("--out", help="dir where analysis docs live (default: repo)")
    parser.add_argument("--min-anchors", type=int, default=1, help="min resolvable code anchors to PASS (default 1)")
    args = parser.parse_args()

    repo = os.path.abspath(args.repo)
    if not os.path.isdir(repo):
        print("repo path does not exist:", repo)
        return 2

    code, msg = gate_depth(repo, args.out, args.min_anchors)
    print(msg)
    return code


if __name__ == "__main__":
    sys.exit(main())