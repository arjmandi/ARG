#!/usr/bin/env python3
"""probe_arg_log — the beat-by-beat Log timeline + consistency checks.

Read-only over arg_state.db (turn_record) and arg_probe.db (api_log). Shows what
was done/predicted/observed/matched per beat with source_stamp, overlays
WRITE_REJECT/SUBSTITUTION_CAUGHT/REVISION, and checks that the control plane,
the Log, and the API agree: api_log↔Log action, frame-hash loop closure, and
drift_ref stamped every beat.

Usage: uv run python probe_arg_log.py [--db arg_state.db] [--probe arg_probe.db] [--run RUN]
"""
import argparse
import sqlite3
from typing import Optional


def _ro(db: str) -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def report(db: str, probe: str, run: Optional[str] = None) -> dict:
    m = _ro(db); p = _ro(probe)
    if not run:
        r = m.execute("SELECT run_id FROM run ORDER BY started_at DESC LIMIT 1").fetchone()
        run = r["run_id"] if r else None
    if not run:
        print("no run"); return {}
    turns = m.execute("SELECT * FROM turn_record WHERE run_id=? ORDER BY turn_id", (run,)).fetchall()
    api = {a["turn_id"]: a for a in p.execute(
        "SELECT * FROM api_log WHERE run_id=? ORDER BY turn_id", (run,))}
    rejects = m.execute("SELECT turn_id, organ, violation_class FROM write_reject WHERE run_id=?",
                        (run,)).fetchall()
    subs = m.execute("SELECT turn_id FROM substitution_caught WHERE run_id=?", (run,)).fetchall()
    revs = m.execute("SELECT turn_id, step_id FROM revision WHERE run_id=?", (run,)).fetchall()

    print(f"=== ARG Log timeline — run {run[:24]} ({len(turns)} beats) ===")
    print("turn | action | src | lvl | score | match | drift | state")
    for t in turns[:200]:
        print(f"{t['turn_id']:>4} | {t['action']:<8} | {(t['source_stamp'] or '')[:4]:<4} | "
              f"{t['level_counter']} | {t['score']} | {t['match']} | {t['drift_ref'] or '-'} | "
              f"{t['state_flags']}")

    problems = []
    for t in turns:
        a = api.get(t["turn_id"])
        if a and a["action"] != t["action"]:
            problems.append(f"turn {t['turn_id']}: api action {a['action']} != Log {t['action']}")
        if a and a["frame_received"] and a["response_json"]:
            pass  # frame present; deep hash check available offline via response_json
        if t["drift_ref"] is None and t["action"] != "RESET":
            problems.append(f"turn {t['turn_id']}: drift_ref not stamped")
    # frame-hash loop closure
    for i in range(len(turns) - 1):
        if turns[i + 1]["action"] == "RESET":
            continue
        if turns[i]["post_frame_hash"] != turns[i + 1]["pre_frame_hash"]:
            problems.append(f"turn {turns[i+1]['turn_id']}: frame-hash discontinuity")

    print(f"\nWRITE_REJECT: {len(rejects)} | SUBSTITUTION_CAUGHT: {len(subs)} | REVISION: {len(revs)}")
    print("\n=== consistency ===")
    if problems:
        for pb in problems[:20]:
            print("  ✗ " + pb)
    else:
        print("  ✓ api↔Log actions agree; frame-hash loop closed; drift_ref stamped every beat")
    return {"beats": len(turns), "problems": problems, "rejects": len(rejects)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="arg_state.db")
    ap.add_argument("--probe", default="arg_probe.db")
    ap.add_argument("--run", default=None)
    a = ap.parse_args()
    report(a.db, a.probe, a.run)


if __name__ == "__main__":
    main()
