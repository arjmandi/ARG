#!/usr/bin/env python3
"""ARG C4 tests — real shadow compile + the §8 metric table (review S4/S7).

- LIVE cell: ICR/GA/RGR/GDS computed from real agenda play; RGR uses the §8
  definition (CHARACTERIZED share among GOAL-BOUND referents).
- A-OFF cell (ARG_AGENDA=0): the Executive compiles a REAL shadow step per
  beat from the live store (never persisted/rendered/executed); drift metrics
  are defined against it (drift_ref=SHADOW) — no synthetic strings.
Run: uv run python tests/test_arg_metrics.py"""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["TESTING"] = "True"

import test_arg_agenda as TA  # noqa: E402  (shared loop scaffolding)

FAILS = []


def T(name, cond, detail=""):
    print(f"  [{'ok ' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def main() -> None:
    from agents.structs import GameAction

    def mk_env(state):
        def env(action):
            state["n"] += 1; n = state["n"]
            clicked_plate = action == GameAction.ACTION6 and \
                action.action_data.model_dump().get("x") == 1 and \
                action.action_data.model_dump().get("y") == 1
            if clicked_plate:
                state["score"] += 1
            st = "WIN" if n >= 7 else "NOT_FINISHED"
            body = {"frame": TA._grid_plate(9 if (state["score"] % 2) else 8), "state": st,
                    "score": state["score"], "levels_completed": 0,
                    "available_actions": [6] if st == "NOT_FINISHED" else [],
                    "guid": "g", "game_id": "ls20", "card_id": "c1"}
            r = MagicMock(); r.json.return_value = body; r.status_code = 200
            return r
        return env

    def good_actuator(answer_view, row, schema):
        return {"action": "ACTION6", "x": 1, "y": 1, "canary_echo": [], "raw": MagicMock()}

    # ================= LIVE cell =================
    os.environ.pop("ARG_AGENDA", None)
    s1, p1 = tempfile.mktemp(suffix=".db"), tempfile.mktemp(suffix=".db")
    agent_arg = TA._reload_arg(s1, p1, max_actions="8")
    agent_arg.seeds.write_seeds = TA._seeder_with_plan("R0003")
    a1 = TA._run_loop(agent_arg, ["metrics-live"], mk_env({"n": 0, "score": 0}),
                      actuator=good_actuator)
    import probe_arg_metrics
    import importlib
    importlib.reload(probe_arg_metrics)
    mt = probe_arg_metrics.compute(s1, p1, a1._run_id)
    T("LIVE: ICR computed (steps consumed / written)", mt["ICR"] == 1.0, str(mt["ICR"]))
    T("LIVE: RGR is the §8 definition — CHARACTERIZED share among GOAL-BOUND",
      mt["goal_bound_referents"] >= 1 and mt["RGR"] == 1.0,
      f"bound={mt['goal_bound_referents']} rgr={mt['RGR']}")
    T("LIVE: GA computed over the binding closure", mt["GA"] is not None and 0 < mt["GA"] <= 1,
      str(mt["GA"]))
    T("LIVE: GDS metrics defined (drift_ref beats > 0, zero drift under obedience)",
      mt["drift_ref_beats"] >= 1 and mt["gds_bind"] == 0.0 and mt["gds_abandon"] == 0.0,
      f"beats={mt['drift_ref_beats']}")
    T("LIVE: decision mix carries agenda stamps", "ACTUATOR_LLM" in mt["decision_mix"])
    T("LIVE: per-organ WER + SRR + ECR + DPR keys computed",
      all(k in mt for k in ("wer_per_organ", "SRR", "ECR", "DPR", "FBR", "FCR", "FSN",
                            "DTL", "SCL", "APR", "tokens_vs_beat_slope")))
    pq = sqlite3.connect(p1)
    T("LIVE: llm_calls carries ops accounting columns",
      pq.execute("SELECT COALESCE(SUM(ops_accepted+ops_rejected),0) FROM llm_calls").fetchone()[0] >= 0)
    T("LIVE: actuator render_tokens stamped per call (R9 authority)",
      pq.execute("SELECT COUNT(*) FROM llm_calls WHERE organ='actuator' AND render_tokens>0",
                 ).fetchone()[0] >= 1)
    pq.close()

    # ================= A-OFF cell (real shadow compile) =================
    os.environ["ARG_AGENDA"] = "0"
    s2, p2 = tempfile.mktemp(suffix=".db"), tempfile.mktemp(suffix=".db")
    agent_arg = TA._reload_arg(s2, p2, max_actions="8")
    agent_arg.seeds.write_seeds = TA._seeder_with_plan("R0003")
    a2 = TA._run_loop(agent_arg, ["metrics-shadow"], mk_env({"n": 0, "score": 0}),
                      actuator=good_actuator)
    os.environ.pop("ARG_AGENDA", None)
    m2 = sqlite3.connect(s2); m2.row_factory = sqlite3.Row
    rid2 = a2._run_id
    sh = m2.execute("SELECT shadow_step_id FROM turn_record WHERE run_id=? AND "
                    "shadow_step_id IS NOT NULL LIMIT 1", (rid2,)).fetchone()
    T("SHADOW: a REAL compiled shadow step is stamped (leaf|action|target|rule)",
      sh is not None and sh["shadow_step_id"].count("|") == 3
      and "ACTION6" in sh["shadow_step_id"] and "R0003" in sh["shadow_step_id"],
      str(sh["shadow_step_id"] if sh else None))
    T("SHADOW: agenda never persists in A-off cells (no commitments)",
      m2.execute("SELECT COUNT(*) c FROM commitment WHERE run_id=?", (rid2,)).fetchone()["c"] == 0)
    T("SHADOW: drift_ref stamped SHADOW",
      m2.execute("SELECT COUNT(*) c FROM turn_record WHERE run_id=? AND drift_ref='SHADOW' AND "
                 "action != 'RESET'", (rid2,)).fetchone()["c"] >= 1)
    mt2 = probe_arg_metrics.compute(s2, p2, rid2)
    T("SHADOW: GDS metrics defined against the shadow reference",
      mt2["drift_ref_beats"] >= 1 and mt2["gds_bind"] is not None
      and mt2["gds_abandon"] is not None,
      f"beats={mt2['drift_ref_beats']} bind={mt2['gds_bind']} abandon={mt2['gds_abandon']}")
    T("SHADOW: ICR is None (no steps written) — the A-dimension separates",
      mt2["ICR"] is None and mt["ICR"] == 1.0)
    m2.close()

    print(f"\n{'PASS' if not FAILS else 'FAIL: ' + str(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
