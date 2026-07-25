#!/usr/bin/env python3
"""ARG D4 tests — coverage-gap item 16 (the measurement bundle).

- bare/raw comparators: pinned protocol — ONE call per action, minimal
  template (raw adds full history); registered as argbare/argraw; probe-logged.
- B-CACHE: one decision call per beat over the substituted Z1+Z2+Z5; rungs
  freeze at ANCHORED; no goals/commitments.
- ZCR→R6 LIVE trigger: zone-differential echo failure flips the renderer to
  the compact tier (uniform failure stays Q11/INVALID territory).
- gate 6: Σ|bindings| > N_max is inadmissible (GATE6_BINDING_BUDGET).
- golden renders: zones byte-compared against tests/golden_arg_renders.json
  (ARG_GOLDEN_REGEN=1 to re-pin).
- HRT mismatch-by-stamp column + metrics length bins compute.
Run: uv run python tests/test_arg_gaps4.py"""
import importlib
import json
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
GOLDEN = Path(__file__).resolve().parent / "golden_arg_renders.json"


def T(name, cond, detail=""):
    print(f"  [{'ok ' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def main() -> None:
    from agents.structs import GameAction

    # ================= comparators: bare + raw =================
    from agents import AVAILABLE_AGENTS
    T("bare/raw registered as agents",
      "argbare" in AVAILABLE_AGENTS and "argraw" in AVAILABLE_AGENTS)
    p1 = tempfile.mktemp(suffix=".db")
    os.environ["ARG_PROBE_PATH"] = p1
    os.environ["SENSI_MAX_ACTIONS"] = "6"
    from agents.arg import config as cfg
    importlib.reload(cfg)
    from agents.arg import baselines, organs, probe_db
    importlib.reload(probe_db)
    importlib.reload(baselines)
    views = []
    baselines.organs.configure_llm = lambda *a, **k: None
    baselines.organs.run_baseline = lambda v: (views.append(v) or
                                               {"action": "ACTION1", "x": 0, "y": 0,
                                                "raw": MagicMock()})
    agent = baselines.RAW.__new__(baselines.RAW)
    baselines.RAW.__init__(agent, card_id="c1", game_id="ls20", agent_name="argraw",
                           ROOT_URL="http://mock", record=False, tags=["cmp"])
    st = {"n": 0}

    def env(action):
        st["n"] += 1; n = st["n"]
        state = "WIN" if n >= 6 else "NOT_FINISHED"
        body = {"frame": TA._grid_plate(9 if n % 2 else 8), "state": state,
                "score": n // 2, "levels_completed": 0,
                "available_actions": [1, 6] if state == "NOT_FINISHED" else [],
                "guid": "g", "game_id": "ls20", "card_id": "c1"}
        r = MagicMock(); r.json.return_value = body; r.status_code = 200
        return r
    baselines.Agent.do_action_request = lambda self, action: env(action)
    agent.get_scorecard = lambda: MagicMock(model_dump=lambda: {})
    agent.main()
    pq = sqlite3.connect(p1); pq.row_factory = sqlite3.Row
    rid = agent._run_id
    n_api = pq.execute("SELECT COUNT(*) c FROM api_log WHERE run_id=?", (rid,)).fetchone()["c"]
    n_llm = pq.execute("SELECT COUNT(*) c FROM llm_calls WHERE run_id=? AND organ='baseline'",
                       (rid,)).fetchone()["c"]
    T("pinned cadence: exactly ONE LLM call per emitted (non-RESET) action",
      n_llm == n_api - 1, f"api={n_api} llm={n_llm}")
    T("the pinned template carries render + header + instruction",
      views and "FRAME (hex colors" in views[0] and "score=" in views[0]
      and "verified progress" in views[0])
    T("RAW carries the FULL untyped history at the same cadence",
      any("FULL HISTORY" in v for v in views[1:]), str(len(views)))
    T("no ARG structure anywhere in the comparator view",
      all("ROSTER" not in v and "GOAL CARD" not in v and "«R:" not in v for v in views))
    pq.close()

    # ================= B-CACHE cell =================
    s2, p2 = tempfile.mktemp(suffix=".db"), tempfile.mktemp(suffix=".db")
    os.environ["ARG_BASELINE"] = "bcache"
    agent_arg = TA._reload_arg(s2, p2, max_actions="6")
    agent_arg.seeds.write_seeds = TA._seeder_with_plan("R0003")   # a TESTED rule exists…
    agent_arg.organs.configure_llm = lambda *a, **k: None
    agent_arg.organs.run_baseline = lambda v: {"action": "ACTION6", "x": 1, "y": 1,
                                               "raw": MagicMock()}
    a2 = TA._mk_agent(agent_arg, ["bcache"])
    st2 = {"n": 0, "score": 0}

    def env2(action):
        st2["n"] += 1; n = st2["n"]
        if action == GameAction.ACTION6:
            st2["score"] += 1
        state = "WIN" if n >= 5 else "NOT_FINISHED"
        body = {"frame": TA._grid_plate(9 if st2["score"] % 2 else 8), "state": state,
                "score": st2["score"], "levels_completed": 0,
                "available_actions": [6] if state == "NOT_FINISHED" else [],
                "guid": "g", "game_id": "ls20", "card_id": "c1"}
        r = MagicMock(); r.json.return_value = body; r.status_code = 200
        return r
    agent_arg.Agent.do_action_request = lambda self, action: env2(action)
    a2.main()
    os.environ.pop("ARG_BASELINE", None)
    m2 = sqlite3.connect(s2); m2.row_factory = sqlite3.Row
    rid2 = a2._run_id
    T("B-CACHE: decisions are ACTUATOR_LLM one-per-beat (no probes needed)",
      m2.execute("SELECT COUNT(*) c FROM turn_record WHERE run_id=? AND "
                 "source_stamp='ACTUATOR_LLM'", (rid2,)).fetchone()["c"] >= 3)
    T("B-CACHE: goal machinery OFF (no commitments despite the TESTED rule)",
      m2.execute("SELECT COUNT(*) c FROM commitment WHERE run_id=?", (rid2,)).fetchone()["c"] == 0)
    T("B-CACHE: consequence gating OFF — rungs FREEZE at ANCHORED",
      m2.execute("SELECT COUNT(*) c FROM status_transition WHERE run_id=? AND "
                 "entity_kind='REFERENT_RUNG' AND to_status IN ('ENGAGED','CHARACTERIZED')",
                 (rid2,)).fetchone()["c"] == 0)
    m2.close()

    # ================= ZCR zone-differential → R6 compact (live trigger) =================
    s3, p3 = tempfile.mktemp(suffix=".db"), tempfile.mktemp(suffix=".db")
    os.environ["ARG_K_CANARY"] = "1"
    os.environ["ARG_C"] = "2"          # fast epochs → ≥3 salted surveyor calls
    agent_arg = TA._reload_arg(s3, p3, max_actions="12")
    compact_seen = {"n": 0}

    def observer3(cs, lt, view):
        # echo Z2's canary but never Z3/Z6-class ones... Observer is salted Z2
        # only, so use the SURVEYOR to create the differential instead.
        return {"ops": [], "canary_echo": re.findall(r"ZQ[0-9a-f]{8}", view),
                "raw": MagicMock()}

    def surveyor3(trigger, view, buckets):
        if "RENDER:" in view and "working-set region joins" in view \
                and not any(ch in view for ch in ("00000000",)):
            compact_seen["n"] += 1
        # echo ONLY the Z2 canary → Z3/Z6 rates fall → zone-differential
        z2 = re.findall(r"\[Z2-CANARY (ZQ[0-9a-f]{8})\]", view)
        return {"proposals": [], "canary_echo": z2, "raw": MagicMock()}
    agent_arg.organs.configure_llm = lambda *a, **k: None
    agent_arg.organs.run_observer = observer3
    agent_arg.organs.run_surveyor = surveyor3
    a3 = TA._mk_agent(agent_arg, ["zcr-diff"])
    st3 = {"n": 0}

    def env3(action):
        st3["n"] += 1; n = st3["n"]
        state = "WIN" if n >= 11 else "NOT_FINISHED"
        body = {"frame": TA._grid_plate(9 if n % 2 else 8), "state": state, "score": 0,
                "levels_completed": 0, "available_actions": [6] if state == "NOT_FINISHED" else [],
                "guid": "g", "game_id": "ls20", "card_id": "c1"}
        r = MagicMock(); r.json.return_value = body; r.status_code = 200
        return r
    agent_arg.Agent.do_action_request = lambda self, action: env3(action)
    a3.main()
    os.environ.pop("ARG_K_CANARY", None)
    os.environ.pop("ARG_C", None)
    T("ZCR→R6: zone-differential failure flips the LIVE compact fallback",
      a3._force_compact is True)
    import probe_arg_legibility
    importlib.reload(probe_arg_legibility)
    lb3 = probe_arg_legibility.verify(s3, p3, a3._run_id)
    T("ZCR→R6: differential (not uniform) → run stays VALID; rot is a health matter",
      lb3["zcr_uniform_fail"] is False, str(lb3["zcr_rates"]))

    # ================= gate 6 (N_max) =================
    os.environ["ARG_N_MAX"] = "2"
    from agents.arg import config as cfg6
    importlib.reload(cfg6)
    for mod in ("store", "executive", "seeds"):
        importlib.reload(importlib.import_module(f"agents.arg.{mod}"))
    from agents.arg.store import Store
    from agents.arg.executive import Executive
    from agents.arg.adapter import ARCAdapter, Component
    s6 = Store(tempfile.mktemp(suffix=".db"))
    s6.register_run("g6", "ls20", "m", 0, "{}", 6000, "t")
    e6 = Executive(s6, ARCAdapter(), "g6")
    s6.conn.execute("INSERT INTO goal VALUES ('g6','GR',1,NULL,'root','{}','{}',"
                    "'MONOTONE_TERMINAL',NULL,200,3,'SEEDED',0,0)")
    refs = []
    for i in range(3):
        refs.append(e6.mint_referent(
            Component(color=5, cells=frozenset([(i, 0)]), bbox=(i, 0, i, 0), centroid=(i, 0),
                      size=1, shape=frozenset([(0, 0)])), 1))
    s6.commit()
    res6 = e6.admit_goal({"statement": "too many", "bindings": refs,
                          "achievement_test": {"op": "GT", "channel": "score", "vs": "prev"},
                          "discriminator": {"d": 1}, "evidence_ptrs": [1]}, 2, parent="GR")
    T("gate 6: Σ|bindings| > N_max is INADMISSIBLE (GATE6_BINDING_BUDGET)",
      res6["reason"] == "GATE6_BINDING_BUDGET", str(res6))
    os.environ.pop("ARG_N_MAX", None)
    importlib.reload(cfg6)

    # ================= golden renders =================
    for mod in ("store", "executive", "seeds", "renderer"):
        importlib.reload(importlib.import_module(f"agents.arg.{mod}"))
    from agents.arg import store as stG, executive as exG, seeds as sdG, renderer as rdG
    sG = stG.Store(tempfile.mktemp(suffix=".db"))
    sG.register_run("gold", "ls20", "m", 0, "{}", 6000, "t")
    eG = exG.Executive(sG, ARCAdapter(), "gold")
    idsG = sdG.write_seeds(sG, "gold", 0)
    plate = eG.mint_referent(Component(color=7, cells=frozenset([(1, 1)]), bbox=(1, 1, 1, 1),
                                       centroid=(1, 1), size=1, shape=frozenset([(0, 0)])), 1)
    eG.bind_goal_ref(idsG["G0"], plate)
    sG.commit()
    bvG = rdG.Renderer(sG, eG, "gold", None).budgeted_view(
        {"turn": 3, "level": 0, "score": 0}, [[0] * 8 for _ in range(8)], ["ACTION1", "ACTION6"])
    zonesG = bvG["zones"]
    if os.environ.get("ARG_GOLDEN_REGEN") == "1" or not GOLDEN.exists():
        GOLDEN.write_text(json.dumps(zonesG, indent=1, sort_keys=True))
        T("golden renders (re)pinned", GOLDEN.exists(), str(GOLDEN.name))
    else:
        gold = json.loads(GOLDEN.read_text())
        diffs = [z for z in ("Z1", "Z2", "Z3", "Z4", "Z5", "Z6") if gold.get(z) != zonesG.get(z)]
        T("golden renders byte-identical across all six zones", diffs == [], str(diffs))
    sG.close()

    # ================= HRT column + metrics bins compute =================
    import probe_arg_hrt, probe_arg_metrics
    importlib.reload(probe_arg_hrt); importlib.reload(probe_arg_metrics)
    hr = probe_arg_hrt.hrt(s2, p2, rid2)
    T("HRT: mismatch-by-stamp column present",
      "mismatch_by_stamp" in hr and "ACTUATOR_LLM" in hr["mismatch_by_stamp"])
    mt = probe_arg_metrics.compute(s2, p2, rid2)
    T("metrics: length-stratified bins compute",
      "bins" in mt and mt["bins"]["1-50"] is not None and "decision_accuracy" in mt["bins"]["1-50"],
      str(mt["bins"]["1-50"]))

    print(f"\n{'PASS' if not FAILS else 'FAIL: ' + str(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
