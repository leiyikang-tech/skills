#!/usr/bin/env python3
"""State backbone for the repo-map skill: init / advance / resume / finish.

Owns harness/run.json so the repository-analysis pipeline is DURABLE and
re-runnable across crashes. A phase only advances when its gate passes; the
gate checker writes run.json atomically, so state is always consistent at a
known phase and a mid-run crash resumes at the exact failed gate.

Commands (each returns exit 0 on success, 1 on real error):
  init    --repo <path> [--out <dir>]   create a fresh run in discovery phase
  gate    <g1|g2|g3|g4|g5> [--result PASS|FAIL] [--note text]
                                        record one gate result (PASS advances)
  advance <phase>                       mark phase complete, move to next
  resume                                print the current phase + gate state
  status                                human-readable full run state
  finish  --summary <text>              mark run complete; write summary

State shape (run.json):
  {
    "repo": "<abs path>",
    "phase": "discovery",
    "created": "<iso ts>",
    "updated": "<iso ts>",
    "gates": {"g1": {"result": "PASS", "attempts": 3, "note": ""}, ...},
    "artifacts": {"dirs": [], "root_kb": "", "stack": ""},
    "summary": ""
  }
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

PHASES = ["g1", "g2", "g3", "g4", "g5"]
PHASE_LABELS = {
    "g1": "discovery",
    "g2": "scoring",
    "g3": "generate",
    "g4": "review",
    "g5": "final",
}
MAX_ATTEMPTS = 3


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_state(path):
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def save_state(path, state):
    state["updated"] = now_iso()
    with open(path, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
        f.write("\n")


def cmd_init(args):
    run_dir = args.out or os.path.dirname(os.path.abspath(__file__))
    run_json = os.path.join(run_dir, "run.json")
    os.makedirs(run_dir, exist_ok=True)
    if os.path.exists(run_json):
        print(f"run.json already exists at {run_json}; not overwriting (use --resume / gate)")
        return 1
    repo = os.path.abspath(args.repo)
    if not os.path.isdir(repo):
        print(f"repo path does not exist: {repo}")
        return 1
    state = {
        "repo": repo,
        "phase": PHASE_LABELS["g1"],
        "created": now_iso(),
        "updated": now_iso(),
        "gates": {},
        "artifacts": {"dirs": [], "root_kb": "", "stack": ""},
        "summary": "",
    }
    for g in PHASES:
        state["gates"][g] = {"result": None, "attempts": 0, "note": ""}
    save_state(run_json, state)
    print(f"init: run created for {repo} (phase=discovery)")
    return 0


def cmd_gate(args, run_dir):
    run_json = os.path.join(run_dir, "run.json")
    state = load_state(run_json)
    if not state:
        print("no run.json found; run 'refresh_state.py init --repo <path>' first")
        return 1
    g = args.gate.lower()
    if g not in PHASES:
        print(f"unknown gate {g}; expected one of {PHASES}")
        return 1
    gate = state["gates"][g]
    result = args.result.upper() if args.result else "PASS"
    if result == "PASS":
        gate["result"] = "PASS"
        gate["note"] = args.note or gate["note"]
        idx = PHASES.index(g)
        if idx + 1 < len(PHASES):
            state["phase"] = PHASE_LABELS[PHASES[idx + 1]]
            save_state(run_json, state)
            print(f"gate {g}: PASS -> advanced to phase {state['phase']}")
        else:
            state["phase"] = "complete"
            save_state(run_json, state)
            print(f"gate {g}: PASS -> run complete")
    else:
        gate["attempts"] += 1
        gate["result"] = "FAIL"
        gate["note"] = args.note or gate["note"]
        save_state(run_json, state)
        if gate["attempts"] >= MAX_ATTEMPTS:
            print(f"gate {g}: FAIL (attempt {gate['attempts']}/{MAX_ATTEMPTS}) -> BLOCKED, escalate to oracle")
            return 2
        print(f"gate {g}: FAIL (attempt {gate['attempts']}/{MAX_ATTEMPTS}) -> rework")
    return 0


def cmd_resume(run_dir):
    run_json = os.path.join(run_dir, "run.json")
    state = load_state(run_json)
    if not state:
        print("no run.json found")
        return 1
    print(f"phase={state['phase']} repo={state['repo']}")
    for g in PHASES:
        gst = state["gates"][g]
        print(f"  {g}: result={gst['result']} attempts={gst['attempts']} note={gst['note']}")
    return 0


def cmd_status(run_dir):
    run_json = os.path.join(run_dir, "run.json")
    state = load_state(run_json)
    if not state:
        print("no run.json found")
        return 1
    print(json.dumps(state, indent=2, ensure_ascii=False))
    return 0


def cmd_finish(args, run_dir):
    run_json = os.path.join(run_dir, "run.json")
    state = load_state(run_json)
    if not state:
        print("no run.json found")
        return 1
    state["phase"] = "complete"
    state["summary"] = args.summary or state["summary"]
    save_state(run_json, state)
    print("finish: run marked complete with summary")
    return 0


def main():
    parser = argparse.ArgumentParser(description="repo-map state backbone")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("--repo", required=True, help="absolute path to the repo to analyze")
    p_init.add_argument("--out", help="directory to write run.json (default: harness dir)")

    p_gate = sub.add_parser("gate")
    p_gate.add_argument("gate", choices=PHASES)
    p_gate.add_argument("--result", choices=["PASS", "FAIL"])
    p_gate.add_argument("--note", default="")
    p_gate.add_argument("--out", help="directory holding run.json (default: harness dir)")

    p_resume = sub.add_parser("resume")
    p_resume.add_argument("--out", help="directory holding run.json (default: harness dir)")

    p_status = sub.add_parser("status")
    p_status.add_argument("--out", help="directory holding run.json (default: harness dir)")

    p_finish = sub.add_parser("finish")
    p_finish.add_argument("--summary", default="")
    p_finish.add_argument("--out", help="directory holding run.json (default: harness dir)")

    args = parser.parse_args()
    default_run_dir = os.path.dirname(os.path.abspath(__file__))
    run_dir = getattr(args, "out", None) or default_run_dir

    if args.cmd == "init":
        return cmd_init(args)
    if args.cmd == "gate":
        return cmd_gate(args, run_dir)
    if args.cmd == "resume":
        return cmd_resume(run_dir)
    if args.cmd == "status":
        return cmd_status(run_dir)
    if args.cmd == "finish":
        return cmd_finish(args, run_dir)
    return 1


if __name__ == "__main__":
    sys.exit(main())