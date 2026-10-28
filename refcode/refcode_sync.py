"""
refcode_sync — remote-first sync client.

Pushes a locally-indexed project's DERIVED data (project row + symbol rows +
body-window rows) to a refcode-server, VERIFIES the push landed via the
remote manifest, and (optionally) CLEARS local storage to free disk.

Design goals (user-specified):
  * remote is the single source of truth; local disk stays small
  * new projects default to "push straight to remote"
  * if the remote is unreachable, fall back to a LOCAL PENDING QUEUE that
    records only metadata (slug + sha + counts) — NOT window text. On
    recovery the client re-extracts from source and re-pushes, then clears
    the queue.
  * local never builds the 15GB trigram FTS — it streams derived text only.

Usage (also available as `refcode sync ...`):
  python3 refcode_sync.py push <slug> <path> [--url U] [--sha S] [--licence L]
                                    [--refcode-db DB] [--host http://h:8788]
  python3 refcode_sync.py verify <slug>            [--host ...]
  python3 refcode_sync.py clear <slug> [--refcode-db DB]
  python3 refcode_sync.py flush                     [--host ...]
  python3 refcode_sync.py status

Pure stdlib; reuses refcode.Extractor/windows/iter_files/classify_project so
the same extraction logic drives both local index and remote push.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sqlite3
import sys
import urllib.request
import urllib.error
from pathlib import Path

try:
    import refcode
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import refcode  # type: ignore

# --------------------------------------------------------------------------- #
# paths / env
# --------------------------------------------------------------------------- #
def local_db_path() -> str:
    return os.environ.get("REFCODE_DB") or str(
        Path(os.environ.get("HOME", ".")) / ".refcode" / "refcode.db"
    )

def pending_db_path() -> Path:
    home = Path(os.environ.get("HOME", "."))
    return home / ".refcode" / "pending_sync.db"

def default_host() -> str:
    return os.environ.get("REFCODE_HOST", "http://localhost:8788")

PENDING_SCHEMA = """
CREATE TABLE IF NOT EXISTS pending (
  slug        TEXT PRIMARY KEY,
  path        TEXT,
  url         TEXT,
  sha         TEXT,
  licence     TEXT,
  queued_at   TEXT,
  attempts    INTEGER DEFAULT 0
);
"""

# --------------------------------------------------------------------------- #
# extraction → JSONL stream (no FTS built locally)
# --------------------------------------------------------------------------- #
def extract_to_jsonl(slug: str, path: Path, url: str, sha: str, licence: str):
    """Yield JSONL lines for one project, mirroring refcode._index_one."""
    ex = refcode.Extractor()
    root = path.resolve()
    info = refcode.classify_project(root, ex)
    yield json.dumps({
        "t": "project",
        "slug": slug, "url": url, "sha": sha, "licence": licence,
        "domain": info.get("domain", ""),
        "languages": json.dumps(info.get("lang_counts", {})),
        "dependency_names": json.dumps(info.get("dependency_names", [])),
        "bytes": info.get("bytes", 0),
        "files": info.get("files", 0),
        "symbols": 0, "windows": 0,
    }, ensure_ascii=False)

    nsym = nwin = nfiles = 0
    for fp in refcode.iter_files(root):
        head = refcode._head(fp)
        if refcode._is_binary(head):
            continue
        lang = ex.detect(fp, head)
        if not lang:
            continue
        rel = str(fp.relative_to(root))
        try:
            text = fp.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        nfiles += 1

        for s in ex.symbols(text, lang):
            nsym += 1
            yield json.dumps({
                "t": "symbol", "project": slug,
                "node_id": f"{rel}:{s.get('line', 0)}:{s.get('name', '')}",
                "kind": s.get("kind", ""), "name": s.get("name", ""),
                "qualified_name": s.get("name", ""), "file_path": rel,
                "language": lang, "start_line": s.get("line", 0),
                "end_line": s.get("end_line", 0),
                "signature": s.get("signature", ""), "docstring": "",
            }, ensure_ascii=False)

        for i, (line0, win_text) in enumerate(refcode.windows(text)):
            nwin += 1
            yield json.dumps({
                "t": "window", "project": slug, "file_path": rel,
                "language": lang, "win": i, "line0": line0, "body": win_text,
            }, ensure_ascii=False)

    yield json.dumps({
        "t": "end", "project": slug, "sha": sha,
        "symbols": nsym, "windows": nwin, "files": nfiles,
        "client": "refcode_sync.py",
    }, ensure_ascii=False)


# --------------------------------------------------------------------------- #
# HTTP helpers
# --------------------------------------------------------------------------- #
# The refcode server is a LAN service, not a public website: bypass any system
# proxy (http_proxy / HTTPS_PROXY / no_proxy) that urllib would otherwise honor.
# Without this, a proxy-configured host routes /projects/<s>/push through e.g.
# Privoxy, which 500s on the gzip body instead of forwarding to the server.
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _post(host: str, url_path: str, body: bytes, gz: bool = False) -> dict:
    headers = {"Content-Type": "application/x-ndjson; charset=utf-8"}
    if gz:
        headers["Content-Encoding"] = "gzip"
    req = urllib.request.Request(host + url_path, data=body, headers=headers,
                                 method="POST")
    timeout = int(os.environ.get("REFCODE_PUSH_TIMEOUT", "600"))
    with _opener.open(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))

def _get(host: str, url_path: str) -> dict:
    req = urllib.request.Request(host + url_path, method="GET")
    with _opener.open(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))

def _manifest(host: str, slug: str) -> dict:
    return _get(host, f"/projects/{slug}/manifest")

# --------------------------------------------------------------------------- #
# push / verify / clear / flush
# --------------------------------------------------------------------------- #
def cmd_push(args) -> int:
    slug = args.slug
    path = Path(args.path)
    host = args.host
    gz = not args.no_gzip

    # Probe: does the project already exist remotely? 404 = not present = OK to
    # push; a transport error (URLError / connection) = remote unreachable →
    # fall back to the pending queue. HTTPError(404) must NOT be treated as an
    # outage.
    exists = False
    try:
        probe = _manifest(host, slug)
        exists = bool(probe.get("project"))
    except urllib.error.HTTPError as e:
        if e.code != 404:
            return _fallback_queue(slug, path, args, reason=f"HTTP {e.code}")
        exists = False
    except (urllib.error.URLError, OSError) as e:
        return _fallback_queue(slug, path, args, reason=str(e))

    if exists:
        print(f"[refcode_sync] {slug} already on remote ({probe['project'].get('status')})")
        if args.force:
            print("[refcode_sync] --force: re-pushing (replace)")
        else:
            print("[refcode_sync] exists; use --force to replace, or skip")
            return 0

    # Build the JSONL in memory (gzip keeps it ~44% of raw) and push.
    lines = list(extract_to_jsonl(slug, path, args.url, args.sha, args.licence))
    raw = ("\n".join(lines)).encode("utf-8")
    if gz:
        payload = gzip.compress(raw, 6)
        body, enc = payload, True
    else:
        body, enc = raw, False
    print(f"[refcode_sync] pushing {slug}: {len(lines)} lines "
          f"({len(body)/1e6:.1f}MB{' gz' if enc else ''})")

    try:
        res = _post(host, f"/projects/{slug}/push?client=refcode_sync.py",
                    body, gz=enc)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        return _fallback_queue(slug, path, args, reason=str(e))

    print(f"[refcode_sync] pushed: {res.get('nsym', '?')} syms, "
          f"{res.get('nwin', '?')} wins")

    if args.no_verify:
        return 0
    v = verify(slug, host, expect_sym=res.get("nsym"), expect_win=res.get("nwin"))
    if not v:
        print(f"[refcode_sync] WARNING: verification failed for {slug}")
        return 2
    print(f"[refcode_sync] verified: {slug} fully on remote")
    return 0


def verify(slug: str, host: str, expect_sym: int | None = None,
           expect_win: int | None = None) -> bool:
    try:
        m = _manifest(host, slug)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        return False
    proj = m.get("project") or {}
    if not proj:
        return False
    if expect_sym is not None and (proj.get("symbols") != expect_sym
                                   and proj.get("symbols") != 0):
        print(f"[refcode_sync] symbol mismatch: local={expect_sym} "
              f"remote={proj.get('symbols')}")
        return False
    if expect_win is not None and (proj.get("windows") != expect_win
                                   and proj.get("windows") != 0):
        print(f"[refcode_sync] window mismatch: local={expect_win} "
              f"remote={proj.get('windows')}")
        return False
    return True


def cmd_verify(args) -> int:
    host = args.host
    try:
        m = _manifest(host, args.slug)
    except urllib.error.HTTPError as e:
        print(f"[refcode_sync] {args.slug} NOT on remote (HTTP {e.code})")
        return 1
    except (urllib.error.URLError, OSError) as e:
        print(f"[refcode_sync] cannot reach remote: {e}")
        return 2
    proj = m.get("project")
    if not proj:
        print(f"[refcode_sync] {args.slug} NOT on remote")
        return 1
    lp = m.get("last_push") or {}
    print(f"[refcode_sync] {args.slug}: sha={proj.get('sha')} "
          f"sym={proj.get('symbols')} win={proj.get('windows')} "
          f"files={proj.get('files')} pushed_at={lp.get('pushed_at')}")
    return 0


def cmd_clear(args) -> int:
    """Delete a project's local data + source. `refcode.db` is the local index."""
    slug = args.slug
    removed = []
    # Remove source cache if present.
    cache = refcode.default_repo_cache()
    src = cache / slug
    if src.exists():
        import shutil
        shutil.rmtree(src)
        removed.append(f"source {src}")
    # Remove this project's rows from the local refcode.db (if it exists).
    dbp = Path(local_db_path())
    if dbp.exists():
        try:
            con = sqlite3.connect(dbp)
            cur = con.execute(
                "SELECT COUNT(*) FROM ref_projects WHERE slug=?", (slug,))
            if cur.fetchone()[0]:
                con.execute("DELETE FROM ref_symbols WHERE project=?", (slug,))
                con.execute("DELETE FROM ref_body_fts WHERE project=?", (slug,))
                con.execute("DELETE FROM ref_projects WHERE slug=?", (slug,))
                con.commit()
                removed.append(f"local db rows ({dbp})")
        except Exception as e:  # DB may be locked or absent tables
            print(f"[refcode_sync] clear db error: {e}")
    if not removed:
        print(f"[refcode_sync] nothing to clear for {slug}")
        return 0
    print(f"[refcode_sync] cleared: " + ", ".join(removed))
    return 0


def _fallback_queue(slug: str, path: Path, args, reason: str) -> int:
    """Remote unreachable → record metadata-only in the pending queue."""
    con = sqlite3.connect(pending_db_path())
    con.executescript(PENDING_SCHEMA)
    con.execute(
        """INSERT OR REPLACE INTO pending
             (slug,path,url,sha,licence,queued_at,attempts)
           VALUES (?,?,?,?,?,?,0)""",
        (slug, str(path), args.url, args.sha, args.licence,
         _now_iso()),
    )
    con.commit()
    con.close()
    print(f"[refcode_sync] remote unreachable ({reason}); queued {slug} "
          f"(metadata only; will re-extract on flush)")
    return 3


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def cmd_flush(args) -> int:
    """Re-push every pending queue entry once the remote is back."""
    host = args.host
    dbp = pending_db_path()
    if not dbp.exists():
        print("[refcode_sync] no pending queue")
        return 0
    con = sqlite3.connect(dbp)
    con.executescript(PENDING_SCHEMA)
    rows = con.execute("SELECT slug,path,url,sha,licence FROM pending ORDER BY queued_at").fetchall()
    if not rows:
        print("[refcode_sync] pending queue empty")
        return 0
    pushed = failed = 0
    for slug, path, url, sha, licence in rows:
        try:
            p = Path(path)
            lines = list(extract_to_jsonl(slug, p, url, sha, licence))
            body = gzip.compress("\n".join(lines).encode("utf-8"), 6)
            res = _post(host, f"/projects/{slug}/push?client=refcode_sync-flush",
                        body, gz=True)
            if verify(slug, host, res.get("nsym"), res.get("nwin")):
                con.execute("DELETE FROM pending WHERE slug=?", (slug,))
                con.commit()
                pushed += 1
                print(f"[refcode_sync] flushed {slug}")
            else:
                failed += 1
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            print(f"[refcode_sync] flush {slug} failed: {e}")
            failed += 1
            break
    con.close()
    print(f"[refcode_sync] flush done: pushed={pushed} failed={failed}")
    return 0 if failed == 0 else 1


def cmd_status(args) -> int:
    dbp = pending_db_path()
    if not dbp.exists():
        print("[refcode_sync] pending queue: empty")
    else:
        con = sqlite3.connect(dbp)
        con.executescript(PENDING_SCHEMA)
        rows = con.execute(
            "SELECT slug,url,sha,queued_at,attempts FROM pending ORDER BY queued_at").fetchall()
        con.close()
        if rows:
            print(f"[refcode_sync] pending queue: {len(rows)} item(s)")
            for r in rows:
                print(f"  {r[0]}  sha={r[2] or '-'}  queued={r[3]}  attempts={r[4]}")
        else:
            print("[refcode_sync] pending queue: empty")
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _add_common(sp):
    sp.add_argument("--host", default=default_host(),
                    help="refcode-server base URL (default: $REFCODE_HOST or "
                         "http://localhost:8788)")
    sp.add_argument("--refcode-db", default=None,
                    help="local refcode.db (default: $REFCODE_DB)")


def _add_sync_actions(pss, flat: bool):
    sp = pss.add_parser("push", help="extract + push a project to remote")
    sp.add_argument("slug")
    sp.add_argument("path")
    sp.add_argument("--url", default="")
    sp.add_argument("--sha", default="")
    sp.add_argument("--licence", default="")
    sp.add_argument("--force", action="store_true")
    sp.add_argument("--no-gzip", action="store_true")
    sp.add_argument("--no-verify", action="store_true")
    _add_common(sp)

    sp = pss.add_parser("verify", help="check a project exists on remote")
    sp.add_argument("slug")
    _add_common(sp)

    sp = pss.add_parser("clear", help="delete local data+source for a project")
    sp.add_argument("slug")
    _add_common(sp)

    sp = pss.add_parser("flush", help="re-push queued projects (remote back)")
    _add_common(sp)

    sp = pss.add_parser("status", help="show pending queue")
    _add_common(sp)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="refcode_sync",
                                description="Remote-first sync client for refcode")
    sub = p.add_subparsers(dest="action", required=True)
    _add_sync_actions(sub, flat=True)
    return p


def build_sync_parser(sub) -> None:
    """Register the `sync` subcommand under an existing parent subparsers."""
    ps = sub.add_parser("sync", help="remote-first sync (push/verify/clear/flush/status)")
    ps.set_defaults(func=cmd_sync)
    pss = ps.add_subparsers(dest="action", required=True)
    _add_sync_actions(pss, flat=False)


def cmd_sync(args, _conn=None) -> int:
    """Dispatch a `sync` sub-action (refcode.py calls this as args.func(args, conn))."""
    return cmd_dispatch(args)


def cmd_dispatch(args) -> int:
    if args.action == "push":
        return cmd_push(args)
    if args.action == "verify":
        return cmd_verify(args)
    if args.action == "clear":
        return cmd_clear(args)
    if args.action == "flush":
        return cmd_flush(args)
    if args.action == "status":
        return cmd_status(args)
    print(f"unknown action: {args.action}")
    return 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return cmd_dispatch(args)


if __name__ == "__main__":
    sys.exit(main())