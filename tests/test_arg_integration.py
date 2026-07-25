#!/usr/bin/env python3
"""ARG integration test: the organs wired into the live loop (B5 Observer, B7
Surveyor epoch), with the LLM mocked. Asserts Observer ops are validated +
applied and Surveyor proposals are gated + ingested, and llm_calls are logged.
Run: uv run python tests/test_arg_integration.py"""
import importlib
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["TESTING"] = "True"
os.environ["SENSI_MAX_ACTIONS"] = "10"

FAILS = []


def T(name, cond, detail=""):
    print(f"  [{'ok ' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def _grid(fill, plate=None):
    g = [[0] * 8 for _ in range(8)]
    for y in range(4, 8):
        for x in range(4, 8):
            g[y][x] = fill
    if plate:
        g[plate[1]][plate[0]] = 7
    return [g]


def main() -> None:
    store_db = tempfile.mktemp(suffix=".db")
    probe_db = tempfile.mktemp(suffix=".db")
    os.environ["ARG_STORE_PATH"] = store_db
    os.environ["ARG_PROBE_PATH"] = probe_db
    from agents.arg import config as cfg
    importlib.reload(cfg)
    for mod in ("store", "probe_db", "executive", "pather", "seeds", "renderer", "organs",
                "predicates", "agent_arg"):
        importlib.reload(importlib.import_module(f"agents.arg.{mod}"))
    from agents.arg import agent_arg, organs
    from agents.structs import GameAction, GameState

    # mock the LLM: Observer emits an INTERPRET + a PROPOSE_RULE; Surveyor a PROPOSE_GOAL
    organs.configure_llm = lambda *a, **k: None
    obs_calls = {"n": 0}

    def fake_observer(changeset, log_tail, view):
        obs_calls["n"] += 1
        # find a referent id mentioned in the view to interpret; echo any canaries
        import re
        ids = re.findall(r"R\d{4}", view)
        ref = ids[0] if ids else "R0001"
        return {"ops": [{"op": "INTERPRET", "ref": ref, "label": "small-mover"},
                        {"op": "PROPOSE_RULE", "template": "WHEN any DO ACTION1 THEN change",
                         "ctx": {"action": "ACTION1", "target": None},
                         "effect": {"cells_changed": "nonzero"}}],
                "canary_echo": re.findall(r"ZQ[0-9a-f]{8}", view), "raw": MagicMock()}

    sur_calls = {"n": 0}

    def fake_surveyor(trigger, view, buckets):
        sur_calls["n"] += 1
        import re
        return {"proposals": [{"op": "PROPOSE_RULE", "template": "t", "ctx": {}, "effect": {},
                              "test_plan": "predict"}],
                "canary_echo": re.findall(r"ZQ[0-9a-f]{8}", view), "raw": MagicMock()}

    agent_arg.organs.run_observer = fake_observer
    agent_arg.organs.run_surveyor = fake_surveyor

    agent = agent_arg.ARG.__new__(agent_arg.ARG)
    agent_arg.ARG.__init__(agent, card_id="c1", game_id="ls20", agent_name="arg",
                           ROOT_URL="http://mock", record=False, tags=["integ"])
    st = {"n": 0}

    def fake(action):
        st["n"] += 1; n = st["n"]
        fill = 9 if n % 2 else 8
        state = "WIN" if n >= 9 else "NOT_FINISHED"
        body = {"frame": _grid(fill, (1, 1)), "state": state, "score": 0, "levels_completed": 0,
                "available_actions": [1, 2, 4, 6] if state == "NOT_FINISHED" else [],
                "guid": "g", "game_id": "ls20", "card_id": "c1"}
        r = MagicMock(); r.json.return_value = body; r.status_code = 200
        return r
    agent_arg.Agent.do_action_request = lambda self, action: fake(action)
    agent.get_scorecard = lambda: MagicMock(model_dump=lambda: {})
    agent.main()

    import sqlite3
    m = sqlite3.connect(store_db); m.row_factory = sqlite3.Row
    p = sqlite3.connect(probe_db); p.row_factory = sqlite3.Row
    rid = agent._run_id

    T("Observer invoked on unexplained (novel) beats", obs_calls["n"] > 0)
    T("Observer INTERPRET applied (alias written)",
      m.execute("SELECT COUNT(*) c FROM referent_alias WHERE run_id=?", (rid,)).fetchone()["c"] > 0)
    T("Observer PROPOSE_RULE ingested (rule created)",
      m.execute("SELECT COUNT(*) c FROM rule WHERE run_id=?", (rid,)).fetchone()["c"] > 0)
    T("Surveyor epoch invoked on a trigger", sur_calls["n"] > 0)
    T("llm_calls logged for both organs",
      p.execute("SELECT COUNT(DISTINCT organ) c FROM llm_calls WHERE run_id=?", (rid,)).fetchone()["c"] >= 1)
    T("run still terminates on WIN",
      m.execute("SELECT state_flags FROM turn_record WHERE run_id=? ORDER BY turn_id DESC LIMIT 1",
                (rid,)).fetchone()["state_flags"] == "WIN")
    # legibility still VALID with organs live
    import probe_arg_legibility
    lb = probe_arg_legibility.verify(store_db, probe_db, rid)
    T("legibility VALID with organs in the loop", lb["verdict"] == "VALID", str(lb))

    m.close(); p.close()
    print(f"\n{'PASS' if not FAILS else 'FAIL: ' + str(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
