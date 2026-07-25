#!/usr/bin/env python3
"""ARG M5 thesis-engine tests: consequence-grounding (rule TESTED only via
pre-registered post-creation matched receipts; CHARACTERIZED unreachable
otherwise), six admission gates, reopen semantics (G0 latches; LEARN-* reopens
on a fresh context class), deterministic rank, Revision-Evidence gate.
Run: uv run python tests/test_arg_engine.py"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.arg.store import Store  # noqa: E402
from agents.arg.adapter import ARCAdapter, Component  # noqa: E402
from agents.arg.executive import Executive  # noqa: E402
from agents.arg import seeds as sd  # noqa: E402

FAILS = []


def T(name, cond, detail=""):
    print(f"  [{'ok ' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def _mk(color, cells):
    xs = [c[0] for c in cells]; ys = [c[1] for c in cells]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    n = len(cells)
    return Component(color=color, cells=frozenset(cells), bbox=(x0, y0, x1, y1),
                     centroid=(round(sum(xs) / n), round(sum(ys) / n)), size=n,
                     shape=frozenset((x - x0, y - y0) for x, y in cells))


def main() -> None:
    s = Store(tempfile.mktemp(suffix=".db"))
    rid = "eng"
    s.register_run(rid, "ls20", "sonnet", 0, "{}", 6000, "t")
    exe = Executive(s, ARCAdapter(), rid)
    ids = sd.write_seeds(s, rid, 0)
    ref = exe.mint_referent(_mk(7, [(21, 31), (22, 31)]), 1)
    s.commit()

    # ---- consequence-grounding: a rule TESTED only via its OWN pre-registered
    #      post-creation matched receipts ----
    rule = exe.add_rule(5, "WHEN ctx DO ACTION1 THEN diff", {"op": "EQ", "channel": "state", "value": "x"},
                        {"shape": "moved"}, test_plan="predict")
    # retrospective receipt (turn_id ≤ created) and a ctx-only receipt (predictor NULL): must NOT count
    exe.write_consequence(3, "ACTION1", ref, "CC1", {"x": 1}, match=True, predictor_id=rule,
                          predictor_kind="RULE")      # turn 3 ≤ created 5 → ignored
    exe.write_consequence(6, "ACTION1", ref, "CC1", {"x": 1}, match=True, predictor_id=None)  # ctx-only
    s.commit()
    T("rule stays HYPOTHESIS on retrospective + ctx-only receipts",
      exe.recompute_rule_status(rule, 7) == "HYPOTHESIS")
    T("CHARACTERIZED unreachable without a pre-registered match",
      exe.recompute_rung(ref, 7) in ("ANCHORED", "ENGAGED"))
    # now two genuine pre-registered post-creation matches
    exe.write_consequence(7, "ACTION1", ref, "CC1", {"x": 1}, match=True, predictor_id=rule,
                          predictor_kind="RULE")
    exe.write_consequence(8, "ACTION1", ref, "CC1", {"x": 1}, match=True, predictor_id=rule,
                          predictor_kind="RULE")
    s.commit()
    T("rule → TESTED on 2 pre-registered matches", exe.recompute_rule_status(rule, 9) == "TESTED")
    T("referent → CHARACTERIZED via the TESTED rule's receipt",
      exe.recompute_rung(ref, 9) == "CHARACTERIZED")
    # a third mismatch beyond K_DEMOTE demotes (never deletes)
    for tt in (10, 11, 12):
        exe.write_consequence(tt, "ACTION1", ref, "CC1", {"x": 0}, match=False, predictor_id=rule,
                              predictor_kind="RULE")
    s.commit()
    T("rule DEMOTED past K mismatches", exe.recompute_rule_status(rule, 13) == "DEMOTED")

    # ---- six admission gates ----
    good = {"statement": "test R on A2", "bindings": [ref],
            "achievement_test": {"op": "GT", "channel": "score", "vs": "prev"},
            "discriminator": {"delta": "any"}, "evidence_ptrs": [5]}
    r = exe.admit_goal(good, 14, parent=ids["G0"])
    T("gate: well-formed goal admitted", r["ok"], str(r))
    T("gate1 unresolved binding rejected",
      exe.admit_goal({**good, "bindings": ["R9999"]}, 14, parent=ids["G0"])["reason"] == "GATE1_UNRESOLVED_BINDING")
    T("gate2 incompilable test rejected",
      exe.admit_goal({**good, "achievement_test": {"op": "EQ", "value": "looks_won"}}, 14,
                     parent=ids["G0"])["reason"] == "GATE2_TEST_INCOMPILABLE")
    T("gate3 no discriminator rejected",
      exe.admit_goal({**good, "discriminator": None, "achievement_test":
                      {"op": "GT", "channel": "levels_completed", "vs": "prev"}}, 14,
                     parent=ids["G0"])["reason"] == "GATE3_NO_DISCRIMINATOR")
    T("gate4 duplicate sibling rejected",
      exe.admit_goal(good, 15, parent=ids["G0"])["reason"] == "GATE4_DUPLICATE_SIBLING")
    T("gate5 no-evidence rejected",
      exe.admit_goal({**good, "evidence_ptrs": [], "achievement_test":
                      {"op": "GT", "channel": "lives", "vs": "prev"}}, 14,
                     parent=ids["G0"])["reason"] == "GATE5_NO_EVIDENCE")

    # ---- reopen semantics ----
    # G0 (MONOTONE_TERMINAL) must NOT reopen on a non-progress beat
    ctx_flat = {"cur": {"levels_completed": 0, "state": "NOT_FINISHED", "score": 0},
                "prev": {"levels_completed": 0, "state": "NOT_FINISHED", "score": 0}}
    exe._append_status(16, "GOAL", ids["G0"], "VALIDATED", "ACCEPTED", "fired earlier")
    s.commit()
    trans = exe.evaluate_all_goals(17, ctx_flat)
    T("G0 not spuriously REOPENED (monotone latch)",
      not any(g == ids["G0"] and to == "REOPENED" for g, _, to in trans))

    # LEARN-ACTIONS: mark ACCEPTED, then mint a fresh context class → must REOPEN
    la = ids["LEARN-ACTIONS"]
    exe._append_status(17, "GOAL", la, "PROPOSED", "ACCEPTED", "claimed complete")
    s.commit()
    exe.mint_context_class(1, "divergent", 18, 0)   # a fresh class flips LEARN_ACTIONS false
    s.commit()
    trans2 = exe.evaluate_all_goals(18, ctx_flat)
    T("LEARN-ACTIONS REOPENS when a fresh context class is minted",
      any(g == la and to == "REOPENED" for g, _, to in trans2))

    # ---- deterministic rank ----
    rk1 = exe.compute_rank(ids["G0"])
    rk2 = exe.compute_rank(ids["G0"])
    T("compute_rank deterministic", rk1["order"] == rk2["order"])

    # ---- Revision-Evidence gate ----
    premise = {"RU0001", ref}
    T("abort rejected: not contradiction class",
      exe.revision_evidence_gate(premise, 10, "NOTE", 12, ref)["reason"] == "NOT_CONTRADICTION_CLASS")
    T("abort rejected: stale evidence",
      exe.revision_evidence_gate(premise, 15, "CONSEQUENCE_MISMATCH", 12, ref)["reason"] == "STALE_EVIDENCE")
    T("abort rejected: irrelevant evidence",
      exe.revision_evidence_gate(premise, 10, "CONSEQUENCE_MISMATCH", 12, "R9999")["reason"] == "IRRELEVANT_EVIDENCE")
    T("abort admitted: contradiction + fresh + relevant",
      exe.revision_evidence_gate(premise, 10, "CONSEQUENCE_MISMATCH", 12, ref)["ok"] is True)

    s.close()
    print(f"\n{'PASS' if not FAILS else 'FAIL: ' + str(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
