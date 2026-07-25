#!/usr/bin/env python3
"""ARG G1 chain tests: the sufficiency recognizer + verified-fill edges +
milestone grammar (proposal §2, amendments A1/A2; cold-start evaluation §2).

PINNED (pre-registered falsified-if): on an empty store the recognizer must
report total DEFICIT with empty-evidence holes — anything else is a bug.

Run: uv run python tests/test_arg_chain1.py"""
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.arg.store import Store  # noqa: E402
from agents.arg.adapter import ARCAdapter, Component  # noqa: E402
from agents.arg.executive import Executive  # noqa: E402
from agents.arg import predicates as pr  # noqa: E402
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


def _fresh(rid):
    s = Store(tempfile.mktemp(suffix=".db"))
    s.register_run(rid, "ls20", "sonnet", 0, "{}", 6000, "t")
    exe = Executive(s, ARCAdapter(), rid)
    ids = sd.write_seeds(s, rid, 0)
    return s, exe, ids


CTX = {"cur": {"score": 0, "levels_completed": 0, "state": "NOT_FINISHED"},
       "prev": {"score": 0, "levels_completed": 0, "state": "NOT_FINISHED"}}


def grammar() -> None:
    print("-- A1 milestone grammar (closed where + status predicates) --")
    ch = ARCAdapter().signal_channels()
    ok, _ = pr.compiles({"op": "EXISTS", "entity": "consequence",
                         "where": {"predictor": "RU0001", "match": 1}}, ch)
    T("EXISTS consequence where{predictor,match} compiles", ok)
    ok, _ = pr.compiles({"op": "COUNT", "entity": "rule",
                         "where": {"status": "TESTED"}, "value": 2}, ch)
    T("COUNT rule where{status} compiles", ok)
    ok, _ = pr.compiles({"op": "COUNT", "entity": "referent",
                         "where": {"rung": "ENGAGED"}, "value": 1}, ch)
    T("COUNT referent where{rung} compiles", ok)
    ok, why = pr.compiles({"op": "COUNT", "entity": "rule", "where": {}}, ch)
    T("COUNT without value rejected", not ok, why)
    ok, why = pr.compiles({"op": "EXISTS", "entity": "consequence",
                           "where": {"color": 7}}, ch)
    T("appearance field in where rejected (closed vocabulary)", not ok, why)
    ok, why = pr.compiles({"op": "EXISTS", "entity": "door", "where": {}}, ch)
    T("unknown entity rejected", not ok, why)
    ok, _ = pr.compiles({"op": "RULE_STATUS", "rule": "RU0001", "is": "TESTED"}, ch)
    T("RULE_STATUS compiles", ok)
    ok, why = pr.compiles({"op": "RULE_STATUS", "rule": "RU0001", "is": "PROVEN"}, ch)
    T("RULE_STATUS with invented status rejected", not ok, why)
    ok, _ = pr.compiles({"op": "RUNG", "ref": "R0001", "at_least": "ENGAGED"}, ch)
    T("RUNG compiles", ok)
    ok, why = pr.compiles({"op": "RUNG", "ref": "R0001", "at_least": "FAMOUS"}, ch)
    T("RUNG with invented rung rejected", not ok, why)
    T("milestone predicates classify RECORD_QUANTIFIED (re-checked every beat)",
      pr.classify_reopen({"op": "RULE_STATUS", "rule": "RU0001", "is": "TESTED"})
      == "RECORD_QUANTIFIED"
      and pr.classify_reopen({"op": "RUNG", "ref": "R0001", "at_least": "ENGAGED"})
      == "RECORD_QUANTIFIED")


def record_eval() -> None:
    print("-- where-filtered record evaluation (stamped rows only) --")
    s, exe, ids = _fresh("rec")
    ref = exe.mint_referent(_mk(7, [(1, 1), (2, 1)]), 1)
    ru = exe.add_rule(2, "WHEN CC DO ACTION2 THEN score",
                      {"action": "ACTION2"}, {"score_event": 1}, test_plan="p")
    exe.write_consequence(3, "ACTION2", ref, "CC1", {"d": 1}, match=True,
                          predictor_id=ru, predictor_kind="RULE", score_event=1)
    exe.write_consequence(4, "ACTION1", None, "CC1", {"d": 0})
    s.commit()
    ev = exe._record_eval_factory(CTX)
    T("EXISTS consequence{predictor,match=1} true on the matched receipt",
      ev({"op": "EXISTS", "entity": "consequence",
          "where": {"predictor": ru, "match": 1}}))
    T("EXISTS false for a rule with no receipts",
      not ev({"op": "EXISTS", "entity": "consequence",
              "where": {"predictor": "RU9999", "match": 1}}))
    T("COUNT consequence where{action} honors the filter",
      ev({"op": "COUNT", "entity": "consequence", "where": {"action": "ACTION2"},
          "value": 1})
      and not ev({"op": "COUNT", "entity": "consequence", "where": {"action": "ACTION2"},
                  "value": 2}))
    T("COUNT consequence where{score_event} counts stamped events",
      ev({"op": "COUNT", "entity": "consequence", "where": {"score_event": 1},
          "value": 1}))
    T("COUNT with cmp EQ is exact",
      ev({"op": "COUNT", "entity": "consequence", "where": {}, "value": 2, "cmp": "EQ"}))
    T("RULE_STATUS HYPOTHESIS true on a fresh rule",
      ev({"op": "RULE_STATUS", "rule": ru, "is": "HYPOTHESIS"})
      and not ev({"op": "RULE_STATUS", "rule": ru, "is": "TESTED"}))
    T("COUNT rule where{status:HYPOTHESIS} sees it",
      ev({"op": "COUNT", "entity": "rule", "where": {"status": "HYPOTHESIS"}, "value": 1})
      and not ev({"op": "COUNT", "entity": "rule", "where": {"status": "TESTED"},
                  "value": 1}))
    # promote: two pre-registered post-creation matches
    exe.write_consequence(5, "ACTION2", ref, "CC1", {"d": 1}, match=True,
                          predictor_id=ru, predictor_kind="RULE", score_event=1)
    exe.recompute_rule_status(ru, 6)
    s.commit()
    T("RULE_STATUS flips to TESTED after promotion",
      ev({"op": "RULE_STATUS", "rule": ru, "is": "TESTED"}))
    T("RUNG default ANCHORED: at_least ENGAGED false",
      not ev({"op": "RUNG", "ref": ref, "at_least": "ENGAGED"}))
    exe._append_status(7, "REFERENT_RUNG", ref, "ANCHORED", "ENGAGED", "test")
    s.commit()
    T("RUNG at_least is an order (ENGAGED satisfies ANCHORED-or-better)",
      ev({"op": "RUNG", "ref": ref, "at_least": "ENGAGED"})
      and ev({"op": "RUNG", "ref": ref, "at_least": "ANCHORED"})
      and not ev({"op": "RUNG", "ref": ref, "at_least": "CHARACTERIZED"}))
    T("COUNT referent where{rung} filters by current rung",
      ev({"op": "COUNT", "entity": "referent", "where": {"rung": "ENGAGED"}, "value": 1}))
    T("full eval_now routes milestone ops through the record evaluator",
      pr.eval_now({"op": "AND", "args": [
          {"op": "RULE_STATUS", "rule": ru, "is": "TESTED"},
          {"op": "EXISTS", "entity": "consequence", "where": {"predictor": ru, "match": 1}},
      ]}, CTX, ev))


def cold_start() -> None:
    print("-- COLD START (pinned): empty store => total DEFICIT, empty evidence --")
    s, exe, ids = _fresh("cold")
    g0 = ids["G0"]
    nd = exe.needs(g0, CTX)
    T("needs(G0) = its effect keys under zero knowledge",
      {n["key"] for n in nd if n["kind"] == "effect"} == {"level_event", "score_event"},
      str(nd))
    cs = exe.chain_status(g0, CTX)
    T("PINNED: chain_status(G0) on empty store = DEFICIT", cs["status"] == "DEFICIT", str(cs))
    T("PINNED: every hole is effect-typed with EMPTY evidence",
      len(cs["holes"]) == 2 and all(
          h["kind"] == "effect" and h["evidence"]["candidate_rules"] == []
          and h["evidence"]["action_model"] is False for h in cs["holes"]), str(cs["holes"]))
    T("seeded LEARN goals (no verified edges) cannot fake completeness",
      cs["status"] == "DEFICIT")  # LEARN-* exist as G0 children yet cover nothing


def evidence_derivability() -> None:
    print("-- hole evidence names its own fills (auto-fill tier feed) --")
    s, exe, ids = _fresh("evd")
    g0 = ids["G0"]
    ru = exe.add_rule(2, "WHEN CC DO ACTION2 ON R THEN level",
                      {"action": "ACTION2"}, {"level_event": 1}, test_plan="p")
    s.commit()
    cs = exe.chain_status(g0, CTX)
    hole = next(h for h in cs["holes"] if h["key"] == "level_event")
    T("HYPOTHESIS rule with the needed effect appears as candidate",
      cs["status"] == "DEFICIT" and hole["evidence"]["candidate_rules"] == [ru], str(hole))
    other = next(h for h in cs["holes"] if h["key"] == "score_event")
    T("unrelated hole stays empty-evidence", other["evidence"]["candidate_rules"] == [])
    s.conn.execute("INSERT INTO action_model (run_id, seq, turn_id, action, dx, dy, "
                   "quantum, support, mover_sig) VALUES ('evd',1,3,'ACTION1',0,-1,4,3,'m')")
    s.commit()
    cs = exe.chain_status(g0, CTX)
    T("action-model presence flips the reach bit in evidence",
      all(h["evidence"]["action_model"] is True for h in cs["holes"]))
    # DEMOTED candidates disappear from evidence
    for tt in (4, 5, 6):
        exe.write_consequence(tt, "ACTION2", None, "CC1", {"d": 0}, match=False,
                              predictor_id=ru, predictor_kind="RULE")
    exe.recompute_rule_status(ru, 7)
    s.commit()
    cs = exe.chain_status(g0, CTX)
    hole = next(h for h in cs["holes"] if h["key"] == "level_event")
    T("DEMOTED rule leaves the candidate list", hole["evidence"]["candidate_rules"] == [])


def verified_fill() -> None:
    print("-- verified fill: mechanical proof, LLM cannot assert it --")
    s, exe, ids = _fresh("vf")
    g0 = ids["G0"]
    ru = exe.add_rule(2, "WHEN CC DO ACTION2 THEN score",
                      {"action": "ACTION2"}, {"score_event": 1}, test_plan="p")
    ru_shape = exe.add_rule(2, "WHEN CC DO ACTION3 THEN shape",
                            {"action": "ACTION3"}, {"shape": "moved"}, test_plan="p")
    s.commit()
    okk, hole = exe.verify_fill(g0, {"op": "EXISTS", "entity": "consequence",
                                     "where": {"predictor": ru, "match": 1}}, CTX)
    T("knowledge fill: matched-receipt milestone over a rule whose effect ⊇ need",
      okk and hole["via"] == ru and hole["keys"] == ["score_event"], str(hole))
    okk, hole = exe.verify_fill(g0, {"op": "RULE_STATUS", "rule": ru, "is": "TESTED"}, CTX)
    T("knowledge fill: RULE_STATUS(RU,TESTED) form accepted", okk and hole["via"] == ru)
    okk, hole = exe.verify_fill(g0, {"op": "GT", "channel": "score", "vs": "prev"}, CTX)
    T("signal fill: child effect-keys ⊆ parent needs", okk and hole["via"] == "signal"
      and hole["keys"] == ["score_event"], str(hole))
    okk, _ = exe.verify_fill(g0, {"op": "EXISTS", "entity": "consequence",
                                  "where": {"predictor": ru_shape, "match": 1}}, CTX)
    T("refused: milestone over a rule with no needed effect", not okk)
    okk, _ = exe.verify_fill(g0, {"op": "RUNG", "ref": "R0001", "at_least": "ENGAGED"}, CTX)
    T("refused: rung milestone alone proves no parent need", not okk)
    okk, _ = exe.verify_fill(g0, {"op": "EXISTS", "entity": "consequence",
                                  "where": {"predictor": "RU9999", "match": 1}}, CTX)
    T("refused: milestone naming a nonexistent rule", not okk)


def verdicts() -> None:
    print("-- chain_status verdicts on constructed trees --")
    s, exe, ids = _fresh("ver")
    g0 = ids["G0"]
    ref = exe.mint_referent(_mk(7, [(1, 1)]), 1)
    # parent with a level-only test (G0's disjunction would also accept score)
    r = exe.admit_goal({"statement": "advance the level", "bindings": [ref],
                        "achievement_test": {"op": "GT", "channel": "levels_completed",
                                             "vs": "prev"},
                        "discriminator": {"d": 1}, "evidence_ptrs": [1]}, 2, parent=g0)
    parent = r["goal_id"]
    cs = exe.chain_status(parent, CTX)
    T("no rules, no children => DEFICIT", cs["status"] == "DEFICIT"
      and cs["holes"][0]["key"] == "level_event")
    # hypothesis rule appears; milestone child; verified edge
    ru = exe.add_rule(3, "WHEN CC DO ACTION6 ON R THEN level",
                      {"action": "ACTION6", "target": ref}, {"level_event": 1},
                      test_plan="p")
    mtest = {"op": "EXISTS", "entity": "consequence",
             "where": {"predictor": ru, "match": 1}}
    okk, hole = exe.verify_fill(parent, mtest, CTX)
    T("fill verifies against the hypothesis rule", okk, str(hole))
    r = exe.admit_goal({"statement": f"test {ru}", "bindings": [ref],
                        "achievement_test": mtest, "discriminator": {"d": 1},
                        "evidence_ptrs": [3], "provenance": "DEFICIT"}, 4, parent=parent)
    child = r["goal_id"]
    exe.add_goal_edge(parent, child, hole, verified=True, turn_id=4)
    s.commit()
    T("milestone child over a live HYPOTHESIS rule is COMPILABLE (experiment path)",
      exe.chain_status(child, CTX)["status"] == "COMPILABLE")
    T("parent with every need covered by a verified child => REDUCIBLE",
      exe.chain_status(parent, CTX)["status"] == "REDUCIBLE")
    T("'enough goals' answered mechanically: holes = ∅",
      exe.chain_status(parent, CTX)["holes"] == [])
    # demotion re-opens the chain honestly (§9.3): child dead-ends => parent DEFICIT
    for tt in (5, 6, 7):
        exe.write_consequence(tt, "ACTION6", ref, "CC1", {"d": 0}, match=False,
                              predictor_id=ru, predictor_kind="RULE")
    exe.recompute_rule_status(ru, 8)
    s.commit()
    ccs = exe.chain_status(child, CTX)
    T("milestone over a DEMOTED rule is a dead end (DEFICIT, record hole)",
      ccs["status"] == "DEFICIT" and ccs["holes"][0]["kind"] == "record"
      and ccs["holes"][0]["evidence"]["rule_status"] == "DEMOTED", str(ccs))
    T("parent hole re-opens after the child's rule demotes",
      exe.chain_status(parent, CTX)["status"] == "DEFICIT")
    # TESTED serving rule => COMPILABLE directly (means analysis)
    ru2 = exe.add_rule(9, "WHEN CC DO ACTION1 THEN level",
                       {"action": "ACTION1"}, {"level_event": 1}, test_plan="p")
    for tt in (10, 11):
        exe.write_consequence(tt, "ACTION1", None, "CC1", {"d": 1}, match=True,
                              predictor_id=ru2, predictor_kind="RULE", level_event=1)
    exe.recompute_rule_status(ru2, 12)
    s.commit()
    T("a TESTED rule whose effect serves the test => COMPILABLE",
      exe.chain_status(parent, CTX)["status"] == "COMPILABLE")
    # ACCEPTED short-circuits; record pursuits reduce; cycles terminate
    exe._append_status(13, "GOAL", parent, "VALIDATED", "ACCEPTED", "test")
    s.commit()
    T("ACCEPTED goal is trivially COMPILABLE",
      exe.chain_status(parent, CTX)["status"] == "COMPILABLE")
    T("pure record pursuit (LEARN-class) is REDUCIBLE via probes, holes = ∅",
      exe.chain_status(ids["LEARN-RULES"], CTX) == {"status": "REDUCIBLE", "holes": []})
    # budget exhaustion: a REJECTED child stops covering; the parent re-opens
    exe._append_status(13, "GOAL", child, "PROPOSED", "REJECTED", "NEVER_VALIDATED")
    s.commit()
    T("REJECTED (NEVER_VALIDATED) milestone is terminal DEFICIT",
      exe.chain_status(child, CTX)["status"] == "DEFICIT")
    T("parent stays COMPILABLE via its own TESTED rule despite the dead child",
      exe.chain_status(parent, CTX)["status"] == "COMPILABLE")
    ga = exe.admit_goal({"statement": "a", "bindings": [],
                         "achievement_test": {"op": "GT", "channel": "score", "vs": "prev"},
                         "discriminator": {"d": 1}, "evidence_ptrs": [1]}, 14, parent=g0)
    gb = exe.admit_goal({"statement": "b", "bindings": [],
                         "achievement_test": {"op": "GT", "channel": "score", "value": 5},
                         "discriminator": {"d": 1}, "evidence_ptrs": [1]}, 14, parent=g0)
    exe.add_goal_edge(ga["goal_id"], gb["goal_id"], {"keys": ["score_event"]}, True, 14)
    exe.add_goal_edge(gb["goal_id"], ga["goal_id"], {"keys": ["score_event"]}, True, 14)
    s.commit()
    cyc = exe.chain_status(ga["goal_id"], CTX)
    T("mutual edges terminate (cycle guard) and cover nothing",
      cyc["status"] == "DEFICIT", str(cyc))


def rank_and_store() -> None:
    print("-- edge-aware rank (§5.3 key #1) + append-only goal_edge --")
    s, exe, ids = _fresh("rnk")
    g0 = ids["G0"]
    ga = exe.admit_goal({"statement": "sib-a", "bindings": [],
                         "achievement_test": {"op": "GT", "channel": "score", "vs": "prev"},
                         "discriminator": {"d": 1}, "evidence_ptrs": [1]}, 2,
                        parent=g0)["goal_id"]
    gb = exe.admit_goal({"statement": "sib-b", "bindings": [],
                         "achievement_test": {"op": "GT", "channel": "score", "value": 9},
                         "discriminator": {"d": 1}, "evidence_ptrs": [1]}, 2,
                        parent=g0)["goal_id"]
    s.commit()
    base = exe.compute_rank(g0)["order"]
    T("without edges, id order breaks the tie", base.index(ga) < base.index(gb))
    exe.add_goal_edge(g0, gb, {"keys": ["score_event"]}, verified=True, turn_id=3)
    s.commit()
    rk = exe.compute_rank(g0)
    T("verified edge into a live parent ranks FIRST (children before the parents they serve)",
      rk["order"].index(gb) < rk["order"].index(ga), str(rk["order"]))
    T("edge-bit separates former equals", ga not in rk["equal_siblings"].get(gb, []))
    exe._append_status(4, "GOAL", g0, "VALIDATED", "ACCEPTED", "test")
    s.commit()
    rk = exe.compute_rank(g0)
    T("edge into a terminal parent confers nothing",
      rk["order"].index(ga) < rk["order"].index(gb))
    try:
        s.conn.execute("UPDATE goal_edge SET verified=0 WHERE run_id='rnk'")
        T("goal_edge is append-only (UPDATE must abort)", False)
    except sqlite3.DatabaseError as e:
        T("goal_edge is append-only (UPDATE must abort)", "append-only" in str(e))
    unv = exe.verify_fill(g0, {"op": "EXISTS", "entity": "consequence",
                               "where": {"predictor": "RU9999", "match": 1}}, CTX)
    T("unverifiable fill stays edge-less (admitted goals cannot fake the chain)",
      unv == (False, None))


def main() -> None:
    grammar()
    record_eval()
    cold_start()
    evidence_derivability()
    verified_fill()
    verdicts()
    rank_and_store()
    print(f"\n{'ALL PASS' if not FAILS else f'{len(FAILS)} FAILURES: {FAILS}'}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
