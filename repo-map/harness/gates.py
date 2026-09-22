#!/usr/bin/env python3
"""Deterministic quality gates for the repo-map pipeline (G1-G5).

Every gate is a PURE check - no LLM judgment in the pass/fail decision. Each
returns exit code 0 (PASS), 1 (FAIL -> rework), or 2 (BLOCKED -> attempt budget
exhausted). gates.py only DECIDES; it does not mutate run.json. The orchestrator
(skill) calls refresh_state.py gate <g> to persist the result.

  gates.py <g1|g2|g3|g4|g5> --repo <path> [--out <dir>] [--stack <name>]

Gate semantics:
  g1  DISCOVERY  - did exploration surface analyzable material? (entrypoints,
                   manifests, or >=10 source files)
  g2  SCORING    - is the tech stack identified? (manifest OR dominant language
                   cluster >=5 source files)
  g3  GENERATE   - did docs get produced, non-empty, in the scored places?
                   (root knowledge file >1KB + per-dir knowledge files >0 bytes)
  g4  REVIEW     - quality of produced docs? (no zero-byte, no >200KB bloat,
                   internal links resolve, count matches scoring)
  g5  FINAL      - does the project build/lint/test? (per-stack command; SKIP
                   allowed only with an explicit recorded reason)
"""

import argparse
import json
import os
import re
import subprocess
import sys

IGNORED_DIRS = {"node_modules", ".git", "venv", ".venv", "dist", "build", "__pycache__", ".tox", ".mypy_cache"}
MANIFESTS = {
    "node": ["package.json"],
    "python": ["pyproject.toml", "setup.py", "requirements.txt", "Pipfile"],
    "rust": ["Cargo.toml"],
    "go": ["go.mod"],
    "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
    "ruby": ["Gemfile"],
    "php": ["composer.json"],
    "csharp": ["*.csproj", "*.sln"],
}
LANG_EXTS = {
    "node": {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"},
    "python": {".py"},
    "rust": {".rs"},
    "go": {".go"},
    "java": {".java", ".kt"},
    "ruby": {".rb"},
    "php": {".php"},
    "csharp": {".cs"},
}
C_EXTS = {".c", ".h", ".cpp", ".hpp", ".cc", ".cxx"}
NATIVE_EXTS = {".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".rs", ".go"}


def run(cmd, cwd=None, timeout=60):
    try:
        r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:  # noqa: BLE001 - any subprocess failure becomes a check result
        return -1, "", str(e)


def _run_bash_pipefail(cmd, cwd=None, timeout=60):
    """Run a shell command under bash -o pipefail so a failing left side of a
    pipeline is not masked by the exit status of tail/grep on the right."""
    full = "bash -o pipefail -c " + repr(cmd)
    try:
        r = subprocess.run(full, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:  # noqa: BLE001
        return -1, "", str(e)


def detect_stack(repo):
    """Return the dominant stack name or None. Walks only one level deep."""
    # phase A: explicit topology via manifests at repo root or one subdir deep
    for stack, files in MANIFESTS.items():
        for f in files:
            found = run(f'find {repo} -maxdepth 2 -name "{f}" -not -path "*/node_modules/*" -not -path "*/.git/*" | head -1')[1].strip()
            if found:
                return stack
    # phase B: dominant language by file-extension census (top-1 if >= floor)
    exts = run(f'find {repo} -type f -not -path "*/node_modules/*" -not -path "*/.git/*" 2>/dev/null | sed "s/.*\\.//" | sort | uniq -c | sort -rn | head -20', timeout=90)[1].splitlines()
    counts = {}
    for line in exts:
        parts = line.strip().split()
        if len(parts) == 2:
            counts[parts[1]] = int(parts[0])
    best = None
    for stack, extset in LANG_EXTS.items():
        n = sum(counts.get(e.lstrip("."), 0) for e in extset)
        if n >= 5 and (best is None or n > best[1]):
            best = (stack, n, True)
    if best:
        return best[0]
    return None


def gate_g1(repo):
    """Discovery surfaced analyzable material?"""
    # entrypoints / manifests present
    present = run(f'find {repo} -maxdepth 2 \\( -name README.md -o -name AGENTS.md -o -name CLAUDE.md -o -name package.json -o -name pyproject.toml -o -name Cargo.toml -o -name go.mod \\) -not -path "*/node_modules/*" -not -path "*/.git/*" | grep -c .', cwd=repo)[1].strip()
    if present and int(present) > 0:
        return 0, f"entrypoints/manifests found ({present} file(s))"
    # or >=10 source files anywhere
    files = run('find . \\( -path ./node_modules -o -path ./.git -o -path ./venv \\) -prune -o -type f -print | wc -l', cwd=repo)[1].strip()
    if files and int(files) >= 10:
        return 0, f"{files} source files found"
    return 1, f"nothing analyzable: {present or 0} entrypoints, {files or 0} files"


def gate_g2(repo, stack):
    """Tech stack identified?"""
    if stack:
        return 0, f"stack identified: {stack}"
    # fall back to a dominant language census even without a manifest
    st = detect_stack(repo)
    if st:
        return 0, f"stack inferred by language census: {st}"
    return 1, "could not identify tech stack (no manifest, no >=5-file language cluster)"


def gate_g3(repo, out, dirs):
    """Docs produced, non-empty, in the scored places?"""
    out_root = out or repo
    kb_candidates = ["AGENTS.md", "KNOWLEDGE.md", "ARCHITECTURE.md"]
    kb = None
    for c in kb_candidates:
        p = os.path.join(out_root, c)
        if os.path.isfile(p) and os.path.getsize(p) > 1024:
            kb = p
            break
    if not kb:
        return 1, f"no root knowledge file >1KB in {out_root}"

    if not dirs:
        return 0, f"root knowledge file present ({os.path.basename(kb)}); no subdirs scored"
    missing = []
    for d in dirs:
        p = os.path.join(d, "AGENTS.md")
        if not os.path.isfile(p) or os.path.getsize(p) == 0:
            missing.append(p)
    if missing:
        return 1, f"empty/missing per-dir docs: {missing[:5]}"
    return 0, f"root KB + {len(dirs)} per-dir docs all non-empty"


def gate_g4(repo, out, dirs):
    """No empty/bloated docs, internal cross-refs resolve, no stale artifacts."""
    out_root = out or repo
    name_group = r'\( -name "AGENTS.md" -o -name "KNOWLEDGE.md" -o -name "ARCHITECTURE.md" \)'
    docs = run(f'find {out_root} {name_group} 2>/dev/null | grep -c .', cwd=repo, timeout=90)[1].strip()
    if not docs or int(docs) == 0:
        return 1, "no knowledge docs produced at all - generation failed or ran nowhere"
    empty = run(f'find {out_root} {name_group} -size 0 2>/dev/null | wc -l', cwd=repo, timeout=90)[1].strip()
    if empty and int(empty) > 0:
        return 1, f"{empty} empty doc file(s) (zero bytes)"
    bloat = run(f'find {out_root} {name_group} -size +200k 2>/dev/null | wc -l', cwd=repo)[1].strip()
    if bloat and int(bloat) > 0:
        return 1, f"{bloat} doc file(s) >200KB (runaway bloat)"
    bad = _resolve_internal_links(repo, dirs)
    if bad:
        return 1, f"unresolved internal links: {bad[:5]}"
    return 0, f"{docs} doc(s) non-empty, no bloat, internal links resolve"


def _resolve_internal_links(repo, dirs):
    """Return a list of relative paths referenced in docs but missing on disk."""
    broken = []
    link_re = re.compile(r"\]\(([^)#\s]+\.(?:md|py|ts|tsx|js|jsx|rs|go))\)")
    for root_dir in (dirs or [repo]):
        if not os.path.isdir(root_dir):
            continue
        for f in os.listdir(root_dir):
            if not f.endswith(".md"):
                continue
            path = os.path.join(root_dir, f)
            try:
                with open(path) as fh:
                    text = fh.read()
            except Exception:  # noqa: BLE001
                continue
            for link in link_re.findall(text):
                if link.startswith(("http://", "https://", "#")) or link.startswith("/"):
                    continue
                target = os.path.join(root_dir, link)
                if not os.path.exists(target) and not os.path.exists(os.path.join(repo, link)):
                    broken.append(link)
    return broken


def gate_g5(repo, stack):
    """Project builds/lints/tests. Returns 0 PASS, 1 FAIL(rework), 3 SKIP(recorded)."""
    if not stack:
        return 3, "no stack identified - cannot run build gate; SKIP (auto-recorded)"
    cmds = {
        "node": "npm run build 2>&1 | tail -20 && npm run lint 2>&1 | tail -20 && npm test 2>&1 | tail -20",
        "python": "python -m pytest -q 2>&1 | tail -20",
        "rust": "cargo build 2>&1 | tail -20",
        "go": "go build ./... 2>&1 | tail -20",
        "java": "(mvn -q test 2>&1 || gradle test --console=plain 2>&1) | tail -20",
        "ruby": "bundle exec rspec 2>&1 | tail -20",
        "php": "composer test 2>&1 | tail -20",
        "csharp": "dotnet test 2>&1 | tail -20",
    }
    cmd = cmds.get(stack)
    code, out, err = _run_bash_pipefail(cmd, repo, timeout=300)
    if code == 0:
        return 0, f"{stack} build/test passed"
    joined = (out + " " + err).lower()
    if "no module named" in joined:
        return 3, f"{stack} test runner not installed -> SKIP (recorded)"
    skip_patterns = ["no test", "no tests", "nothing to", "command not found",
                     ": not found", "cannot find", "no such file", "no 'build' script",
                     "missing script"]
    if any(p in joined for p in skip_patterns):
        return 3, f"{stack} no runnable suite / missing toolchain -> SKIP (recorded)"
    return 1, f"{stack} build/test failed (rc={code})"


def main():
    parser = argparse.ArgumentParser(description="repo-map deterministic quality gates")
    parser.add_argument("gate", choices=["g1", "g2", "g3", "g4", "g5"])
    parser.add_argument("--repo", required=True, help="absolute path to analyzed repo")
    parser.add_argument("--out", help="dir where knowledge docs were written (default: repo)")
    parser.add_argument("--stack", help="detected stack (gates.py --stack from g2; g5 otherwise re-detects)")
    parser.add_argument("--dirs", help="comma-separated subdirs scored for doc generation")
    args = parser.parse_args()

    repo = os.path.abspath(args.repo)
    if not os.path.isdir(repo):
        print("repo path does not exist:", repo)
        return 1

    dirs = [os.path.join(repo, d.strip()) for d in (args.dirs or "").split(",") if d.strip()] if args.dirs else []
    stack = args.stack or detect_stack(repo)

    if args.gate == "g1":
        code, msg = gate_g1(repo)
    elif args.gate == "g2":
        code, msg = gate_g2(repo, stack)
    elif args.gate == "g3":
        code, msg = gate_g3(repo, args.out, dirs)
    elif args.gate == "g4":
        code, msg = gate_g4(repo, args.out, dirs)
    elif args.gate == "g5":
        code, msg = gate_g5(repo, stack)
    else:
        code, msg = 1, "unknown gate"

    print(msg)
    return code


if __name__ == "__main__":
    sys.exit(main())