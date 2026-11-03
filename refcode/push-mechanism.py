#!/usr/bin/env python3
"""Push a locally-mined mechanism (from mechanisms build) to the shared refcode
server via its POST /mechanisms endpoint (added in commit 1381138)."""

import argparse
import json
import sqlite3
import sys
import urllib.request

MECH_DB = "/root/.refcode/mechanisms.db"
DEFAULT_HOST = "http://172.16.17.124:8788"


def fetch_mechanism(db_path: str, mech_id: str) -> dict:
    db = sqlite3.connect(db_path)
    row = db.execute(
        "SELECT id,name,domain,domain_name,definition,scenes,pros,cons,maturity "
        "FROM mechanisms WHERE id=?",
        (mech_id,),
    ).fetchone()
    if not row:
        raise SystemExit(f"mechanism not found: {mech_id}")
    cols = ["id", "name", "domain", "domain_name", "definition",
            "scenes", "pros", "cons", "maturity"]
    d = dict(zip(cols, row))
    for k in ("scenes", "pros", "cons"):
        if isinstance(d[k], str):
            try:
                d[k] = json.loads(d[k])
            except ValueError:
                pass
    return d


def push(host: str, payload: dict) -> None:
    req = urllib.request.Request(
        f"{host}/mechanisms",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        print(resp.status, resp.read().decode())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mech_id", help="mechanism id, e.g. auto-A105-craft-anything")
    ap.add_argument("--db", default=MECH_DB)
    ap.add_argument("--host", default=DEFAULT_HOST)
    a = ap.parse_args()
    payload = fetch_mechanism(a.db, a.mech_id)
    push(a.host, payload)
    print(f"pushed {payload['id']} -> {a.host}/mechanisms")