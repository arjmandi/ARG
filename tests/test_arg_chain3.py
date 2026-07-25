#!/usr/bin/env python3
"""ARG G3 chain tests: the Surveyor's directed expansion — DEFICIT view block,
fills_hole verified-edge ingest, contract grammar, generative-curriculum cold
start (the batch-4 configuration), chain metrics.

Run: uv run python tests/test_arg_chain3.py"""
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.arg.store import Store  # noqa: E402
from agents.arg.adapter import ARCAdapter  # noqa: E402
from agents.arg.executive import Executive  # noqa: E402
from agents.arg import seeds as sd  # noqa: E402
from agents.arg import organs  # noqa: E402

FAILS = []


def T(name, cond, detail=""):
    print(f"  [{'ok ' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


CTX = {"cur": {"score": 0, "levels_completed": 0, "state": "NOT_FINISHED"},
       "prev": {"score": 0, "levels_completed": 0, "state": "NOT_FINISHED"}}


def _fresh(rid, seeds=True):
    s = Store(tempfile.mktemp(suffix=".db"))
    s.register_run(rid, "ls20", "sonnet", 0, "{}", 6000, "t")
    exe = Executive(s, ARCAdapter(), rid)
    was = sd.config.SEEDS_ON
    sd.config.SEEDS_ON = seeds
    try:
        ids = sd.write_seeds(s, rid, 0)
    finally:
        sd.config.SEEDS_ON = was
    return s, exe, ids


def deficit_block() -> None:
    print("-- the epoch view's DEFICIT block (machine-stated question) --")
    s, exe, ids = _fresh("db")
    blk = exe.deficit_view_block(CTX)
    T("cold start renders the total deficit with hole ids",
      "DEFICIT" in blk and f"{ids['G0']}/H0" in blk and f"{ids['G0']}/H1" in blk, blk[:120])
    T("holes carry their empty derivable evidence (the explore state)",
      '"candidate_rules": []' in blk and '"action_model": false' in blk)
    T("feedstock steering (4d lever): empty-evidence holes invite PROPOSE_RULE",
      "PROPOSE_RULE" in blk and "candidate_rules is EMPTY" in blk)
    T("wave-F steering: target-scoped preference + receipted_refs anchors",
      "SCOPED to a specific referent" in blk and '"receipted_refs"' in blk)
    ru = exe.add_rule(2, "A2 scores", {"action": "ACTION2"}, {"score_event": 1}, test_plan="p")
    s.commit()
    blk = exe.deficit_view_block(CTX)
    T("derivable evidence names the candidate rule", ru in blk)
    # fill everything: TESTED rules serving both keys => no deficit anywhere
    ru2 = exe.add_rule(3, "A1 levels", {"action": "ACTION1"}, {"level_event": 1}, test_plan="p")
    for tt, (r, ev) in ((4, (ru, "score_event")), (5, (ru, "score_event")),
                        (6, (ru2, "level_event")), (7, (ru2, "level_event"))):
        exe.write_consequence(tt, "ACTION2", None, "CC1", {"d": 1}, match=True,
                              predictor_id=r, predictor_kind="RULE", **{ev: 1})
        exe.recompute_rule_status(r, tt)
    s.commit()
    blk = exe.deficit_view_block(CTX)
    T("a complete chain renders 'none — do not invent sub-goals'",
      "DEFICIT: none" in blk, blk[:80])


def fills_hole_ingest() -> None:
    print("-- fills_hole: the LLM claims, the Executive proves --")
    s, exe, ids = _fresh("fh")
    g0 = ids["G0"]
    ru = exe.add_rule(2, "A2 scores", {"action": "ACTION2"}, {"score_event": 1}, test_plan="p")
    s.commit()
    good = {"op": "PROPOSE_GOAL", "statement": f"deliberately test {ru}",
            "bindings": [], "parent": g0, "fills_hole": f"{g0}/H1",
            "achievement_test": {"op": "COUNT", "entity": "consequence",
                                 "where": {"predictor": ru, "match": 1}, "value": 2},
            "discriminator": {"d": 1}, "evidence_ptrs": [2]}
    res = exe.validate_surveyor_proposals([good], 3)
    ent = res["admitted"][0]
    T("provable fill admitted with a VERIFIED edge", ent.get("edge_verified") is True, str(ent))
    edge = s.conn.execute("SELECT verified, hole_json FROM goal_edge WHERE run_id='fh' AND "
                          "parent_goal=? AND child_goal=?", (g0, ent["goal_id"])).fetchone()
    T("edge row records the proven hole",
      edge["verified"] == 1 and json.loads(edge["hole_json"])["via"] == ru)
    T("the verified child now leads the walk (rank key #1)",
      exe.walk_candidates()[0] == ent["goal_id"])
    bogus = {"op": "PROPOSE_GOAL", "statement": "engage R-nothing",
             "bindings": [], "parent": g0, "fills_hole": f"{g0}/H0",
             "achievement_test": {"op": "COUNT", "entity": "referent",
                                  "where": {"rung": "ENGAGED"}, "value": 1},
             "discriminator": {"d": 1}, "evidence_ptrs": [2]}
    res = exe.validate_surveyor_proposals([bogus], 4)
    ent2 = res["admitted"][0]
    T("unprovable fill: goal admitted, edge UNVERIFIED (cannot fake the chain)",
      ent2.get("edge_verified") is False)
    edge2 = s.conn.execute("SELECT verified, hole_json FROM goal_edge WHERE run_id='fh' AND "
                           "child_goal=?", (ent2["goal_id"],)).fetchone()
    T("unverified edge preserves the claim for audit",
      edge2["verified"] == 0 and "claim" in json.loads(edge2["hole_json"]))
    plain = {"op": "PROPOSE_GOAL", "statement": "score up",
             "bindings": [], "parent": g0,
             "achievement_test": {"op": "GT", "channel": "score", "value": 3},
             "discriminator": {"d": 1}, "evidence_ptrs": [2]}
    res = exe.validate_surveyor_proposals([plain], 5)
    n = s.conn.execute("SELECT COUNT(*) c FROM goal_edge WHERE run_id='fh'").fetchone()["c"]
    T("no fills_hole claim => no edge attempt", res["admitted"] and n == 2)


def contract_text() -> None:
    print("-- contract: the Surveyor is TAUGHT the milestone grammar + deficit protocol --")
    doc = organs.SurveyorProposals.__doc__
    for needle in ("DEFICIT", "fills_hole", "RULE_STATUS", "RUNG", "predictor",
                   '"entity":"consequence"', '"entity":"rule"', '"entity":"referent"',
                   "NOT already be true"):
        T(f"contract mentions {needle!r}", needle in doc)


def op_examples_lever() -> None:
    print("-- ARG_OP_EXAMPLES (P4 emission lever): gated worked examples --")
    from agents.arg import config as acfg
    was = acfg.OP_EXAMPLES
    try:
        acfg.OP_EXAMPLES = False
        T("default (Sonnet) contract carries NO examples block",
          "WORKED EXAMPLES" not in organs._surveyor_sig().instructions)
        acfg.OP_EXAMPLES = True
        sig = organs._surveyor_sig()
        T("lever ON appends worked per-op examples",
          "WORKED EXAMPLES" in sig.instructions and '"fills_hole":"G0001/H0"' in sig.instructions)
        T("the pinned base contract is untouched (with_instructions copy)",
          "WORKED EXAMPLES" not in organs.SurveyorProposals.instructions)
    finally:
        acfg.OP_EXAMPLES = was


def zero_information_gate() -> None:
    print("-- A3: a test already TRUE at admission is a zero-information goal --")
    s, exe, ids = _fresh("a3")
    ru = exe.add_rule(2, "A2 scores", {"action": "ACTION2"}, {"score_event": 1}, test_plan="p")
    s.commit()
    r = exe.admit_goal({"statement": f"confirm {ru} is a hypothesis", "bindings": [],
                        "achievement_test": {"op": "RULE_STATUS", "rule": ru,
                                             "is": "HYPOTHESIS"},
                        "discriminator": {"d": 1}, "evidence_ptrs": [2]}, 3, parent=ids["G0"])
    T("record-true-at-admission REJECTED (the gen3 'confirm demoted' class)",
      not r["ok"] and r["reason"] == "GATE2_TRUE_AT_ADMISSION", str(r))
    r = exe.admit_goal({"statement": f"test {ru} deliberately", "bindings": [],
                        "achievement_test": {"op": "RULE_STATUS", "rule": ru, "is": "TESTED"},
                        "discriminator": {"d": 1}, "evidence_ptrs": [2]}, 3, parent=ids["G0"])
    T("the same rule's FALSE-now milestone still admits", r["ok"], str(r))
    r = exe.admit_goal({"statement": "state is already NOT_FINISHED", "bindings": [],
                        "achievement_test": {"op": "EQ", "channel": "state",
                                             "value": "NOT_FINISHED"},
                        "discriminator": {"d": 1}, "evidence_ptrs": [2]}, 4,
                       parent=ids["G0"], ctx=CTX)
    T("channel-true-at-admission REJECTED when signals ctx is supplied",
      not r["ok"] and r["reason"] == "GATE2_TRUE_AT_ADMISSION", str(r))
    res = exe.validate_surveyor_proposals(
        [{"op": "PROPOSE_GOAL", "statement": "zero-info via surveyor", "bindings": [],
          "parent": ids["G0"],
          "achievement_test": {"op": "EQ", "channel": "score", "value": 0},
          "discriminator": {"d": 1}, "evidence_ptrs": [2]}], 5, ctx=CTX)
    T("surveyor path threads ctx into the gate",
      res["rejected"] and res["rejected"][0]["reason"] == "GATE2_TRUE_AT_ADMISSION")


def generative_cold_start() -> None:
    print("-- generative curriculum (batch-4 config): ARG_SEEDS=0 => G0 only --")
    s, exe, ids = _fresh("gen", seeds=False)
    n = s.conn.execute("SELECT COUNT(DISTINCT goal_id) c FROM goal WHERE run_id='gen'"
                       ).fetchone()["c"]
    T("seeds off writes ONLY the root (curriculum must be generated)",
      n == 1 and set(ids) == {"G0"})
    cs = exe.chain_status(ids["G0"], CTX)
    T("PINNED: the generative cold start is a total DEFICIT",
      cs["status"] == "DEFICIT" and all(h["evidence"]["candidate_rules"] == []
                                        for h in cs["holes"]))
    blk = exe.deficit_view_block(CTX)
    T("the first epoch's question is the full curriculum brief",
      f"{ids['G0']}/H0" in blk and "PROPOSE_GOAL" in blk)


def chain_metrics() -> None:
    print("-- §8 chain metrics (tolerant of pre-chain DBs) --")
    import probe_arg_metrics as pam
    s, exe, ids = _fresh("cm")
    g0 = ids["G0"]
    ru = exe.add_rule(2, "A2 scores", {"action": "ACTION2"}, {"score_event": 1}, test_plan="p")
    s.commit()
    cs = exe.chain_status(g0, CTX)
    exe.deficit_stamp(g0, cs["holes"], 2)
    made = exe.auto_fill_holes(g0, cs["holes"], 3)
    for tt in (4, 5):
        exe.write_consequence(tt, "ACTION2", None, "CC1", {"d": 1}, match=True,
                              predictor_id=ru, predictor_kind="RULE", score_event=1)
        exe.recompute_rule_status(ru, tt)
    exe.evaluate_all_goals(6, CTX)
    s.commit()
    # a real (empty) probe DB so compute() can open it
    from agents.arg.probe_db import ProbeStore
    pdb = tempfile.mktemp(suffix=".db")
    ProbeStore(pdb)
    dbfile = s.conn.execute("PRAGMA database_list").fetchone()["file"]
    mt = pam.compute(dbfile, pdb, run="cm")
    T("deficit stamps counted", mt["deficit_stamps"] == 1 and mt["deficit_goals"] == 1)
    T("milestone goals + conversion computed",
      mt["milestone_goals"] == 1 and mt["milestone_accepted"] == 1
      and mt["milestone_conversion"] == 1.0, str({k: mt[k] for k in
                                                  ("milestone_goals", "milestone_accepted")}))
    T("verified edges counted", mt["edges_verified"] == 1 and mt["edges_unverified"] == 0)
    # pre-chain DB (what batches 1–3 are): a real store MINUS the chain tables
    s2, exe2, ids2 = _fresh("cmold")
    db2 = s2.conn.execute("PRAGMA database_list").fetchone()["file"]
    s2.conn.executescript("DROP TABLE deficit_stamp; DROP TABLE goal_edge;")
    s2.conn.commit()
    try:
        mt_old = pam.compute(db2, pdb, run="cmold")
        T("pre-chain DB: chain keys degrade to None, no crash",
          mt_old["deficit_stamps"] is None and mt_old["edges_verified"] is None)
    except Exception as e:
        T("pre-chain DB: chain keys degrade to None, no crash", False, str(e))


def gds_attribution() -> None:
    print("-- GDS attribution: bind = WRONG emitted id; bypass = abandon (P2 semantics) --")
    import probe_arg_metrics as pam
    from agents.arg.probe_db import ProbeStore
    s, exe, ids = _fresh("gds")
    ref = "G0001|ACTION6|R0001|RU0001"
    # untargeted probe while the reference step names a target => BYPASS (abandon)
    exe.record_turn(1, "ACTION1", {}, None, "h0", "h1", {"cells_changed": 1}, {"d": 1},
                    0, 0, "NOT_FINISHED", None, "PROBE",
                    shadow_step_id=ref, drift_ref="SHADOW")
    # targeted at the WRONG referent => join failure (bind)
    exe.record_turn(2, "ACTION6", {"x": 1, "y": 1}, "R0002", "h1", "h2",
                    {"cells_changed": 1}, {"d": 1}, 0, 0, "NOT_FINISHED", None, "PROBE",
                    shadow_step_id=ref, drift_ref="SHADOW")
    # aligned beat => neither
    exe.record_turn(3, "ACTION6", {"x": 2, "y": 2}, "R0001", "h2", "h3",
                    {"cells_changed": 1}, {"d": 1}, 0, 0, "NOT_FINISHED", None, "PROBE",
                    shadow_step_id=ref, drift_ref="SHADOW")
    s.commit()
    # LIVE reference cases: a faithful untargeted step execution is ALIGNED;
    # an aimed live emission landing on the wrong referent is BIND
    cid = exe.write_commitment(ids["G0"], [
        {"kind": "INTERACT", "action": "ACTION1", "target_ref": "R0001",
         "predicted": {"cells_changed": "nonzero"}},
        {"kind": "INTERACT", "action": "ACTION6", "target_ref": "R0001",
         "predicted": {"cells_changed": "nonzero"}}], 4)
    exe.record_turn(4, "ACTION1", {}, None, "h3", "h4", {"cells_changed": 1}, {"d": 1},
                    0, 0, "NOT_FINISHED", None, "COMMITMENT_STEP",
                    commitment_step_id=f"{cid}-S0", drift_ref="LIVE")
    exe.record_turn(5, "ACTION6", {"x": 5, "y": 5}, "R0002", "h4", "h5",
                    {"cells_changed": 1}, {"d": 1}, 0, 0, "NOT_FINISHED", None,
                    "COMMITMENT_STEP", commitment_step_id=f"{cid}-S1", drift_ref="LIVE")
    s.commit()
    pdb = tempfile.mktemp(suffix=".db")
    ProbeStore(pdb)
    dbfile = s.conn.execute("PRAGMA database_list").fetchone()["file"]
    mt = pam.compute(dbfile, pdb, run="gds")
    T("5 reference beats; bind = aimed wrong-referent landings only (shadow + live)",
      mt["drift_ref_beats"] == 5 and mt["gds_bind"] == round(2 / 5, 3),
      f"beats={mt['drift_ref_beats']} bind={mt['gds_bind']}")
    T("shadow bypass counts as ABANDON; faithful untargeted live step is ALIGNED",
      mt["gds_abandon"] == round(1 / 5, 3), str(mt["gds_abandon"]))
    T("disjoint by construction (drift_total = bind + abandon)",
      mt["drift_total"] == round(3 / 5, 3))


def main() -> None:
    deficit_block()
    fills_hole_ingest()
    contract_text()
    op_examples_lever()
    zero_information_gate()
    generative_cold_start()
    chain_metrics()
    gds_attribution()
    print(f"\n{'ALL PASS' if not FAILS else f'{len(FAILS)} FAILURES: {FAILS}'}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
