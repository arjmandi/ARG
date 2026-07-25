#!/usr/bin/env python3
"""ARG C5 tests — the ZCR consumption canary loop, closed (review S5).

- Views are salted at cadence (ARG_K_CANARY=1 → every Observer call; every
  Surveyor epoch); nonces recorded to zcr_salt; organ echoes recorded to
  zcr_echo; render_capture written live.
- An organ that echoes → rates 1.0, run VALID.
- An organ that never echoes → MISSING_CANARY metered as WER, uniform ZCR
  failure → run INVALID (Q11 class, §2.5 diagnosis 1).
Run: uv run python tests/test_arg_zcr.py"""
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


def _env(state):
    from agents.structs import GameAction

    def env(action):
        state["n"] += 1; n = state["n"]
        st = "WIN" if n >= 7 else "NOT_FINISHED"
        body = {"frame": TA._grid_plate(9 if n % 2 else 8), "state": st, "score": 0,
                "levels_completed": 0, "available_actions": [6] if st == "NOT_FINISHED" else [],
                "guid": "g", "game_id": "ls20", "card_id": "c1"}
        r = MagicMock(); r.json.return_value = body; r.status_code = 200
        return r
    return env


def _run(tag, echoing: bool):
    s, p = tempfile.mktemp(suffix=".db"), tempfile.mktemp(suffix=".db")
    os.environ["ARG_K_CANARY"] = "1"          # salt every organ call
    agent_arg = TA._reload_arg(s, p, max_actions="8")

    def observer(changeset, log_tail, view):
        echo = re.findall(r"ZQ[0-9a-f]{8}", view) if echoing else []
        return {"ops": [], "canary_echo": echo, "raw": MagicMock()}

    def surveyor(trigger, view, buckets):
        echo = re.findall(r"ZQ[0-9a-f]{8}", view) if echoing else []
        return {"proposals": [], "canary_echo": echo, "raw": MagicMock()}
    agent_arg.organs.configure_llm = lambda *a, **k: None
    agent_arg.organs.run_observer = observer
    agent_arg.organs.run_surveyor = surveyor
    agent = TA._mk_agent(agent_arg, [tag])
    agent_arg.Agent.do_action_request = lambda self, action: _env({"n": 0})(action) if False else None
    # (bind a fresh stateful env)
    state = {"n": 0}
    env = _env(state)
    agent_arg.Agent.do_action_request = lambda self, action: env(action)
    agent.main()
    os.environ.pop("ARG_K_CANARY", None)
    return s, p, agent._run_id


def main() -> None:
    # ---- echoing organ: canary loop closes, run stays VALID ----
    s1, p1, rid1 = _run("zcr-echo", echoing=True)
    pq = sqlite3.connect(p1); pq.row_factory = sqlite3.Row
    salts = pq.execute("SELECT COUNT(*) c FROM zcr_salt WHERE run_id=?", (rid1,)).fetchone()["c"]
    echoes = pq.execute("SELECT COUNT(*) c, SUM(echoed) e FROM zcr_echo WHERE run_id=?",
                        (rid1,)).fetchone()
    caps = pq.execute("SELECT COUNT(*) c FROM render_capture WHERE run_id=?", (rid1,)).fetchone()["c"]
    T("salted nonces recorded (zcr_salt)", salts >= 3, str(salts))
    T("echoes recorded and CONSUMED (zcr_echo echoed=1)",
      echoes["c"] >= 3 and echoes["e"] == echoes["c"], f"{echoes['e']}/{echoes['c']}")
    T("render_capture written live (Q11 evidence)", caps >= 3, str(caps))
    import importlib as _il
    import probe_arg_legibility
    _il.reload(probe_arg_legibility)
    lb1 = probe_arg_legibility.verify(s1, p1, rid1)
    T("echoing run: VALID with per-zone rates 1.0",
      lb1["verdict"] == "VALID" and all(v == 1.0 for v in lb1["zcr_rates"].values()),
      str(lb1["zcr_rates"]))
    pq.close()

    # ---- non-echoing organ: MISSING_CANARY metered; uniform failure → INVALID ----
    s2, p2, rid2 = _run("zcr-deaf", echoing=False)
    m2 = sqlite3.connect(s2); m2.row_factory = sqlite3.Row
    miss = m2.execute("SELECT COUNT(*) c FROM write_reject WHERE run_id=? AND "
                      "violation_class='MISSING_CANARY'", (rid2,)).fetchone()["c"]
    T("deaf organ: MISSING_CANARY metered as WER", miss >= 1, str(miss))
    lb2 = probe_arg_legibility.verify(s2, p2, rid2)
    T("deaf organ: uniform ZCR failure → run INVALID (Q11 class)",
      lb2["verdict"] == "INVALID" and lb2["zcr_uniform_fail"] is True, str(lb2["zcr_rates"]))
    import probe_arg_health
    _il.reload(probe_arg_health)
    h2 = probe_arg_health.health(s2, p2, rid2)
    T("health reports per-zone ZCR rates", bool(h2["zcr_rates"]))
    m2.close()

    print(f"\n{'PASS' if not FAILS else 'FAIL: ' + str(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
