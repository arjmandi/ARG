#!/usr/bin/env python3
"""ARG D1 tests — coverage-gap items 3,4,6,7,9.

- #3 lives: captured from the raw body at the choke point; life_event stamped;
  rule scope earned across deaths (PERSISTENT / WITHIN_LIFE / UNKNOWN) and a
  WITHIN_LIFE rule is excluded from means analysis until re-armed.
- #4 controllable: earned from movement-correlated observations (HYPOTHESIS at
  1, TESTED at k); mover_centroid prefers the earned controllable referent.
- #6 WER floor: per-organ breach (≥ min ops) → run INVALID.
- #7 image receipt: tri-state honest (None = not applicable → pass; 0 → fail).
- #9 test-the-test: the root goal's fire writes the G0-AUDIT row naming which
  progress signals actually moved.
Run: uv run python tests/test_arg_gaps1.py"""
import importlib
import json
import os
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


def _mk(color, cells):
    from agents.arg.adapter import Component
    xs = [c[0] for c in cells]; ys = [c[1] for c in cells]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    n = len(cells)
    return Component(color=color, cells=frozenset(cells), bbox=(x0, y0, x1, y1),
                     centroid=(round(sum(xs) / n), round(sum(ys) / n)), size=n,
                     shape=frozenset((x - x0, y - y0) for x, y in cells))


def main() -> None:
    from agents.arg.store import Store
    from agents.arg.adapter import ARCAdapter
    from agents.arg.executive import Executive
    from agents.structs import GameAction

    # ================= #4 controllable earned from movement =================
    s, exe, rid = Store(tempfile.mktemp(suffix=".db")), None, "d1a"
    s.register_run(rid, "ls20", "m", 0, "{}", 6000, "t")
    exe = Executive(s, ARCAdapter(), rid)

    def grid_mover(mx):
        g = [[0] * 16 for _ in range(16)]
        g[5][mx] = 7          # the 1-cell mover
        g[10][10] = 3         # a static decoy (also 1 cell)
        return g
    mover = _mk(7, [(5, 5)])
    decoy = _mk(3, [(10, 10)])
    m_ref = exe.mint_referent(mover, 1)
    d_ref = exe.mint_referent(decoy, 1)
    s.commit()
    exe.learn_from_movement("ACTION4", grid_mover(5), grid_mover(6), 2)
    s.commit()
    T("#4: first movement observation → controllable HYPOTHESIS",
      exe.current_status("REFERENT_CONTROLLABLE", m_ref) == "HYPOTHESIS")
    exe.learn_from_movement("ACTION4", grid_mover(6), grid_mover(7), 3)
    s.commit()
    T("#4: k movement observations → controllable TESTED",
      exe.current_status("REFERENT_CONTROLLABLE", m_ref) == "TESTED")
    T("#4: the decoy never earns controllable",
      exe.current_status("REFERENT_CONTROLLABLE", d_ref) is None)
    T("#4: mover_centroid prefers the EARNED controllable referent (not the smallest)",
      exe.mover_centroid() == (5, 5))   # the mover's stored anchor centroid
    s.close()

    # ================= #3 scope across deaths (unit) =================
    s2 = Store(tempfile.mktemp(suffix=".db"))
    s2.register_run("d1b", "ls20", "m", 0, "{}", 6000, "t")
    e2 = Executive(s2, ARCAdapter(), "d1b")
    r_per = e2.add_rule(1, "persists", {"action": "ACTION1", "target": None}, {"cells_changed": "nonzero"})
    r_wl = e2.add_rule(1, "vanishes", {"action": "ACTION2", "target": None}, {"cells_changed": "nonzero"})
    r_unk = e2.add_rule(1, "untouched", {"action": "ACTION3", "target": None}, {"cells_changed": "zero"})
    # matches before the death for both; a death at t10 (life_event receipt);
    # after: r_per matches again, r_wl only mismatches
    for t in (5, 6):
        e2.write_consequence(t, "ACTION1", None, "CC-L0", {"cells_changed": 4}, match=True,
                             predictor_id=r_per, predictor_kind="RULE")
        e2.write_consequence(t, "ACTION2", None, "CC-L0", {"cells_changed": 4}, match=True,
                             predictor_id=r_wl, predictor_kind="RULE")
    e2.write_consequence(10, "ACTION5", None, "CC-L0", {"cells_changed": 9}, life_event=1)
    e2.write_consequence(12, "ACTION1", None, "CC-L0", {"cells_changed": 4}, match=True,
                         predictor_id=r_per, predictor_kind="RULE")
    e2.write_consequence(12, "ACTION2", None, "CC-L0", {"cells_changed": 0}, match=False,
                         predictor_id=r_wl, predictor_kind="RULE")
    s2.commit()
    T("#3: effect surviving a death → PERSISTENT", e2.rule_scope(r_per) == "PERSISTENT")
    T("#3: effect vanishing after the death → WITHIN_LIFE", e2.rule_scope(r_wl) == "WITHIN_LIFE")
    T("#3: no crossing evidence → UNKNOWN", e2.rule_scope(r_unk) == "UNKNOWN")
    # means analysis refuses to rest a plan on a WITHIN_LIFE effect
    e2._append_status(13, "RULE", r_wl, "HYPOTHESIS", "TESTED", "t")
    s2.conn.execute("INSERT INTO goal VALUES ('d1b','GS',1,NULL,'score',?, '{}',"
                    "'MONOTONE_TERMINAL',NULL,200,3,'SEEDED',0,0)",
                    (json.dumps({"op": "GT", "channel": "score", "vs": "prev"}),))
    # make r_wl the only score-advancing rule
    s2.conn.execute("UPDATE run SET status=status WHERE run_id='d1b'")  # no-op keepalive
    e2b = e2.add_rule(14, "wl-scorer", {"action": "ACTION2", "target": None},
                      {"score_event": 1})
    # r_wl has no score effect; use a fresh WITHIN_LIFE-scoped scorer instead:
    for t in (15, 16):
        e2.write_consequence(t, "ACTION2", None, "CC-L0", {"cells_changed": 4}, match=True,
                             predictor_id=e2b, predictor_kind="RULE")
    e2.write_consequence(20, "ACTION5", None, "CC-L0", {"cells_changed": 9}, life_event=1)
    e2.write_consequence(22, "ACTION2", None, "CC-L0", {"cells_changed": 0}, match=False,
                         predictor_id=e2b, predictor_kind="RULE")
    e2._append_status(23, "RULE", e2b, "HYPOTHESIS", "TESTED", "t")
    s2.commit()
    T("#3: WITHIN_LIFE rule excluded from means analysis (needs re-arming)",
      e2.rule_scope(e2b) == "WITHIN_LIFE"
      and e2._select_means("GS", {"cur": {}, "prev": {}}) is None)
    s2.close()

    # ================= #3 lives captured live (loop) + #9 audit =================
    st_env = {"n": 0, "lives": 3, "score": 0}
    s3db, p3db = tempfile.mktemp(suffix=".db"), tempfile.mktemp(suffix=".db")
    agent_arg = TA._reload_arg(s3db, p3db, max_actions="8")
    agent_arg.seeds.write_seeds = importlib.import_module("agents.arg.seeds").write_seeds

    def env(action):
        st_env["n"] += 1; n = st_env["n"]
        if n == 4:
            st_env["lives"] -= 1          # a death
        if n == 5:
            st_env["score"] += 1          # progress → G0 fires → audit
        state = "WIN" if n >= 7 else "NOT_FINISHED"
        body = {"frame": TA._grid_plate(9 if n % 2 else 8), "state": state,
                "score": st_env["score"], "levels_completed": 0, "lives": st_env["lives"],
                "available_actions": [6] if state == "NOT_FINISHED" else [],
                "guid": "g", "game_id": "ls20", "card_id": "c1"}
        r = MagicMock(); r.json.return_value = body; r.status_code = 200
        return r
    # echoing mocks (a deaf mock is CORRECTLY invalidated by the ZCR loop)
    import re as _re
    agent_arg.organs.configure_llm = lambda *a, **k: None
    agent_arg.organs.run_observer = lambda cs, lt, v: {
        "ops": [], "canary_echo": _re.findall(r"ZQ[0-9a-f]{8}", v), "raw": MagicMock()}
    agent_arg.organs.run_surveyor = lambda t, v, b: {
        "proposals": [], "canary_echo": _re.findall(r"ZQ[0-9a-f]{8}", v), "raw": MagicMock()}
    a3 = TA._mk_agent(agent_arg, ["d1-lives"])
    agent_arg.Agent.do_action_request = lambda self, action: env(action)
    a3.main()
    m3 = sqlite3.connect(s3db); m3.row_factory = sqlite3.Row
    rid3 = a3._run_id
    T("#3 LIVE: lives captured from the raw body into the TurnRecord",
      m3.execute("SELECT COUNT(*) c FROM turn_record WHERE run_id=? AND lives IS NOT NULL",
                 (rid3,)).fetchone()["c"] >= 6)
    T("#3 LIVE: the death stamped as life_event=1",
      m3.execute("SELECT COUNT(*) c FROM consequence_record WHERE run_id=? AND life_event=1",
                 (rid3,)).fetchone()["c"] >= 1)
    audit = m3.execute("SELECT text FROM annotate WHERE run_id=? AND text LIKE 'G0-AUDIT%'",
                       (rid3,)).fetchone()
    T("#9 LIVE: root-goal fire writes the test-the-test audit row",
      audit is not None, str(audit["text"] if audit else None))
    if audit:
        payload = json.loads(audit["text"].split(" ", 1)[1])
        T("#9: the audit names WHICH signals moved (score, not level/win)",
          payload == {"score": 1, "level": 0, "win": 0}, str(payload))
    m3.close()

    # ================= #6 WER floor + #7 tri-state startup (legibility) =================
    import probe_arg_legibility
    importlib.reload(probe_arg_legibility)
    lb = probe_arg_legibility.verify(s3db, p3db, rid3)
    T("#7: image-receipt NULL (no vision path) passes startup honestly",
      lb["startup_ok"] is True and lb["verdict"] == "VALID", str(lb["verdict"]))
    # forge a floor breach: ≥ WER_MIN_OPS rejects for one organ, zero accepted
    m3w = sqlite3.connect(s3db)
    from agents.arg import config as cfg
    for i in range(cfg.WER_MIN_OPS):
        m3w.execute("INSERT INTO write_reject (run_id, seq, turn_id, organ, op_type, "
                    "violation_class, retry_count) VALUES (?, (SELECT COALESCE(MAX(seq),0)+1 "
                    "FROM write_reject WHERE run_id=?), 1, 'OBSERVER', 'BIND', 'X', 0)",
                    (rid3, rid3))
    m3w.commit(); m3w.close()
    lb2 = probe_arg_legibility.verify(s3db, p3db, rid3)
    T("#6: per-organ WER floor breach → run INVALID (disqualified from attribution)",
      lb2["verdict"] == "INVALID" and lb2["wer_floor_ok"] is False,
      str(lb2.get("wer_by_organ")))

    print(f"\n{'PASS' if not FAILS else 'FAIL: ' + str(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
