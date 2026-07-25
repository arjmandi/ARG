#!/usr/bin/env python3
"""ARG C1 tests — B4 pre-registration LIVE (the review's S2 blocker).

Asserts the design-mandated behaviors the old suite was blind to:
- closed rule ctx/effect vocabulary (reject classes fire)
- predictions pre-registered BEFORE emission, matched by the Executive
- a rule reaches TESTED **in live play**; a targeted rule's receipts lift its
  referent to CHARACTERIZED **in live play** (buildplan M5 live criterion)
- the Observer QUIETS once beats are explained (prediction matched)
- T1 fires from a real contradiction (a TESTED rule's prediction failed)
- LEARN-ACTIONS is satisfiable and fires in live play (context regimes)
Run: uv run python tests/test_arg_prereg.py"""
import importlib
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


def _reload_arg(store_db, probe_db, max_actions="12"):
    os.environ["ARG_STORE_PATH"] = store_db
    os.environ["ARG_PROBE_PATH"] = probe_db
    os.environ["SENSI_MAX_ACTIONS"] = max_actions
    from agents.arg import config as cfg
    importlib.reload(cfg)
    for mod in ("store", "probe_db", "executive", "pather", "seeds", "renderer", "organs",
                "predicates", "agent_arg"):
        importlib.reload(importlib.import_module(f"agents.arg.{mod}"))
    from agents.arg import agent_arg
    return agent_arg


def _grid(fill, extra=None):
    g = [[0] * 8 for _ in range(8)]
    for y in range(4, 8):
        for x in range(4, 8):
            g[y][x] = fill
    if extra:
        g[extra[1]][extra[0]] = extra[2]
    return [g]


def _mk_agent(agent_arg, tags):
    a = agent_arg.ARG.__new__(agent_arg.ARG)
    agent_arg.ARG.__init__(a, card_id="c1", game_id="ls20", agent_name="arg",
                           ROOT_URL="http://mock", record=False, tags=tags)
    a.get_scorecard = lambda: MagicMock(model_dump=lambda: {})
    return a


def main() -> None:
    import sqlite3

    # ================= unit: closed rule vocabulary =================
    from agents.arg.store import Store
    from agents.arg.adapter import ARCAdapter, Component
    from agents.arg.executive import Executive
    s = Store(tempfile.mktemp(suffix=".db"))
    s.register_run("u", "ls20", "m", 0, "{}", 6000, "t")
    exe = Executive(s, ARCAdapter(), "u")
    ref = exe.mint_referent(Component(color=7, cells=frozenset([(1, 1)]), bbox=(1, 1, 1, 1),
                                      centroid=(1, 1), size=1, shape=frozenset([(0, 0)])), 1)
    s.commit()
    T("shape: ctx without action rejected",
      exe.validate_rule_shape({}, {"cells_changed": "nonzero"})[1] == "RULE_CTX_NOT_CLOSED")
    T("shape: dangling target rejected",
      exe.validate_rule_shape({"action": "ACTION1", "target": "R9999"}, {"cells_changed": "zero"})[1]
      == "RULE_TARGET_DANGLING")
    T("shape: incompilable when rejected",
      exe.validate_rule_shape({"action": "ACTION1", "when": {"op": "GT", "channel": "energy", "vs": "prev"}},
                              {"cells_changed": "zero"})[1] == "RULE_WHEN_INCOMPILABLE")
    T("shape: open effect rejected",
      exe.validate_rule_shape({"action": "ACTION1"}, {"door_opens": True})[1] == "RULE_EFFECT_NOT_CLOSED")
    T("shape: closed rule accepted",
      exe.validate_rule_shape({"action": "ACTION6", "target": ref},
                              {"cells_changed": "nonzero", "level_event": 0})[0] is True)
    # applicability: TESTED first, DEMOTED excluded, target filter
    r_hyp = exe.add_rule(1, "hyp", {"action": "ACTION1", "target": None}, {"cells_changed": "nonzero"})
    r_tst = exe.add_rule(1, "tst", {"action": "ACTION1", "target": None}, {"cells_changed": "nonzero"})
    r_dem = exe.add_rule(1, "dem", {"action": "ACTION1", "target": None}, {"cells_changed": "zero"})
    r_tgt = exe.add_rule(1, "tgt", {"action": "ACTION1", "target": ref}, {"cells_changed": "zero"})
    exe._append_status(2, "RULE", r_tst, "HYPOTHESIS", "TESTED", "t")
    exe._append_status(2, "RULE", r_dem, "HYPOTHESIS", "DEMOTED", "t")
    s.commit()
    apps = exe.applicable_rules("ACTION1", None, {"cur": {}, "prev": {}})
    T("applicable: TESTED first, DEMOTED excluded, off-target excluded",
      [a["rule_id"] for a in apps] == [r_tst, r_hyp], str([a["rule_id"] for a in apps]))
    apps_t = exe.applicable_rules("ACTION1", ref, {"cur": {}, "prev": {}})
    T("applicable: targeted rule joins on matching target",
      r_tgt in [a["rule_id"] for a in apps_t])
    T("match_effect: nonzero vs 0 fails", exe.match_effect({"cells_changed": "nonzero"}, 0, 0, 0) is False)
    T("match_effect: subset-exact on events",
      exe.match_effect({"level_event": 1}, 5, 0, 1) is True
      and exe.match_effect({"level_event": 1}, 5, 0, 0) is False)
    s.close()

    # ================= live loop A: rule → TESTED → CHARACTERIZED → Observer quiets =================
    store_db, probe_db = tempfile.mktemp(suffix=".db"), tempfile.mktemp(suffix=".db")
    agent_arg = _reload_arg(store_db, probe_db, max_actions="10")
    from agents.arg import organs
    organs.configure_llm = lambda *a, **k: None
    obs_calls = {"n": 0, "beats": []}

    def fake_observer(changeset, log_tail, view):
        obs_calls["n"] += 1
        import re
        # rules for every ROSTER referent (the changeset now paginates only
        # THIS beat's changed refs — by design)
        ids = sorted(set(re.findall(r"R\d{4}", view)))
        ops = [{"op": "PROPOSE_RULE", "template": f"click {r} changes things",
                "ctx": {"action": "ACTION6", "target": r},
                "effect": {"cells_changed": "nonzero"}} for r in ids[:4]]
        return {"ops": ops, "canary_echo": re.findall(r"ZQ[0-9a-f]{8}", view),
                "raw": MagicMock()}
    agent_arg.organs.run_observer = fake_observer
    agent_arg.organs.run_surveyor = lambda *a, **k: {"proposals": [], "canary_echo": [], "raw": MagicMock()}

    agent = _mk_agent(agent_arg, ["prereg-a"])
    st = {"n": 0}
    from agents.structs import GameAction

    def fake(action):
        st["n"] += 1; n = st["n"]
        # every beat the block flips color (always a change); a static 1-cell
        # plate at (1,1) stays the smallest referent = the ACTION6 probe target
        state = "WIN" if n >= 9 else "NOT_FINISHED"
        body = {"frame": _grid(9 if n % 2 else 8, (1, 1, 7)), "state": state, "score": 0,
                "levels_completed": 0, "available_actions": [6] if state == "NOT_FINISHED" else [],
                "guid": "g", "game_id": "ls20", "card_id": "c1"}
        r = MagicMock(); r.json.return_value = body; r.status_code = 200
        return r
    agent_arg.Agent.do_action_request = lambda self, action: fake(action)
    agent.main()

    m = sqlite3.connect(store_db); m.row_factory = sqlite3.Row
    rid = agent._run_id
    n_pred = m.execute("SELECT COUNT(*) c FROM consequence_record WHERE run_id=? AND predictor_id "
                       "IS NOT NULL AND predicted_delta_json IS NOT NULL", (rid,)).fetchone()["c"]
    T("LIVE: predictions pre-registered + matched (predictor receipts exist)", n_pred > 0, str(n_pred))
    tested = m.execute("SELECT COUNT(DISTINCT entity_id) c FROM status_transition WHERE run_id=? AND "
                       "entity_kind='RULE' AND to_status='TESTED'", (rid,)).fetchone()["c"]
    T("LIVE: a rule reached TESTED in play", tested > 0, str(tested))
    charz = m.execute("SELECT COUNT(*) c FROM status_transition WHERE run_id=? AND "
                      "entity_kind='REFERENT_RUNG' AND to_status='CHARACTERIZED'", (rid,)).fetchone()["c"]
    T("LIVE: a referent climbed to CHARACTERIZED off a pre-committed prediction (M5 live criterion)",
      charz > 0, str(charz))
    matched_turns = m.execute("SELECT COUNT(*) c FROM turn_record WHERE run_id=? AND match=1",
                              (rid,)).fetchone()["c"]
    T("LIVE: turn_record carries the primary prediction match", matched_turns > 0)
    # Observer quieting: every beat changes cells, so without explanation it would
    # fire every non-RESET beat (8); with the rule matching from beat 2 on, it
    # must fire only on the unexplained prefix.
    T("LIVE: Observer quiets once beats are explained", obs_calls["n"] <= 2, str(obs_calls["n"]))
    m.close()

    # ================= live loop B: T1 from a real contradiction =================
    store_db2, probe_db2 = tempfile.mktemp(suffix=".db"), tempfile.mktemp(suffix=".db")
    agent_arg = _reload_arg(store_db2, probe_db2, max_actions="12")
    organs2 = importlib.import_module("agents.arg.organs")
    organs2.configure_llm = lambda *a, **k: None
    triggers = []

    def fake_observer2(changeset, log_tail, view):
        return {"ops": [{"op": "PROPOSE_RULE", "template": "ACTION6 always changes",
                         "ctx": {"action": "ACTION6", "target": None},
                         "effect": {"cells_changed": "nonzero"}}],
                "canary_echo": [], "raw": MagicMock()}

    def fake_surveyor2(trigger, view, buckets):
        triggers.append(trigger)
        return {"proposals": [], "canary_echo": [], "raw": MagicMock()}
    agent_arg.organs.run_observer = fake_observer2
    agent_arg.organs.run_surveyor = fake_surveyor2

    agent2 = _mk_agent(agent_arg, ["prereg-b"])
    st2 = {"n": 0}

    def fake2(action):
        st2["n"] += 1; n = st2["n"]
        # changes for beats 1-5 (rule matches, → TESTED), then the world FREEZES
        # (beats 6+ identical) → the TESTED rule's prediction fails → T1
        state = "WIN" if n >= 11 else "NOT_FINISHED"
        fill = (9 if n % 2 else 8) if n <= 5 else 5
        body = {"frame": _grid(fill, (1, 1, 7)), "state": state, "score": 0,
                "levels_completed": 0, "available_actions": [6] if state == "NOT_FINISHED" else [],
                "guid": "g", "game_id": "ls20", "card_id": "c1"}
        r = MagicMock(); r.json.return_value = body; r.status_code = 200
        return r
    agent_arg.Agent.do_action_request = lambda self, action: fake2(action)
    agent2.main()

    T("LIVE: T1 contradiction epoch fired when the TESTED rule's prediction failed",
      "T1" in triggers, str(triggers))
    m2 = sqlite3.connect(store_db2); m2.row_factory = sqlite3.Row
    demoted = m2.execute("SELECT COUNT(*) c FROM status_transition WHERE run_id=? AND "
                         "entity_kind='RULE' AND to_status='DEMOTED'", (agent2._run_id,)).fetchone()["c"]
    T("LIVE: repeated contradictions demote the rule (never delete)", demoted > 0)
    m2.close()

    # ================= live loop C: LEARN-ACTIONS satisfiable + fires =================
    store_db3, probe_db3 = tempfile.mktemp(suffix=".db"), tempfile.mktemp(suffix=".db")
    agent_arg = _reload_arg(store_db3, probe_db3, max_actions="14")
    organs3 = importlib.import_module("agents.arg.organs")
    organs3.configure_llm = lambda *a, **k: None
    agent_arg.organs.run_observer = lambda *a, **k: {"ops": [], "canary_echo": [], "raw": MagicMock()}
    agent_arg.organs.run_surveyor = lambda *a, **k: {"proposals": [], "canary_echo": [], "raw": MagicMock()}

    agent3 = _mk_agent(agent_arg, ["prereg-c"])
    st3 = {"n": 0}

    def fake3(action):
        st3["n"] += 1; n = st3["n"]
        state = "WIN" if n >= 13 else "NOT_FINISHED"
        body = {"frame": _grid(9 if n % 2 else 8, (1, 1, 7)), "state": state, "score": 0,
                "levels_completed": 0,
                "available_actions": [1, 2, 3, 4, 5, 6, 7] if state == "NOT_FINISHED" else [],
                "guid": "g", "game_id": "ls20", "card_id": "c1"}
        r = MagicMock(); r.json.return_value = body; r.status_code = 200
        return r
    agent_arg.Agent.do_action_request = lambda self, action: fake3(action)
    agent3.main()

    m3 = sqlite3.connect(store_db3); m3.row_factory = sqlite3.Row
    rid3 = agent3._run_id
    la = m3.execute("SELECT to_status FROM status_transition st JOIN goal g ON g.run_id=st.run_id "
                    "AND g.goal_id=st.entity_id WHERE st.run_id=? AND g.statement='LEARN-ACTIONS' "
                    "ORDER BY st.seq DESC LIMIT 1", (rid3,)).fetchone()
    T("LIVE: LEARN-ACTIONS is satisfiable and fired (ACCEPTED) once all 7 actions covered",
      la and la["to_status"] == "ACCEPTED", str(la["to_status"] if la else None))
    covered = m3.execute("SELECT COUNT(DISTINCT action) c FROM consequence_record WHERE run_id=? "
                         "AND context_class_id LIKE 'CC-L%'", (rid3,)).fetchone()["c"]
    T("LIVE: receipts land in the level's base regime class", covered >= 7, str(covered))
    m3.close()

    print(f"\n{'PASS' if not FAILS else 'FAIL: ' + str(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
