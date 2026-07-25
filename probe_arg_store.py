#!/usr/bin/env python3
"""probe_arg_store — reconstruct ARG's belief/intention state as of a turn.

Read-only over arg_state.db. State "as of T" is computed from append-only rows
(current version = MAX(version) with created_turn≤T; rung/status via the latest
status_transition with turn_id≤T; support/interactions via COUNT turn_id≤T) —
never a HEAD snapshot, so any past turn is inspectable.

Usage: uv run python probe_arg_store.py [--db arg_state.db] [--run RUN] [--turn T]
"""
import argparse
import json
import sqlite3
from typing import Optional


def _conn(db: str) -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def latest_run(c: sqlite3.Connection) -> Optional[str]:
    r = c.execute("SELECT run_id FROM run ORDER BY started_at DESC LIMIT 1").fetchone()
    return r["run_id"] if r else None


def status_as_of(c, run, kind, eid, turn):
    r = c.execute(
        "SELECT to_status FROM status_transition WHERE run_id=? AND entity_kind=? AND entity_id=? "
        "AND turn_id<=? ORDER BY seq DESC LIMIT 1", (run, kind, eid, turn)).fetchone()
    return r["to_status"] if r else None


def dump(db: str, run: Optional[str] = None, turn: Optional[int] = None) -> dict:
    c = _conn(db)
    run = run or latest_run(c)
    if not run:
        print("no runs in store"); return {}
    if turn is None:
        turn = c.execute("SELECT MAX(turn_id) t FROM turn_record WHERE run_id=?", (run,)).fetchone()["t"] or 0

    refs = c.execute(
        "SELECT ref_id, kind, signature FROM referent WHERE run_id=? AND created_turn<=? AND "
        "version=(SELECT MAX(version) FROM referent r2 WHERE r2.run_id=referent.run_id "
        "AND r2.ref_id=referent.ref_id AND r2.created_turn<=?) GROUP BY ref_id",
        (run, turn, turn)).fetchall()
    ref_rows = []
    for r in refs:
        rung = status_as_of(c, run, "REFERENT_RUNG", r["ref_id"], turn) or "ANCHORED"
        inter = c.execute("SELECT COUNT(*) n FROM consequence_record WHERE run_id=? AND target_ref=? "
                          "AND turn_id<=?", (run, r["ref_id"], turn)).fetchone()["n"]
        ref_rows.append((r["ref_id"], r["kind"], rung, inter))

    goals = c.execute(
        "SELECT goal_id, parent_goal, statement, reopen_class FROM goal WHERE run_id=? AND created_turn<=? "
        "AND version=(SELECT MAX(version) FROM goal g2 WHERE g2.run_id=goal.run_id "
        "AND g2.goal_id=goal.goal_id) GROUP BY goal_id ORDER BY goal_id", (run, turn)).fetchall()
    goal_rows = [(g["goal_id"], g["parent_goal"] or "-", status_as_of(c, run, "GOAL", g["goal_id"], turn),
                 g["reopen_class"], g["statement"][:40]) for g in goals]

    rules = c.execute("SELECT rule_id, template FROM rule WHERE run_id=? AND created_turn<=? "
                      "GROUP BY rule_id", (run, turn)).fetchall()
    rule_rows = [(r["rule_id"], status_as_of(c, run, "RULE", r["rule_id"], turn) or "HYPOTHESIS",
                  r["template"][:40]) for r in rules]

    commits = c.execute("SELECT commit_id, goal_id FROM commitment WHERE run_id=? AND created_turn<=?",
                        (run, turn)).fetchall()

    print(f"=== ARG store state — run {run[:24]} as of turn {turn} ===")
    print(f"\nREFERENTS ({len(ref_rows)}):  id | kind | rung | interactions")
    for rid, kind, rung, inter in ref_rows[:40]:
        print(f"  {rid} | {kind} | {rung} | {inter}")
    print(f"\nGOALS ({len(goal_rows)}):  id | parent | status | reopen | statement")
    for gid, par, st, ro, stmt in goal_rows:
        print(f"  {gid} | {par} | {st} | {ro} | {stmt}")
    print(f"\nRULES ({len(rule_rows)}):  id | status | template")
    for rid, st, t in rule_rows[:20]:
        print(f"  {rid} | {st} | {t}")
    print(f"\nCOMMITMENTS: {len(commits)}")
    rung_counts = {}
    for _, _, rung, _ in ref_rows:
        rung_counts[rung] = rung_counts.get(rung, 0) + 1
    print(f"\nGROUNDING: {rung_counts}")
    return {"referents": ref_rows, "goals": goal_rows, "rules": rule_rows, "grounding": rung_counts}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="arg_state.db")
    ap.add_argument("--run", default=None)
    ap.add_argument("--turn", type=int, default=None)
    a = ap.parse_args()
    dump(a.db, a.run, a.turn)


if __name__ == "__main__":
    main()
