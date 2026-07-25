#!/usr/bin/env python3
"""ARG D3 tests — coverage-gap items 1,2,8,10,11.

- #1 relation lifecycle: same_as REFUTED by co-presence (→DEMOTED at K),
  SUPPORTED by alternating appearances (→TESTED + MERGE_CANONICAL lineage);
  dormant endpoints demote any relation.
- #2 Procedures: a fully-consumed commitment DISTILLS; the procedure compiles
  BEFORE means analysis on the next ask; a confirming replay → TESTED within
  scope; boundary + intersecting context-class mint demote; TTL re-probes.
- #8 FISSION EXECUTE: signature-correlated mismatches split the referent —
  children minted (provenance FISSION, split_into lineage), parent DORMANT,
  citing rules demoted, goal bindings widened, dependent steps BLOCKED.
- #10 evidence compaction: the Z6 bound row carries the one-line consequence
  signature (count + change/no-op + exemplar pointers).
- #11 archive line: Z2 prints "+N archived" and the capture logs the overflow.
Run: uv run python tests/test_arg_gaps3.py"""
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


def _fresh(tag):
    from agents.arg.store import Store
    from agents.arg.adapter import ARCAdapter
    from agents.arg.executive import Executive
    s = Store(tempfile.mktemp(suffix=".db"))
    s.register_run(tag, "ls20", "m", 0, "{}", 6000, "t")
    return s, Executive(s, ARCAdapter(), tag), tag


def _bind_row(s, rid, turn, sig, ref, chash):
    s.conn.execute("INSERT INTO binding_record (run_id, turn_id, component_hash, "
                   "anchor_cells_json, anchor_bbox_json, anchor_signature, bound_to, is_new, "
                   "margin) VALUES (?,?,?,?,?,?,?,0,0.9)",
                   (rid, turn, chash, "[[1,1]]", "[1,1,1,1]", sig, ref))


def main() -> None:
    from agents.arg import config as cfg

    # ================= #1 relation lifecycle =================
    s, exe, rid = _fresh("rel")
    ra = exe.mint_referent(_mk(5, [(1, 1)]), 1)
    rb = exe.mint_referent(_mk(5, [(4, 4)]), 1)
    rel = exe.persist_relation(1, "same_as", ra, rb, "maybe the same")
    s.commit()
    # alternating appearances (never co-present) → TESTED + canonical lineage
    for t, ref in ((2, ra), (3, rb), (4, ra), (5, rb)):
        _bind_row(s, rid, t, "sigX", ref, f"h{t}")
    s.commit()
    T("#1: alternating appearances promote same_as to TESTED",
      exe.recompute_sameas_status(rel, 6) == "TESTED")
    lin = s.conn.execute("SELECT op FROM referent_lineage WHERE run_id=?", (rid,)).fetchone()
    T("#1: TESTED same_as writes MERGE_CANONICAL lineage (both ids preserved)",
      lin and lin["op"] == "MERGE_CANONICAL")
    # a second same_as REFUTED by co-presence
    rc = exe.mint_referent(_mk(6, [(6, 6)]), 1)
    rel2 = exe.persist_relation(6, "same_as", ra, rc, "surely the same")
    for t in (7, 8, 9):
        _bind_row(s, rid, t, "sigA", ra, f"ha{t}")
        _bind_row(s, rid, t, "sigC", rc, f"hc{t}")
    s.commit()
    T("#1: co-presence REFUTES same_as (DEMOTED at K)",
      exe.recompute_sameas_status(rel2, 10) == "DEMOTED")
    # dormant endpoint demotes any relation
    rel3 = exe.persist_relation(10, "blocks", rb, rc, None)
    exe._append_status(11, "REFERENT_LIFE", rb, None, "DORMANT", "test")
    s.commit()
    exe.sweep_relations(12)
    T("#1: a DORMANT endpoint demotes the relation",
      exe.current_status("RELATION", rel3) == "DEMOTED")
    s.close()

    # ================= #2 Procedures =================
    s2, e2, rid2 = _fresh("proc")
    tgt = e2.mint_referent(_mk(7, [(2, 2)]), 1)
    s2.conn.execute("INSERT INTO goal VALUES ('proc','GP',1,NULL,'score',?, '{}',"
                    "'MONOTONE_TERMINAL',NULL,200,3,'SEEDED',0,0)",
                    (json.dumps({"op": "GT", "channel": "score", "vs": "prev"}),))
    e2._append_status(1, "GOAL", "GP", None, "PROPOSED", "seeded")
    e2.bind_goal_ref("GP", tgt)
    ru = e2.add_rule(1, "click scores", {"action": "ACTION6", "target": tgt}, {"score_event": 1})
    e2._append_status(1, "RULE", ru, "HYPOTHESIS", "TESTED", "t")
    s2.commit()
    ctx = {"cur": {"levels_completed": 0}, "prev": {}}
    c1 = e2.compile_plan("GP", 2, ctx)
    T("#2: first compile goes through MEANS ANALYSIS (no procedure yet)",
      c1 is not None and e2.procedure_of_commit(c1) is None)
    step, _ = e2.next_executable_step(3)
    e2.consume_step(step, 3, level_index=0)
    s2.commit()
    proc = s2.conn.execute("SELECT proc_id, scope_fingerprint FROM procedure WHERE run_id=?",
                           (rid2,)).fetchone()
    T("#2: full consume DISTILLS a Procedure with a context-class fingerprint",
      proc is not None and proc["scope_fingerprint"].startswith("CC"),
      str(dict(proc) if proc else None))
    T("#2: distilled procedure enters HYPOTHESIS",
      e2.current_status("PROCEDURE", proc["proc_id"]) == "HYPOTHESIS")
    # second ask: the PROCEDURE compiles (before fresh means analysis)
    c2 = e2.compile_plan("GP", 5, ctx)
    T("#2: replay compiles FROM the procedure before means analysis",
      c2 is not None and e2.procedure_of_commit(c2) == proc["proc_id"])
    step2, _ = e2.next_executable_step(6)
    e2.consume_step(step2, 6, level_index=0)
    s2.commit()
    T("#2: one confirming replay → TESTED within scope",
      e2.current_status("PROCEDURE", proc["proc_id"]) == "TESTED")
    # boundary demotes; TTL re-probes
    e2.level_boundary_pass(8)
    s2.commit()
    T("#2: level boundary demotes the procedure to HYPOTHESIS",
      e2.current_status("PROCEDURE", proc["proc_id"]) == "HYPOTHESIS")
    e2._append_status(9, "PROCEDURE", proc["proc_id"], "HYPOTHESIS", "DEMOTED", "counterexample")
    s2.commit()
    swept = e2.ttl_sweep(9 + cfg.TTL)
    T("#2: TTL re-probes a DEMOTED procedure", proc["proc_id"] in swept)
    # an intersecting context-class mint demotes (§5.4 scope fingerprint)
    e2._append_status(10 + cfg.TTL, "PROCEDURE", proc["proc_id"], "HYPOTHESIS", "TESTED", "t")
    e2.mint_context_class(1, "diverge:test", 11 + cfg.TTL, 0)
    s2.commit()
    T("#2: a context-class mint intersecting the scope demotes the procedure",
      e2.current_status("PROCEDURE", proc["proc_id"]) == "DEMOTED")
    s2.close()

    # ================= #8 FISSION EXECUTE =================
    s3, e3, rid3 = _fresh("fiss")
    par = e3.mint_referent(_mk(5, [(3, 3)]), 1)
    other = e3.mint_referent(_mk(6, [(6, 6)]), 1)
    # two signature groups across its binding history
    for t, sig, cells in ((2, "sigA", "[[3,3]]"), (3, "sigA", "[[3,3]]"),
                          (4, "sigB", "[[5,5],[5,6]]"), (5, "sigB", "[[5,5],[5,6]]")):
        s3.conn.execute("INSERT INTO binding_record (run_id, turn_id, component_hash, "
                        "anchor_cells_json, anchor_bbox_json, anchor_signature, bound_to, is_new, "
                        "margin) VALUES (?,?,?,?,?,?,?,0,0.9)",
                        (rid3, t, f"h{t}", cells, "[3,3,5,6]", sig, par))
    # a rule citing the parent + a goal bound to it + a dependent step
    rup = e3.add_rule(1, "r", {"action": "ACTION6", "target": par}, {"score_event": 1})
    e3._append_status(1, "RULE", rup, "HYPOTHESIS", "TESTED", "t")
    s3.conn.execute("INSERT INTO goal VALUES ('fiss','GF',1,NULL,'x','{}','{}',"
                    "'MONOTONE_TERMINAL',NULL,200,3,'SEEDED',0,0)")
    e3.bind_goal_ref("GF", par)
    cid = e3.write_commitment("GF", [{"kind": "INTERACT", "action": "ACTION6",
                                      "target_ref": par, "predicted": {"score_event": 1}}], 5,
                              premise_rules=[rup])
    s3.commit()
    fx = e3.fission_execute(par, 6)
    s3.commit()
    T("#8: fission executes → one child per signature cluster",
      fx["executed"] and len(fx["children"]) == 2, str(fx))
    kids = fx["children"]
    T("#8: children carry FISSION provenance + split_into lineage",
      s3.conn.execute("SELECT COUNT(*) c FROM referent_lineage WHERE run_id=? AND "
                      "op='FISSION_SPLIT' AND parent_ref=?", (rid3, par)).fetchone()["c"] == 2
      and s3.conn.execute("SELECT COUNT(*) c FROM referent WHERE run_id=? AND provenance='FISSION'",
                          (rid3,)).fetchone()["c"] == 2)
    T("#8: the parent is retired (DORMANT, out of the roster) — audit chain survives",
      par in e3._dormant_refs() and par not in e3._roster_ids())
    T("#8: rules citing the parent DEMOTED", e3.current_status("RULE", rup) == "DEMOTED")
    bound_now = {r["ref_id"] for r in s3.conn.execute(
        "SELECT ref_id FROM goal_binding WHERE run_id=? AND goal_id='GF'", (rid3,))}
    T("#8: goal bindings widened to all children", set(kids) <= bound_now)
    T("#8: dependent step auto-BLOCKED",
      e3.current_status("COMMITMENT_STEP", f"{cid}-S0") == "BLOCKED")
    T("#8: idempotent on the retired parent",
      e3.fission_execute(par, 7)["executed"] is False)
    s3.close()

    # ================= #10 compaction + #11 archive line (renderer) =================
    import importlib
    for mod in ("store", "executive", "seeds", "renderer"):
        importlib.reload(importlib.import_module(f"agents.arg.{mod}"))
    from agents.arg import store as st5, executive as ex5, seeds as sd5, renderer as rd5
    from agents.arg.adapter import ARCAdapter
    s5 = st5.Store(tempfile.mktemp(suffix=".db"))
    s5.register_run("cmp", "ls20", "m", 0, "{}", 6000, "t")
    e5 = ex5.Executive(s5, ARCAdapter(), "cmp")
    ids = sd5.write_seeds(s5, "cmp", 0)
    tgt5 = e5.mint_referent(_mk(7, [(1, 1)]), 1)
    for i in range(45 + 5):   # 50 more referents → past W=40 → archive line
        e5.mint_referent(_mk((i % 9) + 1, [(2 + i % 6, 3 + i // 6)]), 1)
    e5.bind_goal_ref(ids["G0"], tgt5)
    cc5 = e5.current_context_class(0, 1)
    for t in (2, 3, 4):
        e5.write_consequence(t, "ACTION6", tgt5, cc5, {"cells_changed": 3 if t < 4 else 0},
                             score_event=1 if t == 3 else 0)
    s5.commit()
    sig5 = e5.consequence_signature(tgt5)
    T("#10: consequence signature = count + change/no-op split + exemplars",
      "3rcpt" in sig5 and "ex t2" in sig5, sig5)
    r5 = rd5.Renderer(s5, e5, "cmp", None)
    bv5 = r5.budgeted_view({"turn": 5, "level": 0, "score": 0},
                           [[0] * 8 for _ in range(8)], ["ACTION6"])
    T("#10: Z6 bound row carries the signature (join side B, compacted)",
      "rcpt(" in bv5["zones"]["Z6"], bv5["zones"]["Z6"].splitlines()[4][:90]
      if len(bv5["zones"]["Z6"].splitlines()) > 4 else "")
    T("#11: Z2 prints the archive index line (never silent truncation)",
      "referents archived by eviction rank" in bv5["zones"]["Z2"])
    T("#11: the overflow count is reported to the caller for logging",
      bv5["archived"] >= 10, str(bv5["archived"]))
    s5.close()

    print(f"\n{'PASS' if not FAILS else 'FAIL: ' + str(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
