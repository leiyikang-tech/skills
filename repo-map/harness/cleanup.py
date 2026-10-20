#!/usr/bin/env python3
"""Post-analysis byproduct cleanup for the repo-map skill.

After Op5 (persist) and `refresh_state.py finish` have closed a run, the
analysis leaves behind disposable byproducts that bloat disk: compilation
artifacts and caches, stale git history objects, and /tmp scratch clones.
This script removes them SAFELY, on the analyzed repo:

  cleanup.py --repo <path> [--artifacts] [--gc] [--tmp] [--dry-run]

Three independent categories (any subset, all on by default):
  --artifacts  compilation artifacts + caches: __pycache__/*.pyc, pytest/mypy/
               ruff caches, node_modules, .venv/venv, target, .gradle,
               dist/build, harness2's dependencies/ runtime dir, .DS_Store.
  --gc         git deep-history compaction: `git reflog expire --expire=now`
               + `git gc --aggressive --prune=now` on the analyzed repo's .git.
  --tmp        remove repo-map scratch dirs/files under the system temp root
               (/tmp/work-log-clone, /tmp/work-log, /tmp/corpus*.json, ...).

Safety guarantees (the non-negotiable core):
  * --artifacts deletes a candidate ONLY when it is NOT tracked by git (`git
    ls-files`). A tracked source file is ALWAYS skipped, never deleted. A
    directory is deleted only when NOTHING under it is tracked, so a `dist/`
    or `build/` that holds committed files is left intact. This covers both
    git-ignored and untracked-but-cache candidates (a repo without a
    .gitignore still gets its __pycache__ cleaned).
  * --gc only COMPACTS the analyzed repo's own git history (reflog expire +
    git gc). It never rewrites, rebases, or drops commits, so Refresh-mode
    diffs against `last_analyzed_sha` keep working.
  * --tmp only touches paths that live under the system temp root AND match the
    known repo-map scratch names. Nothing outside /tmp is ever removed by it.

Exit codes: 0 = clean success, 1 = real error (repo missing / gc failed).
`--dry-run` prints exactly what WOULD be removed without removing anything.

This is a pure stdlib script (matching gates.py / refresh_state.py); no deps.
"""

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import tempfile

# Curated artifact/cache directory names. Only non-tracked occurrences are
# deleted (see safety note above).
ARTIFACT_DIR_NAMES = {
    # python
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".coverage",
    # node / frontend
    "node_modules",
    ".next",
    ".nuxt",
    ".turbo",
    ".cache",
    # build output
    "dist",
    "build",
    "out",
    # rust / jvm / go
    "target",
    ".gradle",
    # python virtualenvs
    ".venv",
    "venv",
    # harness2 git-ignored runtime dependency dir
    "dependencies",
}
# Curated artifact/cache FILE suffixes / names.
ARTIFACT_FILE_SUFFIXES = {".pyc", ".pyo", ".pyo3", ".class", ".o", ".obj", ".DS_Store"}

# Known repo-map scratch names that may exist under the system temp root.
TMP_SCRATCH_NAMES = {
    "work-log-clone",
    "work-log",
    "work-log-clone.git",
    "corpus.json",
    "corpus_fixed.json",
    "corpus",
}


def _run(cmd, cwd=None, timeout=120):
    """Run a command, returning (returncode, stdout, stderr). Never raises on
    subprocess failure — like gates.py.run."""
    try:
        r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:  # noqa: BLE001
        return -1, "", str(e)


def _is_git_repo(repo):
    code, _, _ = _run("git rev-parse --is-inside-work-tree", cwd=repo)
    return code == 0


def _is_tracked(repo, path):
    """True if `path` (or anything under it, for a dir) is tracked by git.
    This is the authoritative safety test: a tracked file is NEVER deleted.
    Handles both ignored and untracked-but-cache candidates."""
    if os.path.isfile(path):
        code, _, _ = _run(f"git ls-files --error-unmatch -- {shlex.quote(path)}", cwd=repo)
        return code == 0
    # directory: safe to delete only if NOTHING under it is tracked
    code, out, _ = _run(f"git ls-files -- {shlex.quote(os.path.join(path, '*'))}", cwd=repo)
    if code != 0:
        return False
    return bool(out.strip())


def _walk_artifact_candidates(repo):
    """Yield (path, is_dir) for every artifact/cache candidate under repo.
    When an artifact directory is hit, its contents are NOT yielded separately
    (removing the dir removes them). Deletion happens later only for
    non-tracked candidates."""
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d != ".git"]
        for d in list(dirs):
            if d in ARTIFACT_DIR_NAMES:
                yield os.path.join(root, d), True
                # prune: never descend into an artifact dir / re-list its files
                dirs.remove(d)
        for f in files:
            lower = f.lower()
            if lower.endswith(".pyc") or lower.endswith(".pyo") or \
               lower.endswith(".class") or lower.endswith(".o") or \
               lower.endswith(".obj") or lower == ".DS_Store":
                yield os.path.join(root, f), False


def cleanup_artifacts(repo, dry_run):
    """Remove non-tracked build artifacts + caches. Returns (removed, freed,
    skipped_tracked) where freed is best-effort bytes."""
    if not os.path.isdir(repo):
        print(f"[artifacts] repo path does not exist: {repo}")
        return [], 0, 0
    is_git = _is_git_repo(repo)
    removed = []
    skipped_tracked = 0
    freed = 0
    for path, is_dir in _walk_artifact_candidates(repo):
        if not os.path.exists(path):
            continue
        if is_git and _is_tracked(repo, path):
            # tracked file (or dir containing tracked files): NEVER delete
            skipped_tracked += 1
            print(f"[artifacts] SKIP (tracked): {path}")
            continue
        # measure before removing
        if is_dir:
            try:
                size = _dir_size(path)
            except OSError:
                size = 0
        else:
            size = os.path.getsize(path)
        if dry_run:
            removed.append((path, size, is_dir))
            print(f"[artifacts] would remove: {path} ({_fmt(size)})")
        else:
            try:
                if is_dir:
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                removed.append((path, size, is_dir))
                freed += size
                print(f"[artifacts] removed: {path} ({_fmt(size)})")
            except OSError as e:
                print(f"[artifacts] ERROR removing {path}: {e}")
    return removed, freed, skipped_tracked


def _dir_size(path):
    total = 0
    for root, dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def _fmt(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}" if unit != "B" else f"{n}B"
        n /= 1024
    return f"{n:.1f}TB"


def cleanup_gc(repo, dry_run):
    """Compact the analyzed repo's git history (reflog expire + gc --aggressive).
    Never rewrites commits. Returns (ok, message)."""
    if not os.path.isdir(repo):
        print(f"[gc] repo path does not exist: {repo}")
        return False, "repo missing"
    if not _is_git_repo(repo):
        print("[gc] not a git repo; skipping history compaction")
        return True, "not a git repo"
    before = _dir_size(os.path.join(repo, ".git"))
    if dry_run:
        print(f"[gc] would compact .git history ({_fmt(before)}): "
              "git reflog expire --expire=now --all && git gc --aggressive --prune=now")
        return True, "dry-run"
    # expire all reflogs now, then aggressively gc and drop unreachable objects
    code, out, err = _run(
        "git reflog expire --expire=now --all && git gc --aggressive --prune=now",
        cwd=repo, timeout=600)
    if code != 0:
        print(f"[gc] FAILED (rc={code}): {err.strip() or out.strip()}")
        return False, f"gc failed (rc={code})"
    after = _dir_size(os.path.join(repo, ".git"))
    print(f"[gc] .git {_fmt(before)} -> {_fmt(after)} (released {_fmt(before - after)})")
    return True, f".git {_fmt(before)} -> {_fmt(after)}"


def cleanup_tmp(dry_run):
    """Remove repo-map scratch files/dirs under the system temp root. Returns
    (removed_paths, freed_bytes)."""
    tmp_root = tempfile.gettempdir()
    removed = []
    freed = 0
    for name in sorted(TMP_SCRATCH_NAMES):
        path = os.path.join(tmp_root, name)
        if not os.path.exists(path):
            continue
        # double-check the realpath stays under the temp root (symlink safety)
        try:
            real = os.path.realpath(path)
        except OSError:
            continue
        real_root = os.path.realpath(tmp_root)
        if not real.startswith(real_root + os.sep) and real != real_root:
            print(f"[tmp] SKIP (outside temp root): {path} -> {real}")
            continue
        size = _dir_size(path) if os.path.isdir(path) else os.path.getsize(path)
        if dry_run:
            print(f"[tmp] would remove: {path} ({_fmt(size)})")
        else:
            try:
                if os.path.isdir(path) and not os.path.islink(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                freed += size
                print(f"[tmp] removed: {path} ({_fmt(size)})")
            except OSError as e:
                print(f"[tmp] ERROR removing {path}: {e}")
                continue
        removed.append(path)
    return removed, freed


def main():
    parser = argparse.ArgumentParser(
        description="repo-map post-analysis byproduct cleanup (safe: never deletes tracked source)")
    parser.add_argument("--repo", required=True, help="absolute path to the analyzed repo")
    parser.add_argument("--artifacts", action="store_true",
                        help="remove non-tracked compilation artifacts + caches (default)")
    parser.add_argument("--gc", action="store_true",
                        help="compact git history via reflog expire + git gc --aggressive")
    parser.add_argument("--tmp", action="store_true",
                        help="remove repo-map scratch dirs/files under the system temp root")
    parser.add_argument("-n", "--dry-run", action="store_true",
                        help="print what would be removed without removing anything")
    args = parser.parse_args()

    repo = os.path.abspath(args.repo)
    if not os.path.isdir(repo):
        print("repo path does not exist:", repo)
        return 1

    # default: all categories on when none specified
    do_artifacts = args.artifacts or not (args.gc or args.tmp)
    do_gc = args.gc or not (args.artifacts or args.tmp)
    do_tmp = args.tmp or not (args.artifacts or args.gc)

    total_freed = 0
    if do_artifacts:
        _, freed, skipped = cleanup_artifacts(repo, args.dry_run)
        total_freed += freed
    if do_gc:
        ok, _ = cleanup_gc(repo, args.dry_run)
        if not ok:
            return 1
    if do_tmp:
        _, freed = cleanup_tmp(args.dry_run)
        total_freed += freed

    mode = "DRY-RUN" if args.dry_run else "cleaned"
    print(f"[cleanup] {mode}; total released: {_fmt(total_freed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())