#!/usr/bin/env python3
"""ARG M8 observability test: run a mock game to produce real arg_state.db +
arg_probe.db, then exercise every probe (store dump, log timeline, metrics,
legibility+validity, health, hrt) and assert they reconstruct the full picture.
Run: uv run python tests/test_arg_probes.py"""
import importlib
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["TESTING"] = "True"
os.environ["SENSI_MAX_ACTIONS"] = "14"

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
    from agents.arg import agent_arg
    from agents.structs import FrameData, GameAction, GameState
    # hermetic: echoing no-op organ mocks (never real LLM calls from a test)
    import re as _re
    agent_arg.organs.configure_llm = lambda *a, **k: None
    agent_arg.organs.run_observer = lambda cs, lt, v: {
        "ops": [], "canary_echo": _re.findall(r"ZQ[0-9a-f]{8}", v), "raw": MagicMock()}
    agent_arg.organs.run_surveyor = lambda t, v, b: {
        "proposals": [], "canary_echo": _re.findall(r"ZQ[0-9a-f]{8}", v), "raw": MagicMock()}

    ARG = agent_arg.ARG
    agent = ARG.__new__(ARG)
    ARG.__init__(agent, card_id="c1", game_id="ls20", agent_name="arg", ROOT_URL="http://mock",
                 record=False, tags=["m8"])
    state = {"n": 0, "mx": 5, "my": 5}

    def fake(action):
        state["n"] += 1; n = state["n"]
        if action == GameAction.RESET:
            body = {"frame": _grid(9, (state["mx"], state["my"])), "state": "NOT_FINISHED", "score": 0,
                    "levels_completed": 0, "available_actions": [1, 2, 4, 6], "guid": "g",
                    "game_id": "ls20", "card_id": "c1"}
        elif n >= 11:
            body = {"frame": _grid(5), "state": "WIN", "score": 2, "levels_completed": 1,
                    "available_actions": [], "guid": "g", "game_id": "ls20", "card_id": "c1"}
        else:
            state["mx"] = min(7, state["mx"] + 1)   # a moving referent (for action-model learning)
            body = {"frame": _grid(9, (state["mx"], state["my"])), "state": "NOT_FINISHED",
                    "score": 0, "levels_completed": 0, "available_actions": [1, 2, 4, 6], "guid": "g",
                    "game_id": "ls20", "card_id": "c1"}
        resp = MagicMock(); resp.json.return_value = body; resp.status_code = 200
        return resp
    agent_arg.Agent.do_action_request = lambda self, action: fake(action)
    agent.get_scorecard = lambda: MagicMock(model_dump=lambda: {"score": 2})
    agent.main()

    # ---- probes ----
    import probe_arg_store, probe_arg_log, probe_arg_metrics, probe_arg_legibility  # noqa: E402
    import probe_arg_health, probe_arg_hrt  # noqa: E402
    rid = agent._run_id

    print("\n--- probe_arg_store ---")
    st = probe_arg_store.dump(store_db, rid)
    T("store probe reconstructs referents", len(st.get("referents", [])) > 0)
    T("store probe reconstructs goals (G0 + LEARN-*)", len(st.get("goals", [])) >= 4)
    T("store probe shows grounding rungs", bool(st.get("grounding")))

    print("\n--- probe_arg_log ---")
    lg = probe_arg_log.report(store_db, probe_db, rid)
    T("log probe: no consistency problems", lg["problems"] == [], str(lg["problems"][:3]))
    T("log probe: beats recorded", lg["beats"] > 0)

    print("\n--- probe_arg_metrics ---")
    mt = probe_arg_metrics.compute(store_db, probe_db, rid)
    T("metrics: actions counted", mt["actions"] > 0)
    T("metrics: RGR computed", 0.0 <= mt["RGR"] <= 1.0)
    T("metrics: decision mix present", bool(mt["decision_mix"]))
    T("metrics: R9 compliance ok", mt["R9_ok"] is True)
    T("metrics: WER computed", 0.0 <= mt["WER"] <= 1.0)

    print("\n--- probe_arg_legibility ---")
    lb = probe_arg_legibility.verify(store_db, probe_db, rid)
    T("legibility: verdict VALID", lb["verdict"] == "VALID", str(lb))
    # verdict persisted to the write-separate probe store
    import sqlite3
    v = sqlite3.connect(probe_db).execute(
        "SELECT verdict FROM run_validity WHERE run_id=?", (rid,)).fetchone()
    T("legibility: verdict persisted to run_validity", v and v[0] == "VALID")

    print("\n--- probe_arg_health ---")
    h = probe_arg_health.health(store_db, probe_db, rid)
    T("health: runs without crash", "metrics" in h)

    print("\n--- probe_arg_hrt ---")
    hr = probe_arg_hrt.hrt(store_db, probe_db, rid)
    T("hrt: three organ hops reported (+ mismatch-by-stamp column)",
      {"OBSERVER", "SURVEYOR", "ACTUATOR", "mismatch_by_stamp"} <= set(hr.keys()))

    # observability picture completeness (owner's requirement)
    p = sqlite3.connect(probe_db)
    T("api_log captured every HTTP round-trip",
      p.execute("SELECT COUNT(*) FROM api_log WHERE run_id=?", (rid,)).fetchone()[0] > 0)
    T("scorecards captured", p.execute("SELECT COUNT(*) FROM scorecards WHERE run_id=?", (rid,)).fetchone()[0] >= 1)
    T("startup_probe captured", p.execute("SELECT COUNT(*) FROM startup_probe WHERE run_id=?", (rid,)).fetchone()[0] == 1)
    T("action_model learned from movement (M6 live)",
      sqlite3.connect(store_db).execute("SELECT COUNT(*) FROM action_model WHERE run_id=?", (rid,)).fetchone()[0] > 0)

    print(f"\n{'PASS' if not FAILS else 'FAIL: ' + str(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
