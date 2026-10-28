#!/usr/bin/env python3
"""Export an existing refcode.db corpus as gzipped per-project window-text streams,
so a remote refcode-server.ts can import it WITHOUT re-extracting from source.

WHY THIS EXISTS (priority-3 decision):
An already-indexed refcode.db holds the trigram FTS (large) that is *reconstructible*
from its window-text column. The refcode-server.ts remote store rebuilds FTS from window
text on push, so we can hand it the same derived data the local `sync push` would extract —
just read from the existing DB instead of re-running tree-sitter over source. That avoids
re-extracting (slow) and avoids shipping the big FTS (huge). Usage:

    # list what the DB holds
    python3 migrate-existing.py list --db {{REFCODE_DB}}

    # export ONE project's windows as gz to a file, ready to feed a server's /projects/<s>/push
    python3 migrate-existing.py export a2a --db {{REFCODE_DB}} -o /tmp/a2a.ndjson.gz

    # export ALL live projects, one gz each, into an out dir
    python3 migrate-existing.py export-all --db {{REFCODE_DB}} -o /tmp/corpus-gz

The output JSONL matches what refcode_sync.py push sends (see refcode-server.ts push schema),
so a small forwarder can POST each file to the Windows service on the user's behalf.
"""
from __future__ import annotations
import argparse
import gzip
import json
import sqlite3
import sys
from pathlib import Path


def _open(db: str) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def cmd_list(args) -> int:
    conn = _open(args.db)
    total_wins = 0
    print(f"{'slug':<32} {'status':<10} {'wins':>10}")
    for r in conn.execute(
        "SELECT p.slug, p.status, "
        "(SELECT COUNT(*) FROM ref_body_fts b WHERE b.project = p.slug) AS wins "
        "FROM ref_projects p ORDER BY p.slug"
    ):
        print(f"{r['slug']:<32} {r['status']:<10} {r['wins']:>10}")
        total_wins += r["wins"] or 0
    print(f"\n{len(list(conn.execute('SELECT slug FROM ref_projects')))} projects, {total_wins} total body windows")
    conn.close()
    return 0


def _export_project(conn, slug: str, out: Path) -> int:
    proj = conn.execute("SELECT * FROM ref_projects WHERE slug=?", (slug,)).fetchone()
    if proj is None:
        print(f"[warn] unknown slug: {slug}", file=sys.stderr)
        return 0

    syms = conn.execute(
        "SELECT * FROM ref_symbols WHERE project=? ORDER BY rowid", (slug,)
    ).fetchall()
    wins = conn.execute(
        "SELECT * FROM ref_body_fts WHERE project=? ORDER BY rowid", (slug,)
    ).fetchall()
    files = conn.execute(
        "SELECT COUNT(DISTINCT file_path) FROM ref_body_fts WHERE project=?", (slug,)
    ).fetchone()[0]

    nsym = 0
    nwin = 0
    with gzip.open(out, "wt", encoding="utf-8") as fh:
        rec = {
            "t": "project",
            "slug": proj["slug"],
            "url": proj["url"] or "",
            "sha": proj["sha"] or "",
            "licence": proj["licence"] or "",
            "use_policy": proj["use_policy"] or "",
            "domain": proj["domain"] or "",
            "languages": proj["languages"] or "",
            "ask_for": proj["ask_for"] or "",
            "dependency_names": proj["dependency_names"] or "",
            "files": proj["files"] or files,
            "symbols": proj["symbols"] or len(syms),
            "windows": proj["windows"] or len(wins),
        }
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

        for s in syms:
            rec = {
                "t": "symbol",
                "project": s["project"],
                "node_id": s["node_id"],
                "kind": s["kind"] or "",
                "name": s["name"] or "",
                "qualified_name": s["qualified_name"] or "",
                "file_path": s["file_path"] or "",
                "language": s["language"] or "",
                "start_line": s["start_line"] or 0,
                "end_line": s["end_line"] or 0,
                "signature": s["signature"] or "",
                "docstring": s["docstring"] or "",
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            nsym += 1

        for w in wins:
            rec = {
                "t": "window",
                "project": w["project"],
                "file_path": w["file_path"] or "",
                "language": w["language"] or "",
                "win": w["win"] or 0,
                "line0": w["line0"] or 0,
                "body": w["body"] or "",
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            nwin += 1

        fh.write(
            json.dumps(
                {
                    "t": "end",
                    "project": slug,
                    "sha": proj["sha"] or "",
                    "symbols": len(syms),
                    "windows": len(wins),
                    "files": files,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    return nwin


def cmd_export(args) -> int:
    conn = _open(args.db)
    out = Path(args.out)
    n = _export_project(conn, args.slug, out)
    print(f"exported {args.slug}: {n} windows -> {out}")
    conn.close()
    return 0


def cmd_export_all(args) -> int:
    conn = _open(args.db)
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    total = 0
    for r in conn.execute(
        "SELECT slug, status FROM ref_projects WHERE status='live' ORDER BY slug"
    ):
        out = outdir / f"{r['slug']}.ndjson.gz"
        n = _export_project(conn, r["slug"], out)
        print(f"  {r['slug']:<32} {n:>8} windows -> {out.name}")
        total += n
    print(f"\ndone: exported to {outdir} ({total} windows total)")
    conn.close()
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    for name, fn, extra in (
        ("list", cmd_list, lambda s: s.add_argument("--db", default="{{REFCODE_DB}}")),
        ("export", cmd_export, lambda s: (
            s.add_argument("slug"),
            s.add_argument("--db", default="{{REFCODE_DB}}"),
            s.add_argument("-o", "--out", required=True),
        )),
        ("export-all", cmd_export_all, lambda s: (
            s.add_argument("--db", default="{{REFCODE_DB}}"),
            s.add_argument("-o", "--out", required=True),
        )),
    ):
        sp = sub.add_parser(name)
        extra(sp)
        sp.set_defaults(func=fn)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())