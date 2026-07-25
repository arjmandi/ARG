#!/usr/bin/env python3
"""ARG C6 tests — lifecycle hygiene (review S6/S8/S9/S10).

- B3 re-anchor: a moved referent gets a new anchor VERSION; the join tracks it.
- T5 boundary pass: TESTED→HYPOTHESIS with prior support noted; instances go
  DORMANT (out of roster/candidates); ACTIVE steps abort.
- Budget terminal rule: spent budget below VALIDATED → REJECTED
  NEVER_VALIDATED; anti-oscillation gate now guards a real set.
- TTL: a DEMOTED rule older than TTL becomes re-probeable.
- Revision gate resolves evidence_ptr AGAINST THE STORE (claimed fields carry
  no weight); accepted abort writes a REVISION row and ABORTs the step.
- Relations persist (Surveyor + closed verb set); A4/A10 seams are real.
Run: uv run python tests/test_arg_lifecycle.py"""
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["TESTING"] = "True"

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


def _fresh(tag="lc"):
    from agents.arg.store import Store
    from agents.arg.adapter import ARCAdapter
    from agents.arg.executive import Executive
    s = Store(tempfile.mktemp(suffix=".db"))
    s.register_run(tag, "ls20", "m", 0, "{}", 6000, "t")
    return s, Executive(s, ARCAdapter(), tag), tag


def main() -> None:
    from agents.arg.adapter import ChangeSet
    from agents.arg import config as cfg

    # ================= re-anchor on bind (B3 "anchors updated") =================
    s, exe, rid = _fresh()
    mover = _mk(7, [(5, 5)])
    ref = exe.mint_referent(mover, 1)
    s.commit()
    moved = _mk(7, [(6, 5)])   # same signature, new position
    obs = exe.perceive_bind(2, ChangeSet(cells_changed=2, changed_components=[moved],
                                         vanished_components=[]))
    s.commit()
    T("re-anchor: mover re-bound (not duplicated)", obs["bound"] == [ref] and not obs["minted"],
      str(obs))
    cur = [r for r in exe.current_referents_with_cells() if r["ref_id"] == ref][0]
    T("re-anchor: current anchor tracks the new position", cur["cells"] == [[6, 5]], str(cur["cells"]))
    v = s.conn.execute("SELECT MAX(version) v FROM referent WHERE run_id=? AND ref_id=?",
                       (rid, ref)).fetchone()["v"]
    T("re-anchor: appended as a new VERSION (append-only)", v == 2, str(v))

    # ================= T5 boundary pass =================
    s2, exe2, rid2 = _fresh("lc2")
    r1 = exe2.mint_referent(_mk(5, [(1, 1)]), 1)
    ru = exe2.add_rule(1, "r", {"action": "ACTION1", "target": None}, {"cells_changed": "nonzero"})
    exe2._append_status(2, "RULE", ru, "HYPOTHESIS", "TESTED", "t")
    s2.conn.execute("INSERT INTO goal VALUES ('lc2','GX',1,NULL,'x','{}','{}','MONOTONE_TERMINAL',"
                    "NULL,200,3,'SEEDED',0,0)")
    cid = exe2.write_commitment("GX", [{"kind": "INTERACT", "action": "ACTION1",
                                        "target_ref": r1, "predicted": {"cells_changed": "nonzero"}}], 3)
    s2.commit()
    res = exe2.level_boundary_pass(5)
    s2.commit()
    T("T5: TESTED rule demoted to HYPOTHESIS with prior support noted",
      exe2.current_status("RULE", ru) == "HYPOTHESIS" and res["rules_demoted"] == 1)
    reason = s2.conn.execute("SELECT reason FROM status_transition WHERE run_id=? AND entity_id=? "
                             "ORDER BY seq DESC LIMIT 1", (rid2, ru)).fetchone()["reason"]
    T("T5: demotion reason carries prior_support", "prior_support=" in reason, reason)
    T("T5: instances reset (referent DORMANT, out of the roster)",
      res["referents_dormant"] == 1 and exe2._roster_ids() == set())
    T("T5: ACTIVE step aborted",
      exe2.current_status("COMMITMENT_STEP", f"{cid}-S0") == "ABORTED" and res["steps_aborted"] == 1)

    # ================= budget terminal rule + anti-oscillation =================
    s3, exe3, rid3 = _fresh("lc3")
    r3 = exe3.mint_referent(_mk(5, [(1, 1)]), 1)
    test3 = {"op": "GT", "channel": "score", "vs": "prev"}
    s3.conn.execute("INSERT INTO goal VALUES ('lc3','GB',1,NULL,'burn',?,'{}','MONOTONE_TERMINAL',"
                    "NULL,1,3,'SEEDED',0,0)", (json.dumps(test3),))
    exe3._append_status(1, "GOAL", "GB", None, "PROPOSED", "seeded")
    cid3 = exe3.write_commitment("GB", [{"kind": "INTERACT", "action": "ACTION6",
                                         "target_ref": r3, "predicted": {"score_event": 1}}], 2)
    exe3.record_turn(3, "ACTION6", {}, r3, "a", "b", {}, {}, 0, 0, "NOT_FINISHED", None,
                     "COMMITMENT_STEP", commitment_step_id=f"{cid3}-S0")
    s3.commit()
    rejected = exe3.check_goal_budgets(4)
    s3.commit()
    T("budget: exhausted-below-VALIDATED goal REJECTED NEVER_VALIDATED",
      rejected == ["GB"] and exe3.current_status("GOAL", "GB") == "REJECTED")
    # anti-oscillation now guards a REAL rejection: same test, no fresh evidence
    again = exe3.admit_goal({"statement": "burn again", "bindings": [r3],
                             "achievement_test": test3, "discriminator": {"d": 1},
                             "evidence_ptrs": [2]}, 5, parent="GB")
    T("anti-oscillation: re-proposal without post-rejection evidence inadmissible",
      again["reason"] == "GATE4_ANTI_OSCILLATION", str(again))
    again2 = exe3.admit_goal({"statement": "burn again", "bindings": [r3],
                              "achievement_test": test3, "discriminator": {"d": 1},
                              "evidence_ptrs": [9]}, 10, parent="GB")
    T("anti-oscillation: fresh evidence (post-rejection turn) re-admits", again2["ok"], str(again2))

    # ================= TTL re-probe =================
    s4, exe4, rid4 = _fresh("lc4")
    ru4 = exe4.add_rule(1, "r", {"action": "ACTION1", "target": None}, {"cells_changed": "zero"})
    exe4._append_status(10, "RULE", ru4, "HYPOTHESIS", "DEMOTED", "contradicted")
    s4.commit()
    T("TTL: not yet expired → still DEMOTED",
      exe4.ttl_sweep(10 + cfg.TTL - 1) == [] and exe4.current_status("RULE", ru4) == "DEMOTED")
    swept = exe4.ttl_sweep(10 + cfg.TTL)
    T("TTL: expiry makes the demoted rule re-probeable (HYPOTHESIS)",
      swept == [ru4] and exe4.current_status("RULE", ru4) == "HYPOTHESIS")

    # ================= revision gate resolves the pointer =================
    s5, exe5, rid5 = _fresh("lc5")
    r5 = exe5.mint_referent(_mk(5, [(1, 1)]), 1)
    ru5 = exe5.add_rule(1, "r", {"action": "ACTION6", "target": r5}, {"score_event": 1})
    exe5._append_status(1, "RULE", ru5, "HYPOTHESIS", "TESTED", "t")
    s5.conn.execute("INSERT INTO goal VALUES ('lc5','GZ',1,NULL,'z','{}','MONOTONE_TERMINAL',"
                    "NULL,200,3,'SEEDED',0,0)".replace("'z','{}'", "'z','{}','{}'"))
    cid5 = exe5.write_commitment("GZ", [{"kind": "INTERACT", "action": "ACTION6",
                                         "target_ref": r5, "predicted": {"score_event": 1}}], 5,
                                 premise_rules=[ru5])
    s5.commit()
    # a merely-CLAIMED contradiction (unresolvable pointer) is rejected
    g1 = exe5.gate_abort_step(f"{cid5}-S0", "rule:RU9999", 8)
    T("gate: unresolvable pointer rejected (claims carry no weight)",
      g1["reason"] == "NOT_CONTRADICTION_CLASS", str(g1))
    # a real DEMOTION of an UNRELATED rule: resolvable but irrelevant
    other = exe5.add_rule(6, "o", {"action": "ACTION1", "target": None}, {"cells_changed": "zero"})
    exe5._append_status(7, "RULE", other, "HYPOTHESIS", "DEMOTED", "x")
    s5.commit()
    g2 = exe5.gate_abort_step(f"{cid5}-S0", f"rule:{other}", 8)
    T("gate: resolvable-but-irrelevant evidence rejected", g2["reason"] == "IRRELEVANT_EVIDENCE")
    # the step's own premise rule demotes AFTER compile → admissible
    exe5._append_status(9, "RULE", ru5, "TESTED", "DEMOTED", "contradicted")
    s5.commit()
    g3 = exe5.gate_abort_step(f"{cid5}-S0", f"rule:{ru5}", 10)
    s5.commit()
    T("gate: contradiction-class + fresh + premise-relevant → abort ACCEPTED", g3["ok"], str(g3))
    T("gate: accepted abort writes the replayable REVISION row + ABORTs the step",
      s5.conn.execute("SELECT COUNT(*) c FROM revision WHERE run_id=?", (rid5,)).fetchone()["c"] == 1
      and exe5.current_status("COMMITMENT_STEP", f"{cid5}-S0") == "ABORTED")

    # ================= relations persist; seams are real =================
    res5 = exe5.validate_surveyor_proposals(
        [{"op": "PROPOSE_RELATION", "verb": "blocks", "src": r5, "dst": r5, "test_plan": "t"},
         {"op": "PROPOSE_RELATION", "verb": "vibes_with", "src": r5, "dst": r5}], 11)
    s5.commit()
    T("relations: closed-verb relation PERSISTED",
      s5.conn.execute("SELECT COUNT(*) c FROM relation WHERE run_id=? AND verb='blocks'",
                      (rid5,)).fetchone()["c"] == 1)
    T("relations: non-closed verb rejected",
      any(r["reason"] == "RELATION_VERB_NOT_CLOSED" for r in res5["rejected"]))

    # A4 (ARG_CONSEQ=0): appearance promotes — the ablation seam is real
    os.environ["ARG_CONSEQ"] = "0"
    from agents.arg import config as cfg2
    importlib.reload(cfg2)
    for mod in ("store", "executive"):
        importlib.reload(importlib.import_module(f"agents.arg.{mod}"))
    from agents.arg.store import Store as Store2
    from agents.arg.executive import Executive as Executive2
    from agents.arg.adapter import ARCAdapter
    sa = Store2(tempfile.mktemp(suffix=".db"))
    sa.register_run("a4", "ls20", "m", 0, "{}", 6000, "t")
    ea = Executive2(sa, ARCAdapter(), "a4")
    rua = ea.add_rule(1, "r", {"action": "ACTION1", "target": None}, {"cells_changed": "nonzero"})
    sa.commit()
    T("A4: with ARG_CONSEQ=0 a rule promotes WITHOUT receipts (anti-cascade off)",
      ea.recompute_rule_status(rua, 2) == "TESTED")
    os.environ.pop("ARG_CONSEQ", None)
    importlib.reload(cfg2)
    for mod in ("store", "executive"):
        importlib.reload(importlib.import_module(f"agents.arg.{mod}"))

    # A10 (ARG_GOALCARD_POS): zone order + restated variants are real
    os.environ["ARG_GOALCARD_POS"] = "mid"
    from agents.arg import config as cfg3
    importlib.reload(cfg3)
    for mod in ("store", "executive", "seeds", "renderer"):
        importlib.reload(importlib.import_module(f"agents.arg.{mod}"))
    from agents.arg import store as st3, executive as ex3, seeds as sd3, renderer as rd3
    sm = st3.Store(tempfile.mktemp(suffix=".db"))
    sm.register_run("a10", "ls20", "m", 0, "{}", 6000, "t")
    em = ex3.Executive(sm, ARCAdapter(), "a10")
    sd3.write_seeds(sm, "a10", 0)
    em.mint_referent(_mk(5, [(1, 1)]), 1)
    sm.commit()
    bv = rd3.Renderer(sm, em, "a10", None).budgeted_view(
        {"turn": 1, "level": 0, "score": 0}, [[0] * 8 for _ in range(8)], ["ACTION1"])
    T("A10 mid: the goal card renders mid-context (before Z4/Z5)",
      bv["view"].index("GOAL CARD") < bv["view"].index("UNTOUCHED FRONTIER"))
    os.environ.pop("ARG_GOALCARD_POS", None)
    importlib.reload(cfg3)

    for st_ in (s, s2, s3, s4, s5, sa, sm):
        st_.close()
    print(f"\n{'PASS' if not FAILS else 'FAIL: ' + str(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
