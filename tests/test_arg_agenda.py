#!/usr/bin/env python3
"""ARG C2 tests — the agenda ACTS (the review's S1 blocker).

The buildplan M5 live criterion the old suite was blind to: "a written
intention becomes a Commitment obeyed from the next beat." A custom seeder
injects a TESTED rule + a referent-bound subgoal; the REAL loop must walk to
the leaf, compile a Commitment (with premise closure + prediction), realize
the ACTION6 parameter through the Actuator behind R8, execute with a
COMMITMENT_STEP/ACTUATOR_LLM stamp, consume-on-success, and move the goal
PROPOSED→EXPLORED→VALIDATED→ACCEPTED. Plus: R8 retry→FALLBACK, substitution
caught (no receipt against the step's target), premise auto-block, lease
expiry. Run: uv run python tests/test_arg_agenda.py"""
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["TESTING"] = "True"

FAILS = []


def T(name, cond, detail=""):
    print(f"  [{'ok ' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def _reload_arg(store_db, probe_db, max_actions="10", lease=None):
    os.environ["ARG_STORE_PATH"] = store_db
    os.environ["ARG_PROBE_PATH"] = probe_db
    os.environ["SENSI_MAX_ACTIONS"] = max_actions
    if lease:
        os.environ["ARG_LEASE"] = lease
    else:
        os.environ.pop("ARG_LEASE", None)
    from agents.arg import config as cfg
    importlib.reload(cfg)
    for mod in ("store", "probe_db", "executive", "pather", "seeds", "renderer", "organs",
                "predicates", "agent_arg"):
        importlib.reload(importlib.import_module(f"agents.arg.{mod}"))
    from agents.arg import agent_arg
    return agent_arg


def _mk_agent(agent_arg, tags):
    a = agent_arg.ARG.__new__(agent_arg.ARG)
    agent_arg.ARG.__init__(a, card_id="c1", game_id="ls20", agent_name="arg",
                           ROOT_URL="http://mock", record=False, tags=tags)
    a.get_scorecard = lambda: MagicMock(model_dump=lambda: {})
    return a


def _grid_plate(fill, score_flash=False):
    """bg + 4x4 block + 1-cell plate at (1,1). First-frame segment order:
    bg → R0001, block → R0002, plate → R0003."""
    g = [[0] * 8 for _ in range(8)]
    for y in range(4, 8):
        for x in range(4, 8):
            g[y][x] = fill
    g[1][1] = 7
    return [g]


def _seeder_with_plan(target_ref):
    """A seeder that writes G0 + a target-bound subgoal + a TESTED rule whose
    effect advances the subgoal's test — the state a run reaches after
    discovery; the loop must now DO."""
    def seed(store, run_id, turn_id=0):
        from agents.arg import seeds as real_seeds
        os.environ["ARG_SEEDS"] = "1"
        c = store.conn
        g0 = store.mint_id(run_id, "G", 4)
        c.execute("INSERT INTO goal VALUES (?,?,1,NULL,'win the game',?,?, 'MONOTONE_TERMINAL',"
                  "NULL,200,3,'SEEDED',0,0)",
                  (run_id, g0, json.dumps(real_seeds.G0_TEST), json.dumps({"any": True})))
        real_seeds._status(store, run_id, 0, "GOAL", g0, None, "VALIDATED", "seeded root")
        sub = store.mint_id(run_id, "G", 4)
        c.execute("INSERT INTO goal VALUES (?,?,1,?,?,?,?, 'MONOTONE_TERMINAL',NULL,200,3,"
                  "'SEEDED',0,0)",
                  (run_id, sub, g0, "trigger a score event via the plate",
                   json.dumps({"op": "GT", "channel": "score", "vs": "prev"}),
                   json.dumps({"score_rises": True})))
        real_seeds._status(store, run_id, 0, "GOAL", sub, None, "PROPOSED", "seeded sub")
        c.execute("INSERT INTO goal_binding VALUES (?,?,1,?)", (run_id, sub, target_ref))
        ru = store.mint_id(run_id, "RU", 4)
        c.execute("INSERT INTO rule VALUES (?,?,1,?,?,?,'UNKNOWN',NULL,'seeded',0)",
                  (run_id, ru, "click the plate scores",
                   json.dumps({"action": "ACTION6", "target": target_ref}),
                   json.dumps({"score_event": 1, "cells_changed": "nonzero"})))
        real_seeds._status(store, run_id, 0, "RULE", ru, None, "TESTED", "seeded tested")
        store.commit()
        return {"G0": g0, "SUB": sub, "RU": ru}
    return seed


def _run_loop(agent_arg, tags, fake_env, actuator=None):
    agent_arg.organs.configure_llm = lambda *a, **k: None
    agent_arg.organs.run_observer = lambda *a, **k: {"ops": [], "canary_echo": [], "raw": MagicMock()}
    agent_arg.organs.run_surveyor = lambda *a, **k: {"proposals": [], "canary_echo": [], "raw": MagicMock()}
    if actuator:
        agent_arg.organs.run_actuator = actuator
    agent = _mk_agent(agent_arg, tags)
    agent_arg.Agent.do_action_request = lambda self, action: fake_env(action)
    agent.main()
    return agent


def main() -> None:
    import sqlite3
    from agents.structs import GameAction

    # ================= scenario 1: the intention is OBEYED =================
    store_db, probe_db = tempfile.mktemp(suffix=".db"), tempfile.mktemp(suffix=".db")
    agent_arg = _reload_arg(store_db, probe_db, max_actions="8")
    agent_arg.seeds.write_seeds = _seeder_with_plan("R0003")
    st = {"n": 0, "score": 0}

    def env1(action):
        st["n"] += 1; n = st["n"]
        # a plate click (1,1) raises score AND flips the block; other actions no-op
        clicked_plate = action == GameAction.ACTION6 and \
            action.action_data.model_dump().get("x") == 1 and \
            action.action_data.model_dump().get("y") == 1
        if clicked_plate:
            st["score"] += 1
        state = "WIN" if n >= 7 else "NOT_FINISHED"
        fill = 9 if (st["score"] % 2) else 8
        body = {"frame": _grid_plate(fill), "state": state, "score": st["score"],
                "levels_completed": 0, "available_actions": [6] if state == "NOT_FINISHED" else [],
                "guid": "g", "game_id": "ls20", "card_id": "c1"}
        r = MagicMock(); r.json.return_value = body; r.status_code = 200
        return r

    def good_actuator(answer_view, row, schema):
        return {"action": "ACTION6", "x": 1, "y": 1, "canary_echo": [], "raw": MagicMock()}
    agent = _run_loop(agent_arg, ["agenda-1"], env1, actuator=good_actuator)

    m = sqlite3.connect(store_db); m.row_factory = sqlite3.Row
    rid = agent._run_id
    stamps = {r["source_stamp"] for r in m.execute(
        "SELECT DISTINCT source_stamp FROM turn_record WHERE run_id=?", (rid,))}
    T("LIVE: an action was emitted FROM the agenda (ACTUATOR_LLM stamp)",
      "ACTUATOR_LLM" in stamps, str(stamps))
    stepped = m.execute("SELECT COUNT(*) c FROM turn_record WHERE run_id=? AND "
                        "commitment_step_id IS NOT NULL", (rid,)).fetchone()["c"]
    T("LIVE: turn_record carries commitment_step_id", stepped > 0, str(stepped))
    consumed = m.execute("SELECT COUNT(*) c FROM status_transition WHERE run_id=? AND "
                         "entity_kind='COMMITMENT_STEP' AND to_status='CONSUMED'", (rid,)).fetchone()["c"]
    T("LIVE: consume-on-success (a step was CONSUMED on Executive-confirmed match)",
      consumed > 0, str(consumed))
    hist = [r["to_status"] for r in m.execute(
        "SELECT to_status FROM status_transition WHERE run_id=? AND entity_kind='GOAL' "
        "AND entity_id='G0002' ORDER BY seq", (rid,))]
    T("LIVE: goal walked PROPOSED→EXPLORED→VALIDATED→ACCEPTED",
      hist == ["PROPOSED", "EXPLORED", "VALIDATED", "ACCEPTED"], str(hist))
    prem = m.execute("SELECT COUNT(*) c FROM step_premise WHERE run_id=?", (rid,)).fetchone()["c"]
    T("LIVE: premise closure recorded (rule + binding + target)", prem >= 3, str(prem))
    rel = m.execute("SELECT COUNT(*) c FROM relevance_edge WHERE run_id=?", (rid,)).fetchone()["c"]
    T("LIVE: relevance_edges stamped by compilation", rel >= 2, str(rel))
    step_receipts = m.execute("SELECT COUNT(*) c FROM consequence_record WHERE run_id=? AND "
                              "predictor_kind='STEP' AND match=1", (rid,)).fetchone()["c"]
    T("LIVE: STEP receipts pre-registered + matched", step_receipts > 0)
    m.close()

    # ================= scenario 2: R8 retry → FALLBACK =================
    store2, probe2 = tempfile.mktemp(suffix=".db"), tempfile.mktemp(suffix=".db")
    agent_arg = _reload_arg(store2, probe2, max_actions="6")
    agent_arg.seeds.write_seeds = _seeder_with_plan("R0003")
    st.update({"n": 0, "score": 0})

    def bad_actuator(answer_view, row, schema):
        return {"action": "ACTION6", "x": 50, "y": 50, "canary_echo": [], "raw": MagicMock()}
    agent2 = _run_loop(agent_arg, ["agenda-2"], env1, actuator=bad_actuator)
    m2 = sqlite3.connect(store2); m2.row_factory = sqlite3.Row
    rid2 = agent2._run_id
    fb = m2.execute("SELECT COUNT(*) c FROM turn_record WHERE run_id=? AND source_stamp='FALLBACK'",
                    (rid2,)).fetchone()["c"]
    T("LIVE: R8 violations fall back deterministically (FALLBACK stamp)", fb > 0, str(fb))
    rej = m2.execute("SELECT COUNT(*) c FROM write_reject WHERE run_id=? AND organ='ACTUATOR' "
                     "AND violation_class='UNCONTAINED_PARAM'", (rid2,)).fetchone()["c"]
    T("LIVE: uncontained params metered as ACTUATOR WER (retry + final)", rej >= 2, str(rej))
    # fallback = the plate's only cell (1,1) → still consumed on match
    T("LIVE: fallback coordinate contained → step still consumable",
      m2.execute("SELECT COUNT(*) c FROM status_transition WHERE run_id=? AND "
                 "entity_kind='COMMITMENT_STEP' AND to_status='CONSUMED'", (rid2,)).fetchone()["c"] > 0)
    m2.close()

    # ================= scenario 3: substitution caught (ring target) =================
    store3, probe3 = tempfile.mktemp(suffix=".db"), tempfile.mktemp(suffix=".db")
    agent_arg = _reload_arg(store3, probe3, max_actions="6")
    # ring (8 cells around (3,3)) → R0002; inner 1-cell → R0003; rule targets the RING
    agent_arg.seeds.write_seeds = _seeder_with_plan("R0002")

    def _grid_ring(fill):
        g = [[0] * 8 for _ in range(8)]
        for x, y in ((2, 2), (3, 2), (4, 2), (2, 3), (4, 3), (2, 4), (3, 4), (4, 4)):
            g[y][x] = 5
        g[3][3] = fill    # the inner referent (changes so score/frames move)
        return [g]

    st3 = {"n": 0, "score": 0}

    def env3(action):
        st3["n"] += 1; n = st3["n"]
        clicked = action == GameAction.ACTION6
        if clicked:
            st3["score"] += 1
        state = "WIN" if n >= 5 else "NOT_FINISHED"
        body = {"frame": _grid_ring(9 if st3["score"] % 2 else 8), "state": state,
                "score": st3["score"], "levels_completed": 0,
                "available_actions": [6] if state == "NOT_FINISHED" else [],
                "guid": "g", "game_id": "ls20", "card_id": "c1"}
        r = MagicMock(); r.json.return_value = body; r.status_code = 200
        return r
    agent3 = _run_loop(agent_arg, ["agenda-3"], env3, actuator=bad_actuator)
    m3 = sqlite3.connect(store3); m3.row_factory = sqlite3.Row
    rid3 = agent3._run_id
    subs = m3.execute("SELECT step_target, landed_target FROM substitution_caught WHERE run_id=?",
                      (rid3,)).fetchall()
    T("LIVE: substitution caught (fallback centroid landed in the ring's hole)",
      len(subs) > 0 and subs[0]["step_target"] == "R0002" and subs[0]["landed_target"] == "R0003",
      str([dict(s) for s in subs[:2]]))
    misattributed = m3.execute(
        "SELECT COUNT(*) c FROM consequence_record cr JOIN substitution_caught sc "
        "ON sc.run_id=cr.run_id AND sc.turn_id=cr.turn_id WHERE cr.run_id=? AND "
        "cr.predictor_kind='STEP'", (rid3,)).fetchone()["c"]
    T("LIVE: NO receipt written against the step's target on substitution", misattributed == 0)
    T("LIVE: substituted step NOT consumed",
      m3.execute("SELECT COUNT(*) c FROM status_transition WHERE run_id=? AND "
                 "entity_kind='COMMITMENT_STEP' AND to_status='CONSUMED'", (rid3,)).fetchone()["c"] == 0)
    m3.close()

    # ================= unit: premise auto-block + lease expiry =================
    from agents.arg.store import Store
    from agents.arg.adapter import ARCAdapter, Component
    from agents.arg.executive import Executive
    s = Store(tempfile.mktemp(suffix=".db"))
    s.register_run("u2", "ls20", "m", 0, "{}", 6000, "t")
    exe = Executive(s, ARCAdapter(), "u2")
    ref = exe.mint_referent(Component(color=7, cells=frozenset([(1, 1)]), bbox=(1, 1, 1, 1),
                                      centroid=(1, 1), size=1, shape=frozenset([(0, 0)])), 1)
    ru = exe.add_rule(1, "r", {"action": "ACTION6", "target": ref}, {"score_event": 1})
    exe._append_status(1, "RULE", ru, "HYPOTHESIS", "TESTED", "t")
    s.conn.execute("INSERT INTO goal VALUES ('u2','GX',1,NULL,'x','{}','{}','MONOTONE_TERMINAL',"
                   "NULL,200,3,'SEEDED',0,0)")
    cid = exe.write_commitment("GX", [{"kind": "INTERACT", "action": "ACTION6", "target_ref": ref,
                                       "predicted": {"score_event": 1}}], 2, premise_rules=[ru])
    s.commit()
    step, flags = exe.next_executable_step(3)
    T("unit: compiled step is ACTIVE and executable", step is not None and not flags["lease_expired"])
    # demote the premise rule → auto-block
    exe._append_status(4, "RULE", ru, "TESTED", "DEMOTED", "contradicted")
    s.commit()
    step2, _ = exe.next_executable_step(5)
    T("unit: premise demotion auto-BLOCKS the step (cannot act on a dead belief)",
      step2 is None and exe.current_status("COMMITMENT_STEP", f"{cid}-S0") == "BLOCKED")
    # lease: a fresh commitment whose step burns its lease
    cid2 = exe.write_commitment("GX", [{"kind": "INTERACT", "action": "ACTION6", "target_ref": ref,
                                        "predicted": {"score_event": 1}}], 6)
    from agents.arg import config as cfg
    for i in range(cfg.LEASE_MAX_BEATS):
        exe.record_turn(100 + i, "ACTION6", {}, ref, "a", "b", {}, {}, 0, 0, "NOT_FINISHED",
                        None, "COMMITMENT_STEP", commitment_step_id=f"{cid2}-S0")
    s.commit()
    step3, flags3 = exe.next_executable_step(200)
    T("unit: lease expiry EXPIREs the step and raises the trigger flag",
      step3 is None and flags3["lease_expired"]
      and exe.current_status("COMMITMENT_STEP", f"{cid2}-S0") == "EXPIRED")
    s.close()

    print(f"\n{'PASS' if not FAILS else 'FAIL: ' + str(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
