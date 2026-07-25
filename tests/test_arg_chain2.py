#!/usr/bin/env python3
"""ARG G2 chain tests: chain-aware walk + deterministic auto-fill + milestone
experiment-commitments + DEFICIT stamps + the tool seam (cold-start delta 3).

Two bootstrap directions:
- OFFLINE POSITIVE: hypothesis rule → auto-filled milestone → experiment
  receipts match → rule TESTED → milestone ACCEPTED → parent COMPILABLE.
- LOOP NEGATIVE (ls20-realistic): false hypothesis → milestone compiled and
  EXECUTED (the first non-probe stamps) → mismatch receipts → rule DEMOTED →
  step premise auto-blocks → the chain re-opens honestly.

Run: uv run python tests/test_arg_chain2.py"""
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["TESTING"] = "True"
os.environ["SENSI_MAX_ACTIONS"] = "12"

FAILS = []
ROOT = Path(__file__).resolve().parent.parent


def T(name, cond, detail=""):
    print(f"  [{'ok ' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


CTX = {"cur": {"score": 0, "levels_completed": 0, "state": "NOT_FINISHED"},
       "prev": {"score": 0, "levels_completed": 0, "state": "NOT_FINISHED"}}


def tool_seam() -> None:
    print("-- tool seam: descriptors above the adapter, no name string-matching --")
    from agents.arg.adapter import ARCAdapter
    from agents.arg import pather
    ad = ARCAdapter()
    tools = ad.tools()
    byname = {t["name"]: t for t in tools}
    T("every actuate tool descriptor carries side/targeted/param_schema",
      all({"name", "side", "targeted", "param_schema"} <= set(t) for t in tools))
    T("ACTION6 is the targeted actuate tool with an aim schema",
      byname["ACTION6"]["targeted"] and byname["ACTION6"]["side"] == "actuate"
      and byname["ACTION6"]["param_schema"] == {"x": [0, 63], "y": [0, 63]})
    T("simple actions are untargeted", not byname["ACTION1"]["targeted"])
    T("the GET side is a descriptor too (observe)",
      byname["OBSERVE"]["side"] == "observe")
    T("targeted_actions() derives from descriptors", ad.targeted_actions() == {"ACTION6"})
    for fname in ("agents/arg/executive.py", "agents/arg/agent_arg.py", "agents/arg/pather.py"):
        src = (ROOT / fname).read_text()
        hits = [ln for ln in src.splitlines()
                if '"ACTION6"' in ln or "GameAction.ACTION6" in ln]
        T(f"no ACTION6 literal above the adapter in {fname}", not hits, str(hits[:2]))
    T("pather skips targeted tools via descriptors (no mover displacement)",
      pather.learn_action_model(None, "x", None, "ACTION6", [], [], 1,
                                targeted={"ACTION6"}) is None)
    T("pather skips the RESET protocol verb",
      pather.learn_action_model(None, "x", None, "RESET", [], [], 1, targeted=set()) is None)
    # containment attribution under NESTING: the most specific container wins
    # (tn36 artifact: first-by-id stamped the enclosing board, mis-attributing
    # 96 receipts and printing fake bind drift in every cell)
    from agents.arg.store import Store
    from agents.arg.executive import Executive
    from agents.arg.adapter import Component
    import tempfile as _tf
    s = Store(_tf.mktemp(suffix=".db"))
    s.register_run("nest", "ls20", "sonnet", 0, "{}", 6000, "t")
    exe = Executive(s, ad, "nest")
    big = exe.mint_referent(Component(color=1, cells=frozenset((x, y) for x in range(10)
                                                               for y in range(10)),
                                      bbox=(0, 0, 9, 9), centroid=(4, 4), size=100,
                                      shape=frozenset((x, y) for x in range(10)
                                                      for y in range(10))), 1)
    small = exe.mint_referent(Component(color=2, cells=frozenset({(4, 4), (4, 5)}),
                                        bbox=(4, 4, 4, 5), centroid=(4, 4), size=2,
                                        shape=frozenset({(0, 0), (0, 1)})), 1)
    s.commit()
    T("stamp_target attributes the MOST SPECIFIC containing referent",
      exe.stamp_target("ACTION6", {"x": 4, "y": 4}) == small
      and exe.stamp_target("ACTION6", {"x": 0, "y": 0}) == big)


def _fresh(rid):
    from agents.arg.store import Store
    from agents.arg.adapter import ARCAdapter
    from agents.arg.executive import Executive
    from agents.arg import seeds as sd
    s = Store(tempfile.mktemp(suffix=".db"))
    s.register_run(rid, "ls20", "sonnet", 0, "{}", 6000, "t")
    exe = Executive(s, ARCAdapter(), rid)
    ids = sd.write_seeds(s, rid, 0)
    return s, exe, ids


def milestone_compile() -> None:
    print("-- milestone experiment-commitments (compile toward HYPOTHESIS) --")
    from agents.arg.adapter import Component
    s, exe, ids = _fresh("mc")
    ref = exe.mint_referent(Component(color=7, cells=frozenset({(3, 3)}), bbox=(3, 3, 3, 3),
                                      centroid=(3, 3), size=1, shape=frozenset({(0, 0)})), 1)
    ru = exe.add_rule(2, "click plate scores", {"action": "ACTION6", "target": ref},
                      {"score_event": 1}, test_plan="p")
    mtest = {"op": "COUNT", "entity": "consequence",
             "where": {"predictor": ru, "match": 1}, "value": 2}
    r = exe.admit_goal({"statement": f"test {ru}", "bindings": [ref],
                        "achievement_test": mtest, "discriminator": {"d": 1},
                        "evidence_ptrs": [2], "provenance": "DEFICIT"}, 3, parent=ids["G0"])
    child = r["goal_id"]
    cid = exe.compile_plan(child, 4, CTX)
    T("milestone over a HYPOTHESIS rule compiles (experiment-commitment)", cid is not None)
    st = s.conn.execute("SELECT * FROM commitment_step WHERE run_id='mc' AND commit_id=?",
                        (cid,)).fetchone()
    T("single INTERACT step at the rule's (action, target)",
      st["kind"] == "INTERACT" and st["action"] == "ACTION6" and st["target_ref"] == ref)
    T("the rule's closed effect is the step prediction (B4a pre-registration)",
      json.loads(st["predicted_delta_json"]) == {"score_event": 1})
    prem = s.conn.execute("SELECT member_id FROM step_premise WHERE run_id='mc' AND "
                          "commit_id=? AND member_kind='RULE'", (cid,)).fetchone()
    T("the hypothesis rule is the step premise (auto-block on demotion)",
      prem and prem["member_id"] == ru)
    for tt in (5, 6, 7):
        exe.write_consequence(tt, "ACTION6", ref, "CC1", {"d": 0}, match=False,
                              predictor_id=ru, predictor_kind="RULE")
    exe.recompute_rule_status(ru, 8)
    s.commit()
    T("DEMOTED milestone rule no longer compiles", exe.compile_plan(child, 9, CTX) is None)
    # gen4 lessons: (i) milestone-SHAPED tests get experiment budgets whatever
    # the provenance; (ii) a target-scoped rule via an untargeted action with
    # no route is NOT exercisable — compiling it is the blind-commitment loop
    from agents.arg import config
    row = s.conn.execute("SELECT budget_actions FROM goal WHERE run_id='mc' AND goal_id=?",
                         (child,)).fetchone()
    T("milestone-shaped budget clamped to the promotion bar (not MAX_ACTIONS)",
      row["budget_actions"] == max(8, 6 * config.K_SUPPORT), str(row["budget_actions"]))
    ru2 = exe.add_rule(10, "walk into plate", {"action": "ACTION1", "target": ref},
                       {"level_event": 1}, test_plan="p")
    r2 = exe.admit_goal({"statement": f"test {ru2}", "bindings": [ref],
                         "achievement_test": {"op": "RULE_STATUS", "rule": ru2, "is": "TESTED"},
                         "discriminator": {"d": 1}, "evidence_ptrs": [10],
                         "provenance": "DEFICIT"}, 11, parent=ids["G0"])
    T("unexercisable milestone (untargeted action, target-scoped rule, no route) "
      "does not compile", exe.compile_plan(r2["goal_id"], 12, CTX) is None)
    T("and is not COMPILABLE to the recognizer (holes speak instead)",
      exe.chain_status(r2["goal_id"], CTX)["status"] != "COMPILABLE")


def bootstrap_positive() -> None:
    print("-- OFFLINE POSITIVE bootstrap: deficit → milestone → TESTED → parent compiles --")
    from agents.arg import config
    s, exe, ids = _fresh("bp")
    g0 = ids["G0"]
    ru = exe.add_rule(2, "A1 scores", {"action": "ACTION1"}, {"score_event": 1}, test_plan="p")
    s.commit()
    cs = exe.chain_status(g0, CTX)
    T("G0 DEFICIT with the hypothesis rule as derivable evidence",
      cs["status"] == "DEFICIT" and any(
          h["key"] == "score_event" and h["evidence"]["candidate_rules"] == [ru]
          for h in cs["holes"]))
    made = exe.auto_fill_holes(g0, cs["holes"], 3)
    T("auto-fill drafts exactly the derivable milestone", len(made) == 1)
    child = made[0]
    row = s.conn.execute("SELECT provenance, parent_goal, achievement_test_json FROM goal "
                         "WHERE run_id='bp' AND goal_id=?", (child,)).fetchone()
    T("provenance DEFICIT under the deficient parent (amendment A2)",
      row["provenance"] == "DEFICIT" and row["parent_goal"] == g0)
    T("milestone test = COUNT matched receipts ≥ k (the promotion bar)",
      json.loads(row["achievement_test_json"]) == {
          "op": "COUNT", "entity": "consequence",
          "where": {"predictor": ru, "match": 1}, "value": config.K_SUPPORT})
    edge = s.conn.execute("SELECT verified FROM goal_edge WHERE run_id='bp' AND "
                          "parent_goal=? AND child_goal=?", (g0, child)).fetchone()
    T("verified edge created by the mechanical fill proof", edge and edge["verified"] == 1)
    T("re-running auto-fill is a no-op (gate 4 holds the dedup)",
      exe.auto_fill_holes(g0, cs["holes"], 4) == [])
    T("the walk frontier is the milestone child (deepest compilable)",
      exe.chain_frontier(g0, CTX) == child)
    cid = exe.compile_plan(child, 5, CTX)
    T("frontier compiles the experiment-commitment", cid is not None)
    # execute the experiment twice with matching receipts (score fires)
    for tt in (6, 7):
        exe.write_consequence(tt, "ACTION1", None, "CC1", {"d": 1}, match=True,
                              predictor_id=ru, predictor_kind="RULE", score_event=1)
        exe.recompute_rule_status(ru, tt)
    s.commit()
    T("rule promoted TESTED by its own pre-registered receipts",
      exe.current_status("RULE", ru) == "TESTED")
    exe.evaluate_all_goals(8, CTX)
    s.commit()
    T("milestone ACCEPTED once the count reaches the bar",
      exe.current_status("GOAL", child) == "ACCEPTED")
    T("parent now COMPILABLE via the TESTED rule ('enough goals' → align and execute)",
      exe.chain_status(g0, CTX)["status"] == "COMPILABLE")
    T("parent compiles a real commitment", exe.compile_plan(g0, 9, CTX) is not None)


def stamps_and_frontier() -> None:
    print("-- DEFICIT stamps (deduped, append-only) + frontier depth --")
    import sqlite3
    s, exe, ids = _fresh("ds")
    g0 = ids["G0"]
    holes = exe.chain_status(g0, CTX)["holes"]
    T("first stamp writes", exe.deficit_stamp(g0, holes, 2) is True)
    T("identical re-stamp is suppressed", exe.deficit_stamp(g0, holes, 3) is False)
    T("changed holes stamp again", exe.deficit_stamp(g0, holes[:1], 4) is True)
    n = s.conn.execute("SELECT COUNT(*) c FROM deficit_stamp WHERE run_id='ds'").fetchone()["c"]
    T("stamp rows = distinct hole states", n == 2)
    od = exe.open_deficits()
    T("open_deficits serves the latest holes per live goal",
      len(od) == 1 and od[0]["goal_id"] == g0 and od[0]["holes"] == holes[:1])
    try:
        s.conn.execute("UPDATE deficit_stamp SET holes_json='[]' WHERE run_id='ds'")
        T("deficit_stamp is append-only", False)
    except sqlite3.DatabaseError as e:
        T("deficit_stamp is append-only", "append-only" in str(e))
    exe._append_status(5, "GOAL", g0, "VALIDATED", "ACCEPTED", "test")
    s.commit()
    T("stamps of terminal goals leave the open set", exe.open_deficits() == [])
    # frontier: grandchild depth + ACCEPTED skip
    s2, exe2, ids2 = _fresh("fr")
    g0 = ids2["G0"]
    ru = exe2.add_rule(2, "r", {"action": "ACTION2"}, {"level_event": 1}, test_plan="p")
    mtest = {"op": "COUNT", "entity": "consequence",
             "where": {"predictor": ru, "match": 1}, "value": 2}
    mid = exe2.admit_goal({"statement": "mid", "bindings": [],
                           "achievement_test": {"op": "GT", "channel": "levels_completed",
                                                "vs": "prev"},
                           "discriminator": {"d": 1}, "evidence_ptrs": [1]},
                          3, parent=g0)["goal_id"]
    leaf = exe2.admit_goal({"statement": f"test {ru}", "bindings": [],
                            "achievement_test": mtest, "discriminator": {"d": 1},
                            "evidence_ptrs": [2], "provenance": "DEFICIT"},
                           3, parent=mid)["goal_id"]
    exe2.add_goal_edge(g0, mid, {"keys": ["level_event"]}, True, 3)
    exe2.add_goal_edge(mid, leaf, {"keys": ["level_event"]}, True, 3)
    s2.commit()
    T("frontier finds the deepest compilable descendant (grandchild)",
      exe2.chain_frontier(g0, CTX) == leaf)
    exe2._append_status(4, "GOAL", leaf, "PROPOSED", "ACCEPTED", "test")
    s2.commit()
    T("ACCEPTED leaves are skipped (nothing to execute)",
      exe2.chain_frontier(g0, CTX) is None)


def loop_negative() -> None:
    print("-- LOOP: false hypothesis → executed milestone → demotion → honest re-open --")
    store_db = tempfile.mktemp(suffix=".db")
    probe_db = tempfile.mktemp(suffix=".db")
    os.environ["ARG_STORE_PATH"] = store_db
    os.environ["ARG_PROBE_PATH"] = probe_db

    import importlib
    from agents.arg import config as argcfg
    importlib.reload(argcfg)
    from agents.arg import store as argstore, probe_db as argprobe, executive as argexec
    importlib.reload(argstore); importlib.reload(argprobe); importlib.reload(argexec)
    from agents.arg import agent_arg
    importlib.reload(agent_arg)
    from agents.structs import FrameData, GameAction, GameState

    calls = {"obs": 0}

    def mock_observer(cs, lt, v):
        calls["obs"] += 1
        ops = []
        if calls["obs"] == 1:
            # a FALSE closed hypothesis: bare ACTION2 scores (it never does)
            ops = [{"op": "PROPOSE_RULE", "template": "ACTION2 scores",
                    "ctx": {"action": "ACTION2"}, "effect": {"score_event": 1}}]
        return {"ops": ops, "canary_echo": re.findall(r"ZQ[0-9a-f]{8}", v), "raw": MagicMock()}

    agent_arg.organs.configure_llm = lambda *a, **k: None
    agent_arg.organs.run_observer = mock_observer
    agent_arg.organs.run_surveyor = lambda t, v, b: {
        "proposals": [], "canary_echo": re.findall(r"ZQ[0-9a-f]{8}", v), "raw": MagicMock()}

    def _grid(fill):
        g = [[0] * 8 for _ in range(8)]
        for y in range(4, 8):
            for x in range(4, 8):
                g[y][x] = fill
        return [g]

    ARG = agent_arg.ARG
    agent = ARG.__new__(ARG)
    agent.card_id = "card-x"; agent.game_id = "ls20"; agent.guid = ""
    agent.agent_name = "arg"; agent.tags = ["g2-test"]; agent.frames = [FrameData(score=0)]
    agent._cleanup = True; agent.game_state = GameState.NOT_PLAYED
    agent.action_counter = 0
    ARG.__init__(agent, card_id="card-x", game_id="ls20", agent_name="arg",
                 ROOT_URL="http://mock", record=False, tags=["g2-test"])

    state = {"n": 0}

    def fake_request(action):
        state["n"] += 1
        body = {"frame": _grid(9 if state["n"] % 2 else 8), "state": "NOT_FINISHED",
                "score": 0, "levels_completed": 0, "available_actions": [1, 2, 3, 4, 6],
                "guid": "g1", "game_id": "ls20", "card_id": "card-x"}
        resp = MagicMock()
        resp.json.return_value = body
        resp.status_code = 200
        return resp

    agent_arg.Agent.do_action_request = lambda self, action: fake_request(action)
    agent.get_scorecard = lambda: MagicMock(model_dump=lambda: {"score": 0})
    agent.main()

    import sqlite3
    m = sqlite3.connect(store_db); m.row_factory = sqlite3.Row
    rid = agent._run_id

    ms = m.execute("SELECT * FROM goal WHERE run_id=? AND provenance='DEFICIT'",
                   (rid,)).fetchall()
    T("the walk auto-filled a DEFICIT milestone from the live hypothesis",
      len(ms) == 1 and "test RU" in ms[0]["statement"], str([g["statement"] for g in ms]))
    edge = m.execute("SELECT verified FROM goal_edge WHERE run_id=? AND child_goal=?",
                     (rid, ms[0]["goal_id"] if ms else "")).fetchone()
    T("with a VERIFIED edge into the deficient parent", edge and edge["verified"] == 1)
    commits = m.execute("SELECT COUNT(*) c FROM turn_record WHERE run_id=? AND "
                        "source_stamp='COMMITMENT_STEP' AND action='ACTION2'",
                        (rid,)).fetchone()["c"]
    T("the milestone EXECUTED as experiment-commitments (non-probe stamps)", commits >= 3,
      f"{commits} commitment beats")
    receipts = m.execute("SELECT COUNT(*) c FROM consequence_record WHERE run_id=? AND "
                         "predictor_kind='RULE' AND match=0", (rid,)).fetchone()["c"]
    T("each execution minted a pre-registered mismatch receipt", receipts >= 3)
    ru_status = m.execute("SELECT to_status FROM status_transition WHERE run_id=? AND "
                          "entity_kind='RULE' ORDER BY seq DESC LIMIT 1", (rid,)).fetchone()
    T("the false rule DEMOTED by its own receipts", ru_status["to_status"] == "DEMOTED")
    blocked = m.execute("SELECT COUNT(*) c FROM status_transition WHERE run_id=? AND "
                        "entity_kind='COMMITMENT_STEP' AND to_status='BLOCKED' AND "
                        "reason='premise demoted'", (rid,)).fetchone()["c"]
    T("the live step auto-blocked on the demoted premise", blocked >= 1)
    stamps = m.execute("SELECT DISTINCT goal_id FROM deficit_stamp WHERE run_id=?",
                       (rid,)).fetchall()
    T("DEFICIT stamped for the root AND the dead milestone (honest re-open)",
      len(stamps) >= 2, str([r["goal_id"] for r in stamps]))
    g0acc = m.execute("SELECT COUNT(*) c FROM status_transition WHERE run_id=? AND "
                      "entity_id='G0001' AND to_status='ACCEPTED'", (rid,)).fetchone()["c"]
    T("G0 never ACCEPTED (no real progress — the mock is ls20-honest)", g0acc == 0)
    m.close()


def main() -> None:
    tool_seam()
    milestone_compile()
    bootstrap_positive()
    stamps_and_frontier()
    loop_negative()
    print(f"\n{'ALL PASS' if not FAILS else f'{len(FAILS)} FAILURES: {FAILS}'}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
