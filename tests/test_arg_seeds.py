#!/usr/bin/env python3
"""ARG M2 seeds test: G0 + LEARN-* seeded correctly, game-agnostic, right
reopen_class. Run: uv run python tests/test_arg_seeds.py"""
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.arg.store import Store  # noqa: E402
from agents.arg import seeds  # noqa: E402

FAILS = []
# game nouns that must NEVER appear in a seed (generality contract)
BANNED = re.compile(r"\b(plate|door|key|wall|avatar|maze|energy|coin|hatch|box|sprite)\b", re.I)


def T(name, cond, detail=""):
    print(f"  [{'ok ' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def main() -> None:
    s = Store(tempfile.mktemp(suffix=".db"))
    rid = "seed-run"
    s.register_run(rid, "ls20", "sonnet", 0, "{}", 6000, "2026-07-17T00:00:00")
    ids = seeds.write_seeds(s, rid, turn_id=0)

    rows = s.conn.execute("SELECT * FROM goal WHERE run_id=? ORDER BY goal_id", (rid,)).fetchall()
    T("4 goals seeded (G0 + 3 LEARN-*)", len(rows) == 4, str(len(rows)))

    g0 = next(r for r in rows if r["parent_goal"] is None)
    T("G0 is the parentless root", g0["statement"] == "win the game")
    T("G0 reopen_class MONOTONE_TERMINAL", g0["reopen_class"] == "MONOTONE_TERMINAL")
    test = json.loads(g0["achievement_test_json"])
    T("G0 test is disjunctive over progress signals",
      test["op"] == "OR" and any(a.get("channel") == "levels_completed" for a in test["args"])
      and any(a.get("value") == "WIN" for a in test["args"]))

    learn = [r for r in rows if r["parent_goal"] is not None]
    T("LEARN-* are RECORD_QUANTIFIED",
      all(r["reopen_class"] == "RECORD_QUANTIFIED" for r in learn))
    T("LEARN-* children of G0", all(r["parent_goal"] == ids["G0"] for r in learn))
    T("LEARN-* start PROPOSED", all(
        s.conn.execute("SELECT to_status FROM status_transition WHERE run_id=? AND entity_id=? "
                       "ORDER BY seq DESC LIMIT 1", (rid, r["goal_id"])).fetchone()["to_status"]
        == "PROPOSED" for r in learn))

    # generality: no game nouns anywhere in any seeded string
    blob = " ".join(r["statement"] + r["achievement_test_json"] + r["discriminator_json"]
                    for r in rows)
    hit = BANNED.search(blob)
    T("no game nouns in any seed (generality contract)", hit is None,
      f"found '{hit.group()}'" if hit else "")
    T("all seeds provenance SEEDED", all(r["provenance"] == "SEEDED" for r in rows))

    s.close()
    print(f"\n{'PASS' if not FAILS else 'FAIL: ' + str(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
