#!/usr/bin/env python3
"""SQL-checkable convergence stop condition for the repo-map `deep-dive` command.

Replaces the undefined "score stable / quality >= threshold" hand-wave with a
deterministic query against the shared board DB. A deep-dive has CONVERGED when
the LAST run on a project added zero new grounded concepts, zero new findings,
zero new gap claims, and zero new gap fills — exactly the condition encoded in
the v_dd_convergence view (deepdive.sql). convergence.py only READS the DB; it
does not gate or mutate anything (unless --update is passed, which sets
deepdive_runs.converged=1 for the last run when converged=true).

  convergence.py --project <path> [--db {{ANALYSIS_DB}}] [--update]

Prints JSON and always exits 0 (this is a read, not a gate).
"""

import argparse
import json
import os
import sqlite3
import sys

ZERO_COUNTS = ("n_concepts", "n_findings", "n_gaps_claimed", "n_gaps_filled")


def _connect(db):
    con = sqlite3.connect(db, timeout=10)
    con.execute("PRAGMA busy_timeout = 10000")
    con.execute("PRAGMA query_only = ON")
    return con


def fetch_runs(con, project):
    cur = con.execute(
        """
        SELECT run_id, layer, n_concepts, n_findings, n_gaps_claimed, n_gaps_filled,
               finished_at
        FROM deepdive_runs
        WHERE project_path = ?
        ORDER BY layer DESC, finished_at DESC, run_id DESC
        """,
        (project,),
    )
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def run_counts(row):
    return {c: row.get(c, 0) for c in ZERO_COUNTS}


def compute_result(project, runs):
    total_runs = len(runs)
    if total_runs == 0:
        return {
            "project_path": project,
            "total_runs": 0,
            "last_layer": None,
            "last_run_counts": {},
            "prev_run_counts": {},
            "converged": False,
            "reason": "no runs recorded for project",
        }

    last = runs[0]
    prev = runs[1] if total_runs >= 2 else None

    last_counts = run_counts(last)
    condition_met = all(v == 0 for v in last_counts.values())

    if prev is None:
        converged = False
        reason = f"only {total_runs} run recorded - not enough data to conclude convergence"
    else:
        converged = bool(condition_met)
        reason = (
            "last run added zero new grounded concepts/findings/gap claims/gap fills"
            if converged
            else "last run added new grounded concepts/findings/gap claims/gap fills"
        )

    return {
        "project_path": project,
        "total_runs": total_runs,
        "last_layer": last["layer"],
        "last_run_counts": last_counts,
        "prev_run_counts": run_counts(prev) if prev else {},
        "converged": converged,
        "reason": reason,
    }


def apply_update(con, project, last_run_id, converged):
    if not converged:
        return
    con.execute("PRAGMA query_only = OFF")
    con.execute(
        "UPDATE deepdive_runs SET converged = 1 WHERE run_id = ? AND project_path = ?",
        (last_run_id, project),
    )
    con.commit()
    con.execute("PRAGMA query_only = ON")


def main():
    parser = argparse.ArgumentParser(
        description="SQL-checkable convergence stop condition for deep-dive"
    )
    parser.add_argument("--project", required=True, help="absolute path to analyzed project")
    parser.add_argument(
        "--db",
        default=os.path.expanduser("{{ANALYSIS_DB}}"),
        help="path to the board SQLite DB (default: {{ANALYSIS_DB}})",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="set deepdive_runs.converged=1 for the last run when converged=true",
    )
    args = parser.parse_args()

    project = os.path.abspath(args.project)

    try:
        con = _connect(args.db)
    except sqlite3.Error as e:
        print(json.dumps({
            "project_path": project,
            "total_runs": 0,
            "last_layer": None,
            "last_run_counts": {},
            "prev_run_counts": {},
            "converged": False,
            "reason": f"cannot open db {args.db}: {e}",
        }, indent=2))
        return 0

    try:
        runs = fetch_runs(con, project)
        result = compute_result(project, runs)
        if args.update and runs:
            apply_update(con, project, runs[0]["run_id"], result["converged"])
    except sqlite3.Error as e:
        result = {
            "project_path": project,
            "total_runs": 0,
            "last_layer": None,
            "last_run_counts": {},
            "prev_run_counts": {},
            "converged": False,
            "reason": f"query failed: {e}",
        }
    finally:
        con.close()

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())