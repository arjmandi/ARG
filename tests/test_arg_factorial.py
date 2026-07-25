#!/usr/bin/env python3
"""ARG M9 tests: the J/A factorial flips + shadow-agenda byte-identity, cross-run
carryover (TESTED→fresh HYPOTHESIS), A11 store-stress (render is O(working set)),
ARG_GOALS baseline seam. Run: uv run python tests/test_arg_factorial.py"""
import importlib
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FAILS = []


def T(name, cond, detail=""):
    print(f"  [{'ok ' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def _reload(join="1", agenda="1", goals="1", flat="1"):
    os.environ["ARG_JOIN"] = join
    os.environ["ARG_AGENDA"] = agenda
    os.environ["ARG_GOALS"] = goals
    os.environ["ARG_FLAT"] = flat
    from agents.arg import config as cfg
    importlib.reload(cfg)
    for mod in ("store", "executive", "seeds", "renderer", "pather", "predicates"):
        importlib.reload(importlib.import_module(f"agents.arg.{mod}"))
    from agents.arg import store, executive, seeds, renderer
    return store, executive, seeds, renderer, cfg


def _mk(color, cells):
    from agents.arg.adapter import Component
    xs = [c[0] for c in cells]; ys = [c[1] for c in cells]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    n = len(cells)
    return Component(color=color, cells=frozenset(cells), bbox=(x0, y0, x1, y1),
                     centroid=(round(sum(xs) / n), round(sum(ys) / n)), size=n,
                     shape=frozenset((x - x0, y - y0) for x, y in cells))


def _fresh(store, executive, seeds, n_refs=3):
    from agents.arg.adapter import ARCAdapter
    s = store.Store(tempfile.mktemp(suffix=".db"))
    rid = "fac"
    s.register_run(rid, "ls20", "sonnet", 0, "{}", 6000, "t")
    exe = executive.Executive(s, ARCAdapter(), rid)
    seeds.write_seeds(s, rid, 0)
    for i in range(n_refs):
        exe.mint_referent(_mk(5, [(10 + i, 10)]), 1)
    s.commit()
    return s, exe, rid


def main() -> None:
    # ---- shadow-agenda byte-identity: render must not depend on agenda state ----
    st, ex, sd, rd, cfg_on = _reload(agenda="1")
    agenda_on_val = cfg_on.AGENDA_ON       # capture value before the next reload mutates the module
    s1, e1, r1 = _fresh(st, ex, sd)
    view_on = rd.Renderer(s1, e1, r1, None).budgeted_view(
        {"turn": 1, "level": 0, "score": 0}, [[0] * 8 for _ in range(8)], ["ACTION1"])["view"]
    st2, ex2, sd2, rd2, cfg_off = _reload(agenda="0")
    agenda_off_val = cfg_off.AGENDA_ON
    s2, e2, r2 = _fresh(st2, ex2, sd2)
    view_off = rd2.Renderer(s2, e2, r2, None).budgeted_view(
        {"turn": 1, "level": 0, "score": 0}, [[0] * 8 for _ in range(8)], ["ACTION1"])["view"]
    T("shadow byte-identity: render independent of ARG_AGENDA", view_on == view_off)
    T("ARG_AGENDA gate is read", agenda_off_val is False and agenda_on_val is True)

    # ---- chain-aware shadow (§3.5/U-1): the reference step exists in
    # agenda-off cells even when FULL's step would come from the milestone/
    # auto-fill tier — computed VIRTUALLY, no goal written ----
    ctx = {"cur": {"score": 0, "levels_completed": 0, "state": "NOT_FINISHED"}, "prev": {}}
    ru = e2.add_rule(2, "A2 scores", {"action": "ACTION2"}, {"score_event": 1}, test_plan="p")
    s2.commit()
    goals_before = s2.conn.execute("SELECT COUNT(*) c FROM goal WHERE run_id='fac'").fetchone()["c"]
    shadow = e2.plan_shadow_step(ctx)
    T("shadow references the VIRTUAL auto-fill milestone (hole candidate rule)",
      shadow is not None and shadow.endswith(f"|{ru}") and "ACTION2" in shadow, str(shadow))
    T("virtual tier writes nothing (pure read)",
      s2.conn.execute("SELECT COUNT(*) c FROM goal WHERE run_id='fac'").fetchone()["c"]
      == goals_before)

    # ---- ARG_JOIN flip ----
    st3, ex3, sd3, rd3, _ = _reload(join="0")
    s3, e3, r3 = _fresh(st3, ex3, sd3)
    v_join0 = rd3.Renderer(s3, e3, r3, None).budgeted_view(
        {"turn": 1, "level": 0, "score": 0}, [[0] * 8 for _ in range(8)], ["ACTION1"])["zones"]["Z5"]
    T("ARG_JOIN=0 strips Z5 annotations", "joins disabled" in v_join0)

    # ---- ARG_GOALS baseline seam ----
    st4, ex4, sd4, rd4, cfgg = _reload(goals="0")
    T("ARG_GOALS gate is read", cfgg.GOALS_ON is False)

    # ---- cross-run carryover: TESTED prior rule → fresh HYPOTHESIS ----
    st5, ex5, sd5, rd5, _ = _reload()
    # build a PRIOR run with a TESTED rule
    prior = st5.Store(tempfile.mktemp(suffix=".db"))
    prior.register_run("prior", "ls20", "sonnet", 0, "{}", 6000, "t")
    from agents.arg.adapter import ARCAdapter
    pe = ex5.Executive(prior, ARCAdapter(), "prior")
    ru = pe.add_rule(1, "WHEN x DO A1 THEN d", {}, {})
    for tt in (2, 3):
        pe.write_consequence(tt, "ACTION1", None, "CC1", {"x": 1}, match=True, predictor_id=ru,
                             predictor_kind="RULE")
    prior.commit()
    pe.recompute_rule_status(ru, 4)   # → TESTED
    prior.commit()
    prior_path = prior.path
    prior.close()
    # new run imports it
    s5, e5, r5 = _fresh(st5, ex5, sd5)
    n = e5.import_prior_rules(prior_path, 1)
    T("carryover imported the prior TESTED rule", n == 1)
    imp = s5.conn.execute("SELECT prior_support, new_rule_id FROM seed_import WHERE run_id=?",
                          (r5,)).fetchone()
    T("carryover records prior_support", imp and imp["prior_support"] == 2)
    st_new = e5.current_status("RULE", imp["new_rule_id"])
    T("carried rule re-enters as HYPOTHESIS (never trusted)", st_new == "HYPOTHESIS")

    # ---- A11: render is O(working set), not O(store): the render PLATEAUS at W ----
    st6, ex6, sd6, rd6, cfg6 = _reload()
    s6, e6, r6 = _fresh(st6, ex6, sd6, n_refs=60)   # already above W=40 → at the plateau
    rnd = rd6.Renderer(s6, e6, r6, None)
    at_cap = rnd.budgeted_view({"turn": 1, "level": 0, "score": 0}, [[0] * 8 for _ in range(8)],
                               ["ACTION1"])["render_tokens"]
    e6.inflate_store(10, 2)   # 60 → ~600 referents (10× more)
    big = rnd.budgeted_view({"turn": 2, "level": 0, "score": 0}, [[0] * 8 for _ in range(8)],
                            ["ACTION1"])["render_tokens"]
    n_ref = s6.conn.execute("SELECT COUNT(*) c FROM referent WHERE run_id=?", (r6,)).fetchone()["c"]
    T("A11: store inflated 10× but render is FLAT (O(working set), plateaus at W)",
      abs(big - at_cap) <= max(20, at_cap * 0.1) and big <= cfg6.B_RENDER,
      f"at_cap={at_cap} big={big} refs={n_ref}")
    T("A11: the store really did inflate ~10×", n_ref >= 500, str(n_ref))

    for s in (s1, s2, s3, s5, s6):
        s.close()
    print(f"\n{'PASS' if not FAILS else 'FAIL: ' + str(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
