#!/usr/bin/env python3
"""Measure whether a deep-dive recursive self-improvement actually helped.

Replaces the "the LLM pats itself on the back" hand-wave with a measurable
regression: a playbook/methodology change is only accepted if the error
recurrence rate dropped after the change. The BEFORE/AFTER split is by deep-dive
layer. Errors recorded at layer <= --before-layer are the BEFORE cohort (the
state of the world before the improvement); errors at layer > --before-layer are
the AFTER cohort (the state after the improvement).

A methodology change is only accepted when:
  - the AFTER cohort actually has data (>=1 run, so the fix ran and produced
    evidence rather than being asserted), AND
  - AFTER recurrence rate is strictly lower than BEFORE recurrence rate.

This is a light, deterministic comparison tool, not an ML eval. It never writes
to any table and never judges the LLM's confidence - only SQL-checkable facts.

CLI:
  regression_check.py --project <path> [--db {{ANALYSIS_DB}}] [--before-layer N]

Exit codes:
  0  PASS               - AFTER has data and its recurrence rate < BEFORE's
  1  INSUFFICIENT_DATA  - no AFTER runs yet; improvement cannot be claimed
  1  NO_IMPROVEMENT     - AFTER recurrence rate >= BEFORE (no gain / worsening)
  2  ERROR              - bad CLI args / DB open failure
"""

import argparse
import json
import sqlite3
import sys

DEFAULT_DB = "{{ANALYSIS_DB}}"
DEFAULT_BEFORE_LAYER = 1


def open_db(path):
    """Open the board DB read-only with a busy timeout for concurrency."""
    # read-only: no journal created, no write locks taken
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
    con.execute("PRAGMA busy_timeout = 10000")
    con.row_factory = sqlite3.Row
    return con


def _cohort(con, project, layer_op, before_layer):
    """Return dict {runs, total_errors, recurring, rate} for one cohort.

    layer_op is the SQL operator (<= or >) applied against before_layer.
    """
    sql = (
        "SELECT COUNT(*) AS total, "
        "       SUM(recurring) AS recurring, "
        "       COUNT(DISTINCT run_id) AS runs "
        f"FROM deepdive_errors WHERE project_path = ? AND layer {layer_op} ?"
    )
    row = con.execute(sql, (project, before_layer)).fetchone()
    total = row["total"] or 0
    recurring = row["recurring"] or 0
    runs = row["runs"] or 0
    return {
        "runs": runs,
        "total_errors": total,
        "recurring": recurring,
        "rate": (recurring / total) if total else 0.0,
    }


def check(project, db_path, before_layer):
    con = open_db(db_path)
    try:
        before = _cohort(con, project, "<=", before_layer)
        after = _cohort(con, project, ">", before_layer)
    finally:
        con.close()

    improvement_delta = before["rate"] - after["rate"]

    if after["runs"] < 1:
        # no AFTER data yet: the fix has not produced any evidence to accept on
        verdict = "INSUFFICIENT_DATA"
    elif improvement_delta > 0:
        # strictly lower AFTER rate AND after has run data -> real improvement
        verdict = "PASS"
    else:
        verdict = "NO_IMPROVEMENT"

    result = {
        "project_path": project,
        "before": before,
        "after": after,
        "improvement_delta": improvement_delta,
        "verdict": verdict,
    }

    exit_code = 0 if verdict == "PASS" else 1
    return exit_code, result


def main():
    parser = argparse.ArgumentParser(description="deep-dive recursive self-improvement regression check")
    parser.add_argument("--project", required=True, help="absolute path to the analyzed project")
    parser.add_argument("--db", default=DEFAULT_DB, help=f"board DB path (default: {DEFAULT_DB})")
    parser.add_argument("--before-layer", type=int, default=DEFAULT_BEFORE_LAYER,
                        help=f"layer boundary for BEFORE/AFTER split (default: {DEFAULT_BEFORE_LAYER})")
    args = parser.parse_args()

    import os
    project = os.path.abspath(args.project)

    try:
        exit_code, result = check(project, args.db, args.before_layer)
    except sqlite3.Error as e:
        print(json.dumps({"error": f"db error: {e}", "verdict": "ERROR"}))
        return 2

    print(json.dumps(result, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())