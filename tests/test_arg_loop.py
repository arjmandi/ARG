#!/usr/bin/env python3
"""ARG M2 loop test — offline, mock-driven (no live API).

Drives the real ARG.main() beat pump with a monkeypatched do_action_request
serving a scripted grid game, then asserts the plan's M2 verify: RESET-first,
api_log + turn_record per beat, api_log↔Log action agreement, frame-hash loop
closure, terminate on WIN, never on a bare level completion.
Run: uv run python tests/test_arg_loop.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["TESTING"] = "True"
os.environ["SENSI_MAX_ACTIONS"] = "12"

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
    return [g]   # one layer


def main() -> None:
    store_db = tempfile.mktemp(suffix=".db")
    probe_db = tempfile.mktemp(suffix=".db")
    os.environ["ARG_STORE_PATH"] = store_db
    os.environ["ARG_PROBE_PATH"] = probe_db

    # reload config so the env paths + MAX_ACTIONS take effect
    import importlib
    from agents.arg import config as argcfg
    importlib.reload(argcfg)
    from agents.arg import store as argstore, probe_db as argprobe, executive as argexec
    importlib.reload(argstore); importlib.reload(argprobe); importlib.reload(argexec)
    from agents.arg import agent_arg
    importlib.reload(agent_arg)
    from agents.structs import FrameData, GameAction, GameState

    # hermetic: echoing no-op organ mocks (never real LLM calls from a test)
    import re as _re
    from unittest.mock import MagicMock as _MM
    agent_arg.organs.configure_llm = lambda *a, **k: None
    agent_arg.organs.run_observer = lambda cs, lt, v: {
        "ops": [], "canary_echo": _re.findall(r"ZQ[0-9a-f]{8}", v), "raw": _MM()}
    agent_arg.organs.run_surveyor = lambda t, v, b: {
        "proposals": [], "canary_echo": _re.findall(r"ZQ[0-9a-f]{8}", v), "raw": _MM()}

    ARG = agent_arg.ARG
    agent = ARG.__new__(ARG)
    # minimal Agent state (bypass network __init__)
    agent.card_id = "card-x"; agent.game_id = "ls20"; agent.guid = ""
    agent.agent_name = "arg"; agent.tags = ["m2-test"]; agent.frames = [FrameData(score=0)]
    agent._cleanup = True; agent.game_state = GameState.NOT_PLAYED
    agent.action_counter = 0
    ARG.__init__(agent, card_id="card-x", game_id="ls20", agent_name="arg",
                 ROOT_URL="http://mock", record=False, tags=["m2-test"])

    # scripted server: RESET → level0 frames; a level bump at call 4; WIN at call 8
    state = {"n": 0}

    def fake_request(action):
        state["n"] += 1
        n = state["n"]
        if action == GameAction.RESET:
            body = {"frame": _grid(9, plate=(1, 1)), "state": "NOT_FINISHED", "score": 0,
                    "levels_completed": 0, "available_actions": [1, 2, 3, 4, 6],
                    "guid": "g1", "game_id": "ls20", "card_id": "card-x"}
        elif n == 5:  # a bare level completion — must NOT end the run
            body = {"frame": _grid(3, plate=(2, 2)), "state": "NOT_FINISHED", "score": 1,
                    "levels_completed": 1, "available_actions": [1, 2, 3, 4, 6],
                    "guid": "g1", "game_id": "ls20", "card_id": "card-x"}
        elif n >= 9:  # WIN
            body = {"frame": _grid(5), "state": "WIN", "score": 2, "levels_completed": 2,
                    "available_actions": [], "guid": "g1", "game_id": "ls20", "card_id": "card-x"}
        else:
            body = {"frame": _grid(9 if n % 2 else 8, plate=(1, 1)), "state": "NOT_FINISHED",
                    "score": 0, "levels_completed": 0, "available_actions": [1, 2, 3, 4, 6],
                    "guid": "g1", "game_id": "ls20", "card_id": "card-x"}
        resp = MagicMock()
        resp.json.return_value = body
        resp.status_code = 200
        return resp

    # patch the BASE do_action_request (ARG.do_action_request calls super()).
    agent_arg.Agent.do_action_request = lambda self, action: fake_request(action)
    agent.get_scorecard = lambda: MagicMock(model_dump=lambda: {"score": 2})

    agent.main()

    # ---- assertions over the written stores ----
    import sqlite3
    m = sqlite3.connect(store_db); m.row_factory = sqlite3.Row
    p = sqlite3.connect(probe_db); p.row_factory = sqlite3.Row
    rid = agent._run_id

    turns = m.execute("SELECT * FROM turn_record WHERE run_id=? ORDER BY turn_id", (rid,)).fetchall()
    api = p.execute("SELECT * FROM api_log WHERE run_id=? ORDER BY turn_id, step_id", (rid,)).fetchall()

    T("RESET is the first emitted command", turns and turns[0]["action"] == "RESET")
    T("api_log has a row per emitted command", len(api) == len(turns), f"{len(api)} vs {len(turns)}")
    T("api_log↔Log action agreement",
      all(a["action"] == t["action"] for a, t in zip(api, turns)))
    T("frame-hash loop closure (post==next pre)",
      all(turns[i]["post_frame_hash"] == turns[i + 1]["pre_frame_hash"]
          for i in range(len(turns) - 1) if turns[i + 1]["action"] != "RESET"))
    T("terminated on WIN", turns[-1]["state_flags"] == "WIN")
    T("did NOT terminate on the bare level completion",
      any(t["level_counter"] == 1 and t["state_flags"] == "NOT_FINISHED" for t in turns))
    T("seeds written (G0 VALIDATED + LEARN-* PROPOSED)",
      m.execute("SELECT COUNT(*) c FROM goal WHERE run_id=?", (rid,)).fetchone()["c"] >= 4)
    g0_status = m.execute(
        "SELECT to_status FROM status_transition WHERE run_id=? AND entity_kind='GOAL' "
        "AND entity_id='G0001' ORDER BY seq DESC LIMIT 1", (rid,)).fetchone()
    # B6 runs live: G0 (MONOTONE_TERMINAL) latches VALIDATED→ACCEPTED once a
    # progress signal (the mock's level/score bump) fires — the engine working.
    T("G0 status VALIDATED or ACCEPTED (latched on progress)",
      g0_status and g0_status["to_status"] in ("VALIDATED", "ACCEPTED"), g0_status["to_status"])
    T("G0 reached ACCEPTED on the level bump (B6 live)",
      m.execute("SELECT COUNT(*) c FROM status_transition WHERE run_id=? AND entity_id='G0001' "
                "AND to_status='ACCEPTED'", (rid,)).fetchone()["c"] >= 1)
    T("consequence_records written for non-RESET beats",
      m.execute("SELECT COUNT(*) c FROM consequence_record WHERE run_id=?", (rid,)).fetchone()["c"] > 0)
    T("referents minted (grounding began)",
      m.execute("SELECT COUNT(*) c FROM referent WHERE run_id=?", (rid,)).fetchone()["c"] > 0)
    T("binding_records written",
      m.execute("SELECT COUNT(*) c FROM binding_record WHERE run_id=?", (rid,)).fetchone()["c"] > 0)
    T("scorecard captured on level transition + finish",
      p.execute("SELECT COUNT(*) c FROM scorecards WHERE run_id=?", (rid,)).fetchone()["c"] >= 1)
    T("startup_probe written",
      p.execute("SELECT COUNT(*) c FROM startup_probe WHERE run_id=?", (rid,)).fetchone()["c"] == 1)
    T("append-only held (no orphaned api rows w/o frames on success)",
      all(a["frame_received"] == 1 for a in api))

    m.close(); p.close()
    print(f"\n{'PASS' if not FAILS else 'FAIL: ' + str(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
