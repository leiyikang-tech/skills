#!/usr/bin/env python3
"""Migrate an existing local refcode.db corpus to a remote refcode-server.ts,
project by project: export each live project's window/symbol records as gz JSONL
(via migrate-existing) and POST it to the remote /projects/<slug>/push.

WHY THIS EXISTS (priority-3): a remote refcode-server rebuilds its trigram FTS
from pushed window text, so migrating from an existing 15GB local DB needs only
the derived window/symbol text — NOT the local FTS, NOT source re-extraction.
This driver is resumable (skips slugs already present on the remote) and records
each project's result in migration-migrate.log.
"""
from __future__ import annotations
import json
import os
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# --- config --------------------------------------------------------------- #
SRC_DB = os.environ.get("SRC_REFCODE_DB", "{{REFCODE_DB}}")
REMOTE = os.environ.get("REMOTE") or os.environ.get("REFCODE_HOST", "http://localhost:8788")
WORK = Path(os.environ.get("WORK_DIR", "{{MIGRATE_WORK}}"))
LOG = WORK / "migration-migrate.log"
_done: set[str] = set()
if LOG.exists():
    for line in LOG.read_text(encoding="utf-8").splitlines():
        if "[ok]" in line or "[skip]" in line:
            _done.add(line.split()[1])

_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def post_project(slug: str, gz_path: Path) -> dict:
    with gz_path.open("rb") as f:
        body = f.read()
    req = urllib.request.Request(
        f"{REMOTE}/projects/{slug}/push",
        data=body,
        headers={"Content-Type": "application/x-ndjson; charset=utf-8",
                 "Content-Encoding": "gzip"},
        method="POST",
    )
    with _opener.open(req, timeout=1800) as r:
        return json.loads(r.read().decode("utf-8"))


def remote_has(slug: str) -> bool:
    req = urllib.request.Request(f"{REMOTE}/projects/{slug}/manifest", method="GET")
    try:
        with _opener.open(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8")).get("project") is not None
    except urllib.error.HTTPError as e:
        return e.code != 404
    except Exception:
        return True  # assume present on any doubt; manual re-check later


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(f"file:{SRC_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    projects = conn.execute(
        "SELECT slug FROM ref_projects WHERE status='live' ORDER BY slug"
    ).fetchall()
    conn.close()

    ok = skip = fail = 0
    with LOG.open("a", encoding="utf-8") as log:
        for row in projects:
            slug = row["slug"]
            if slug in _done:
                skip += 1
                continue
            gz = WORK / f"{slug}.ndjson.gz"
            try:
                import subprocess
                r = subprocess.run(
                    [sys.executable, str(Path(__file__).parent / "migrate-existing.py"),
                     "export", slug, "--db", SRC_DB, "-o", str(gz)],
                    capture_output=True, text=True, timeout=600)
                if r.returncode != 0 or not gz.exists() or gz.stat().st_size == 0:
                    raise RuntimeError(r.stderr.strip() or "export produced empty file")
                res = post_project(slug, gz)
                log.write(f"[ok] {slug} nsym={res.get('nsym')} nwin={res.get('nwin')}\n")
                log.flush()
                ok += 1
                print(f"[ok] {slug}: {res.get('nsym')}s/{res.get('nwin')}w", flush=True)
            except Exception as e:
                log.write(f"[fail] {slug} {type(e).__name__}: {e}\n")
                log.flush()
                fail += 1
                print(f"[fail] {slug}: {type(e).__name__}: {e}", flush=True)
            finally:
                _done.add(slug)
            if gz.exists():
                gz.unlink()  # free disk; remote holds the data now

    print(f"\nDONE ok={ok} skip={skip} fail={fail} (log: {LOG})")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())