#!/usr/bin/env python3
"""Deterministic "atomic value" score for a cloned repo.

Grounds the v2 waitlist score's v_atomic dimension in VERIFIABLE code rather than
an LLM reading a description. A repo that merely *mentions* "RAG" in its README
must not count as implementing it - so we strip comments and string literals
before counting concrete mechanism symbols (defs, classes, function names, and
the code tokens that use them).

  atomic_score.py --repo <cloned-dir> [--db {{ANALYSIS_DB}}] [--project <path>]

Exit 0 always (an empty/non-existent repo is a valid answer, not a failure). Prints
one JSON line: {repo, files_scanned, mechanism_counts, atomic_score, verdict}.
"""

import argparse
import json
import math
import os
import re
import sqlite3
from pathlib import Path

# Comment/string-literal stripping regex (the anti-hallucination core). Match order
# matters: block comments and string literals before line comments so a '#' inside a
# string or block is not misread. Runs once per file against decoded source.
_STRIP_RE = re.compile(
    r'/\*.*?\*/'      # C-style block comment  (non-greedy, DOTALL below)
    r'|"(?:\\.|[^"\\])*"'   # double-quoted string literal
    r"|'(?:\\.|[^'\\])*'"   # single-quoted string literal
    r'|"""[\s\S]*?"""'      # triple-double string literal
    r"|'''[\s\S]*?'''"      # triple-single string literal
    r'|#[^\n]*'             # line comment (# for python/shell, // for c-like below)
    r'|//[^\n]*',           # C-style line comment
    re.DOTALL,
)

# Directories never scanned regardless of position (matches gates.py's set).
IGNORED_DIRS = {
    ".git", "node_modules", "venv", ".venv", "dist", "build", "__pycache__",
    ".tox", ".mypy_cache", ".pytest_cache", "target", ".idea", ".vscode",
}

# Source file extensions we actually count symbols from.
SOURCE_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs",
    ".rs", ".go", ".java", ".kt", ".rb", ".php", ".c", ".h",
    ".cpp", ".hpp", ".cc", ".cxx", ".cs", ".swift", ".scala",
}

# Doc-only directories: scanned but weighted far lower than real source. A README
# naming a mechanism is evidence of intent, not implementation.
DOC_DIRS = {"docs", "examples", "example", "test", "tests", "spec", "benchmark", "benchmarks"}
DOC_WEIGHT = 0.1

# Mechanism keyword families -> the lexicon that maps "real code token" to a
# capability. Tokens are matched case-insensitively as whole words inside the
# stripped source, so `def build_rag_index` hits data/engine while a comment
# mentioning RAG is already removed.
LEXICON = {
    "algorithm": [
        "algorithm", "sort", "search", "graph", "tree", "hash", "index",
        "dynamic_programming", "dp", "greedy", "recursion", "cache", "lru",
        "attention", "transformer",
    ],
    "api/service": [
        "api", "endpoint", "route", "handler", "controller", "middleware",
        "client", "server", "request", "response", "websocket", "grpc",
        "rest", "rpc",
    ],
    "data/engine": [
        "engine", "database", "query", "sql", "vector", "embedding",
        "retrieval", "rag", "knowledge_graph", "ontology",
    ],
    "protocol": [
        "protocol", "frame", "packet", "message", "event", "stream",
        "serialization", "encode", "decode",
    ],
}

MAX_TOTAL_BYTES = 200 * 1024 * 1024  # hard cap on total source scanned (no hangs)
MAX_FILE_BYTES = 2 * 1024 * 1024     # skip a single file larger than this

# Compile whole-word, case-insensitive token patterns once.
_PATTERNS = {
    family: [re.compile(r"\b" + re.escape(tok) + r"\b", re.IGNORECASE) for tok in toks]
    for family, toks in LEXICON.items()
}


def _is_binary(data: bytes) -> bool:
    """NUL byte in the first chunk => treat as binary, never scan."""
    return b"\x00" in data[:4096]


def _strip_code(raw: str) -> str:
    """Return source with comments and string literals removed.

    Only the stripping regex here is non-obvious enough to document inline; the
    rest of this file is plain traversal + counting.
    """
    return _STRIP_RE.sub(" ", raw)


def _count_in_text(text: str) -> dict:
    counts = {f: 0 for f in LEXICON}
    for family, pats in _PATTERNS.items():
        n = 0
        for p in pats:
            n += len(p.findall(text))
        counts[family] = n
    return counts


def scan_repo(repo: str) -> dict:
    """Walk repo, count mechanism tokens in non-comment/string code. Returns
    {files_scanned, mechanism_counts, total_bytes}."""
    counts = {f: 0 for f in LEXICON}
    files_scanned = 0
    total_bytes = 0

    for dirpath, dirnames, filenames in os.walk(repo):
        # Prune ignored dirs in place so os.walk does not descend into them.
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
        # Recurse into doc dirs but remember we are inside one for weighting.
        rel_parts = Path(dirpath).parts
        in_doc = any(d in DOC_DIRS for d in rel_parts)
        weight = DOC_WEIGHT if in_doc else 1.0

        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in SOURCE_EXTS:
                continue
            fp = os.path.join(dirpath, fn)
            try:
                st = os.stat(fp)
            except OSError:
                continue
            if not st.st_size or st.st_size > MAX_FILE_BYTES:
                continue
            if total_bytes + st.st_size > MAX_TOTAL_BYTES:
                continue
            try:
                data = open(fp, "rb").read()
            except OSError:
                continue
            if _is_binary(data):
                continue
            total_bytes += len(data)
            try:
                text = data.decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001 - any decode issue -> skip file
                continue
            text = _strip_code(text)
            file_counts = _count_in_text(text)
            for fam in counts:
                counts[fam] += int(file_counts[fam] * weight)
            files_scanned += 1

    return {"files_scanned": files_scanned, "mechanism_counts": counts,
            "total_bytes": total_bytes}


def _atomic_score(counts: dict, files_scanned: int) -> float:
    """0..1 normalized score. Log10 scaling so a few hundred hits saturate toward
    1 while a near-zero-code link collection lands ~0."""
    total = sum(counts.values())
    if total <= 0 or files_scanned <= 0:
        return 0.0
    # log10(1+total)/log10(1+MAX) -- MAX chosen so a real library (thousands of
    # hits) maps well above the 0.3 "is real code" bar without needing to tune.
    max_hits = 20000
    return min(1.0, math.log10(1 + total) / math.log10(1 + max_hits))


def _verdict(score: float, files_scanned: int, counts: dict) -> str:
    if files_scanned == 0:
        return "no_source"
    total = sum(counts.values())
    if total == 0:
        return "no_mechanism_tokens"
    if score < 0.3:
        return "thin"
    return "substantive"


def update_db(db: str, project: str, score: float) -> None:
    """UPDATE analysis_index SET v_atomic=<score> WHERE project_path=<project>.
    Single-row; if no row matches, do nothing (never insert)."""
    if not db or not project:
        return
    conn = sqlite3.connect(db, timeout=10)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("PRAGMA busy_timeout=10000")
        cur = conn.execute(
            "UPDATE analysis_index SET v_atomic=? WHERE project_path=?",
            (score, project),
        )
        conn.commit()
        if cur.rowcount == 0:
            pass  # no matching row -> deliberately no-op, no insert
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="deterministic atomic-value score of a cloned repo")
    parser.add_argument("--repo", required=True, help="absolute path to cloned repo (or any source dir)")
    parser.add_argument("--db", help="path to analysis.db (default: {{ANALYSIS_DB}})")
    parser.add_argument("--project", help="project_path value to UPDATE v_atomic for (requires --db)")
    args = parser.parse_args()

    repo = os.path.abspath(args.repo)
    if not os.path.isdir(repo):
        # Empty/non-existent repo is a valid answer, not a failure.
        print(json.dumps({
            "repo": repo, "files_scanned": 0,
            "mechanism_counts": {f: 0 for f in LEXICON},
            "atomic_score": 0.0, "verdict": "no_source",
        }))
        return 0

    res = scan_repo(repo)
    score = _atomic_score(res["mechanism_counts"], res["files_scanned"])
    verdict = _verdict(score, res["files_scanned"], res["mechanism_counts"])

    if args.db and args.project:
        update_db(os.path.expanduser(args.db), args.project, score)

    print(json.dumps({
        "repo": repo,
        "files_scanned": res["files_scanned"],
        "mechanism_counts": res["mechanism_counts"],
        "atomic_score": round(score, 4),
        "verdict": verdict,
    }))
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())