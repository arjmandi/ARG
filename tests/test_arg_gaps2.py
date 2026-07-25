#!/usr/bin/env python3
"""ARG D2 tests — coverage-gap items 5,12,13,14,15.

- #5 typed re-prompt: a rejected op earns ONE corrective re-prompt; corrected
  ops apply; still-rejected ops DROP with retry_count=1 (the DPR source).
- #12 Z4: global actions render once and prune per current regime; ACTION6
  pairs scope to the active chain's bindings when bound.
- #13 Observer log tail: turn_id-keyed, ≤ L turns, carries the pre-committed
  prediction + Executive match.
- #14 C_max: the changeset lists THIS beat's changed refs, paginated with an
  honest remainder line.
- #15 epoch caps: the per-level cap denies epochs (T1 exempt); level reset
  re-allows; cap scales with level index.
Run: uv run python tests/test_arg_gaps2.py"""
import importlib
import os
import re
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["TESTING"] = "True"

import test_arg_agenda as TA  # noqa: E402

FAILS = []


def T(name, cond, detail=""):
    print(f"  [{'ok ' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def main() -> None:
    from agents.structs import GameAction

    # ================= #15 epoch caps (unit) =================
    os.environ["ARG_EPOCH_CAP"] = "1"
    from agents.arg import config as cfg
    importlib.reload(cfg)
    importlib.reload(importlib.import_module("agents.arg.executive"))
    from agents.arg.executive import EpochController
    ec = EpochController()
    f1, t1 = ec.check(20, False, False, True, False, level_index=0)
    T("#15: first epoch fires (T3)", f1 and t1 == "T3")
    ec.fired(20)
    f2, _ = ec.check(40, False, False, True, False, level_index=0)
    T("#15: per-level cap (base=1, level 0) denies the second epoch", not f2)
    T("#15: T1 remains exempt from the cap",
      ec.check(40, True, False, False, False, level_index=0) == (True, "T1"))
    f3, _ = ec.check(60, False, False, True, False, level_index=1)
    T("#15: cap scales with level index (level 1 → cap 2 → allowed)", f3)
    ec.level_reset()
    f4, _ = ec.check(80, False, False, True, False, level_index=0)
    T("#15: level reset re-allows", f4)
    os.environ.pop("ARG_EPOCH_CAP", None)
    importlib.reload(cfg)

    # ================= loop run: #5 retry, #13 tail, #14 pagination =================
    s1, p1 = tempfile.mktemp(suffix=".db"), tempfile.mktemp(suffix=".db")
    os.environ["ARG_C_MAX"] = "3"          # tiny page so pagination triggers
    os.environ["ARG_L"] = "4"              # tiny tail so the window binds
    agent_arg = TA._reload_arg(s1, p1, max_actions="8")
    calls = {"n": 0, "changesets": [], "tails": []}

    def observer(changeset, log_tail, view):
        calls["n"] += 1
        calls["changesets"].append(changeset)
        calls["tails"].append(log_tail)
        echo = re.findall(r"ZQ[0-9a-f]{8}", view)
        if "REJECTED" in changeset:
            # the corrective round: emit ONE valid op + keep one bad → DROP
            ids = re.findall(r"R\d{4}", view)
            return {"ops": [{"op": "INTERPRET", "ref": ids[0] if ids else "R0001",
                             "label": "fixed"},
                            {"op": "INTERPRET", "ref": "R9999", "label": "still-bad"}],
                    "canary_echo": echo, "raw": MagicMock()}
        # first round: one valid + one dangling → triggers the re-prompt
        ids = re.findall(r"R\d{4}", view)
        return {"ops": [{"op": "ANNOTATE", "text": "seen"},
                        {"op": "INTERPRET", "ref": "R9999", "label": "bad"}],
                "canary_echo": echo, "raw": MagicMock()}

    agent_arg.organs.configure_llm = lambda *a, **k: None
    agent_arg.organs.run_observer = observer
    agent_arg.organs.run_surveyor = lambda t, v, b: {
        "proposals": [], "canary_echo": re.findall(r"ZQ[0-9a-f]{8}", v), "raw": MagicMock()}

    # a busy world: 6 one-cell blinkers so >C_max refs change per beat
    def grid(n):
        g = [[0] * 8 for _ in range(8)]
        for i in range(6):
            g[1][1 + i] = (i + n) % 9 + 1
        return [g]

    st = {"n": 0}

    def env(action):
        st["n"] += 1; n = st["n"]
        state = "WIN" if n >= 7 else "NOT_FINISHED"
        body = {"frame": grid(n), "state": state, "score": 0, "levels_completed": 0,
                "available_actions": [1, 6] if state == "NOT_FINISHED" else [],
                "guid": "g", "game_id": "ls20", "card_id": "c1"}
        r = MagicMock(); r.json.return_value = body; r.status_code = 200
        return r
    a1 = TA._mk_agent(agent_arg, ["d2"])
    agent_arg.Agent.do_action_request = lambda self, action: env(action)
    a1.main()

    m = sqlite3.connect(s1); m.row_factory = sqlite3.Row
    rid = a1._run_id
    # #5 retry: corrective round happened; corrected op applied; drop metered
    T("#5: rejected op earned ONE corrective re-prompt",
      any("REJECTED" in c for c in calls["changesets"]))
    T("#5: corrected op APPLIED after the re-prompt",
      m.execute("SELECT COUNT(*) c FROM referent_alias WHERE run_id=? AND label='fixed'",
                (rid,)).fetchone()["c"] >= 1)
    r0 = m.execute("SELECT COUNT(*) c FROM write_reject WHERE run_id=? AND retry_count=0 "
                   "AND organ='OBSERVER'", (rid,)).fetchone()["c"]
    r1 = m.execute("SELECT COUNT(*) c FROM write_reject WHERE run_id=? AND retry_count=1 "
                   "AND organ='OBSERVER'", (rid,)).fetchone()["c"]
    T("#5: still-rejected op DROPPED with retry_count=1 (DPR marker)", r0 >= 1 and r1 >= 1,
      f"r0={r0} r1={r1}")
    import probe_arg_metrics
    importlib.reload(probe_arg_metrics)
    mt = probe_arg_metrics.compute(s1, p1, rid)
    T("#5: DPR computed from drop markers", mt["DPR"] is not None and mt["DPR"] > 0,
      str(mt["DPR"]))
    # #14 pagination
    first_pages = [c for c in calls["changesets"] if "CHANGED THIS BEAT" in c
                   and "REJECTED" not in c]
    T("#14: changeset lists THIS beat's changed refs, paginated at C_max",
      any("+2 more changed" in c or "more changed" in c for c in first_pages),
      first_pages[1][:120].replace("\n", " | ") if len(first_pages) > 1 else "")
    T("#14: page size respected (≤ C_max entries)",
      all(c.count("sig=") <= 3 for c in first_pages))
    # #13 log tail
    later_tails = [t for t in calls["tails"] if t != "(no prior turns)"]
    T("#13: Observer tail is turn_id-keyed with prediction+match fields",
      any(re.search(r"t\d+ ACTION\d", t) and "predicted=" in t and "match=" in t
          for t in later_tails), (later_tails[-1][-140:] if later_tails else ""))
    T("#13: tail bounded at L turns", all(len(t.splitlines()) <= 4 for t in later_tails))
    m.close()
    os.environ.pop("ARG_C_MAX", None)
    os.environ.pop("ARG_L", None)

    # ================= #12 Z4 scope + pruning (unit) =================
    from agents.arg import config as cfg2
    importlib.reload(cfg2)
    for mod in ("store", "executive", "seeds", "renderer"):
        importlib.reload(importlib.import_module(f"agents.arg.{mod}"))
    from agents.arg import store as st4, executive as ex4, seeds as sd4, renderer as rd4
    from agents.arg.adapter import ARCAdapter, Component
    s4 = st4.Store(tempfile.mktemp(suffix=".db"))
    s4.register_run("z4", "ls20", "m", 0, "{}", 6000, "t")
    e4 = ex4.Executive(s4, ARCAdapter(), "z4")
    ids = sd4.write_seeds(s4, "z4", 0)
    ra = e4.mint_referent(Component(color=5, cells=frozenset([(1, 1)]), bbox=(1, 1, 1, 1),
                                    centroid=(1, 1), size=1, shape=frozenset([(0, 0)])), 1)
    rb = e4.mint_referent(Component(color=6, cells=frozenset([(3, 3)]), bbox=(3, 3, 3, 3),
                                    centroid=(3, 3), size=1, shape=frozenset([(0, 0)])), 1)
    s4.commit()
    r4 = rd4.Renderer(s4, e4, "z4", None)
    head = {"turn": 2, "level": 0, "score": 0}
    z4a = r4.budgeted_view(head, [[0] * 8 for _ in range(8)], ["ACTION1", "ACTION6"])["zones"]["Z4"]
    T("#12: unbound scope → both referents' ACTION6 pairs + the global action",
      f"{ra} × ACTION6" in z4a and f"{rb} × ACTION6" in z4a and "ACTION1 (global)" in z4a)
    # a receipt for ACTION1 in the current regime prunes the global line
    cc = e4.current_context_class(0, 3)
    e4.write_consequence(3, "ACTION1", None, cc, {"cells_changed": 0})
    # bind ra to the leaf's chain → ACTION6 pairs scope to ra only
    e4.bind_goal_ref(ids["G0"], ra)
    s4.commit()
    z4b = r4.budgeted_view(head, [[0] * 8 for _ in range(8)], ["ACTION1", "ACTION6"])["zones"]["Z4"]
    T("#12: global action pruned once receipted in the current regime",
      "ACTION1 (global)" not in z4b)
    T("#12: ACTION6 pairs scoped to the active chain's bindings",
      f"{ra} × ACTION6" in z4b and f"{rb} × ACTION6" not in z4b, z4b.replace("\n", " | "))
    s4.close()

    print(f"\n{'PASS' if not FAILS else 'FAIL: ' + str(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
