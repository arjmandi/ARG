#!/usr/bin/env python3
"""ARG M7 tests: epoch trigger set + rate limit (T1 exempt), fission-check
statistic, divergence context-class minting → reopen, Surveyor-proposal ingest
routing + SRR. Run: uv run python tests/test_arg_epochs.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.arg.store import Store  # noqa: E402
from agents.arg.adapter import ARCAdapter, Component  # noqa: E402
from agents.arg.executive import Executive, EpochController  # noqa: E402
from agents.arg import seeds as sd  # noqa: E402

FAILS = []


def T(name, cond, detail=""):
    print(f"  [{'ok ' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def main() -> None:
    # ---- EpochController: trigger set + rate limit ----
    ec = EpochController()
    fire, trig = ec.check(5, contradiction=True, goal_transition=False, comp_fail=False, level_changed=False)
    T("T1 contradiction fires immediately", fire and trig == "T1")
    ec.fired(5)
    # within rate limit (C=10 default): T2-T5 suppressed
    f2, _ = ec.check(8, False, True, False, False)
    T("rate limit binds T2-T5 within C beats", not f2)
    # T1 remains exempt even within the window
    f1, t1 = ec.check(8, True, False, False, False)
    T("T1 exempt from rate limit", f1 and t1 == "T1")
    # after C beats, a level boundary fires T5
    f5, t5 = ec.check(20, False, False, False, True)
    T("T5 boundary fires after rate window", f5 and t5 == "T5")
    ec.fired(20)
    # T4 stall: S=12 beats with no evidence
    ec.note_evidence(20)
    f4, t4 = ec.check(20 + 13, False, False, False, False)
    T("T4 stall fires after S beats no evidence", f4 and t4 == "T4")
    # A9: triggers off → T1/T4 disabled, only T2/T5
    ec2 = EpochController()
    T("A9 disables T1", ec2.check(5, True, False, False, False, triggers_on=False)[0] is False)
    T("A9 disables T4", ec2.check(30, False, False, False, False, triggers_on=False)[0] is False)
    T("A9 keeps T2", ec2.check(30, False, True, False, False, triggers_on=False)[1] == "T2")

    # ---- store-backed checks ----
    s = Store(tempfile.mktemp(suffix=".db"))
    rid = "ep"
    s.register_run(rid, "ls20", "sonnet", 0, "{}", 6000, "t")
    exe = Executive(s, ARCAdapter(), rid)
    ids = sd.write_seeds(s, rid, 0)
    ref = exe.mint_referent(Component(color=7, cells=frozenset([(5, 5)]), bbox=(5, 5, 5, 5),
                                      centroid=(5, 5), size=1, shape=frozenset([(0, 0)])), 1)
    s.commit()

    # fission-check: mismatches (>K_fiss=3) correlate with a signature variant
    for i, (m, sig) in enumerate([(1, "A"), (1, "A"), (1, "A"), (1, "A"),
                                  (0, "B"), (0, "B"), (0, "B"), (0, "B")]):
        exe.write_consequence(10 + i, "ACTION1", ref, "CC1", {"x": 1}, match=bool(m))
        s.conn.execute("INSERT INTO binding_record (run_id, turn_id, component_hash, anchor_cells_json, "
                       "anchor_bbox_json, anchor_signature, bound_to, is_new, margin) "
                       "VALUES (?,?,?,?,?,?,?,0,0.9)",
                       (rid, 10 + i, f"h{i}", "[]", "[]", sig, ref))
    s.commit()
    fc = exe.fission_check(ref)
    T("fission-check fires on feature-correlated mismatch",
      fc["fired"] and abs(fc["r"]) >= 0.5, str(fc))
    T("fission-check quiet with few mismatches",
      exe.fission_check("R9999")["fired"] is False)

    # divergence context class (bucketed zero/nonzero regimes) → LEARN-ACTIONS reopens
    cc0 = exe.current_context_class(0, 29)
    exe.write_consequence(30, "ACTION1", ref, cc0, {"cells_changed": 52}, match=True)
    s.commit()
    T("same bucket (nonzero→nonzero) does NOT mint",
      exe.maybe_diverge_context("ACTION1", 7, 0, 31) is None)
    newcc = exe.maybe_diverge_context("ACTION1", 0, 0, 32)   # zero after nonzero = new regime
    T("divergent bucket (nonzero→zero) mints a new context class", newcc is not None)
    T("the fresh class becomes the current regime",
      exe.current_context_class(0, 33) == newcc)

    # Surveyor ingest routing
    props = [
        {"op": "PROPOSE_GOAL", "statement": "test", "bindings": [ref],
         "achievement_test": {"op": "GT", "channel": "score", "vs": "prev"},
         "discriminator": {"d": 1}, "evidence_ptrs": [5], "parent": ids["G0"]},
        {"op": "PROPOSE_RULE", "template": "t", "ctx": {}, "effect": {}},          # no test_plan → reject
        {"op": "PROPOSE_RULE", "template": "t2", "ctx": {"action": "ACTION1", "target": None},
         "effect": {"cells_changed": "nonzero"}, "test_plan": "predict"},
        {"op": "PROPOSE_RULE", "template": "t3", "ctx": {"action": "FLY"}, "effect": {},
         "test_plan": "predict"},                                                   # ctx not closed → reject
        {"op": "ABORT_STEP", "step_id": "C0-S0",
         "evidence_ptr": "note:whatever"},   # dangling step → rejected, SRR metered
    ]
    res = exe.validate_surveyor_proposals(props, 40)
    admitted_ops = [a["op"] for a in res["admitted"]]
    rejected_reasons = [r["reason"] for r in res["rejected"]]
    T("PROPOSE_GOAL admitted through 6 gates", "PROPOSE_GOAL" in admitted_ops)
    T("PROPOSE_RULE without test_plan rejected",
      "SURVEYOR_RULE_NEEDS_TEST_PLAN" in rejected_reasons)
    T("PROPOSE_RULE with test_plan + closed ctx/effect admitted", "PROPOSE_RULE" in admitted_ops)
    T("PROPOSE_RULE with non-closed ctx rejected", "RULE_CTX_NOT_CLOSED" in rejected_reasons)
    T("inadmissible ABORT_STEP rejected + SRR metered (gate resolves against the store)",
      "NO_SUCH_STEP" in rejected_reasons and res["srr"] == 1)

    s.close()
    print(f"\n{'PASS' if not FAILS else 'FAIL: ' + str(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
