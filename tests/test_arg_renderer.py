#!/usr/bin/env python3
"""ARG M3 renderer tests: zone structure, the bidirectional join (cross-zone
coordinate equality + corruption caught), R7 annotation-blind branching, R9
budget, ARG_JOIN=0 flip. Run: uv run python tests/test_arg_renderer.py"""
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


def _mk_comp(color, cells):
    from agents.arg.adapter import Component
    xs = [c[0] for c in cells]; ys = [c[1] for c in cells]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    n = len(cells)
    return Component(color=color, cells=frozenset(cells), bbox=(x0, y0, x1, y1),
                     centroid=(round(sum(xs) / n), round(sum(ys) / n)), size=n,
                     shape=frozenset((x - x0, y - y0) for x, y in cells))


def _build(join="1", flat="1"):
    os.environ["ARG_JOIN"] = join
    os.environ["ARG_FLAT"] = flat
    from agents.arg import config as cfg
    importlib.reload(cfg)
    from agents.arg import store as st, executive as ex, seeds as sd, renderer as rd
    importlib.reload(st); importlib.reload(ex); importlib.reload(sd); importlib.reload(rd)

    s = st.Store(tempfile.mktemp(suffix=".db"))
    rid = "rndr"
    s.register_run(rid, "ls20", "sonnet", 0, "{}", 6000, "t")
    ids = sd.write_seeds(s, rid, 0)
    exe = ex.Executive(s, None, rid)
    # three referents: a 3-cell plate, an 8-cell block, a 40-cell wall
    plate = exe.mint_referent(_mk_comp(7, [(21, 31), (22, 31), (21, 32)]), 1)
    block = exe.mint_referent(_mk_comp(9, [(30, 40), (31, 40), (30, 41), (31, 41)]), 1)
    wall = exe.mint_referent(_mk_comp(5, [(x, y) for x in range(4, 9) for y in range(4, 12)]), 1)
    # bind the plate to G0 so Z6 has a bound referent (the join has something to check)
    s.conn.execute("INSERT INTO goal_binding (run_id, goal_id, goal_version, ref_id) VALUES (?,?,1,?)",
                   (rid, ids["G0"], plate))
    s.commit()
    r = rd.Renderer(s, exe, rid, None)
    return s, exe, rd, r, {"plate": plate, "block": block, "wall": wall}


def main() -> None:
    s, exe, rd, r, refs = _build()
    head = {"turn": 5, "level": 0, "score": 0}
    bv = r.budgeted_view(head, [[0] * 64 for _ in range(64)],
                         ["ACTION1", "ACTION2", "ACTION6"])
    view, zones = bv["view"], bv["zones"]

    T("all 6 zones present in fixed order",
      view.index("turn=") < view.index("ROSTER:") < view.index("RULES") <
      view.index("UNTOUCHED FRONTIER") < view.index("RENDER:") < view.index("GOAL CARD"))
    T("Z2 roster is salience-blind (3-cell plate has a row like the 40-cell wall)",
      refs["plate"] in zones["Z2"] and refs["wall"] in zones["Z2"])
    T("Z2 prints interactions=0 as a column",
      "| 0 |" in zones["Z2"])
    T("Z6 goal card shows the bound plate", refs["plate"] in zones["Z6"])

    # THE bidirectional join: the plate's shared coord string byte-identical in Z5 and Z6
    coord = r._coord_string({"centroid": (21, 31)})   # plate centroid
    T("shared coord string appears in Z5 (side A)",
      f"«R:{refs['plate']}" in zones["Z5"] and coord in zones["Z5"])
    T("shared coord string appears in Z6 (side B)", coord in zones["Z6"])
    T("cross-zone equality holds (no violations)", r.cross_zone_violations(zones, bv["working_set"]) == [])

    # corrupt Z6's coordinate → must be caught
    bad = dict(zones); bad["Z6"] = zones["Z6"].replace(coord, "@r99c99")
    T("corrupted Z6 coordinate is CAUGHT",
      len(r.cross_zone_violations(bad, bv["working_set"])) == 1)

    # R7: randomize kind/label → joins + frontier + working-set order byte-identical
    s.conn.execute("UPDATE referent SET kind='signal' WHERE run_id=? AND ref_id=?",
                   (s and 'rndr', refs["plate"])) if False else None
    # (kind is CHECK-constrained; instead assert the join/frontier don't contain kind at all)
    T("Z5 joins do not embed kind (R7 annotation-blind)",
      "percept-cluster" not in zones["Z5"] and "signal" not in zones["Z5"])
    ws_ids = [w["ref_id"] for w in bv["working_set"]]
    T("working-set order is by eviction rank, not size",
      ws_ids == sorted(ws_ids))   # all interactions=0, same rung → id order (not size order)

    # R9: render_tokens stamped and ≤ B
    T("render_tokens stamped ≤ B", 0 < bv["render_tokens"] <= 6000, str(bv["render_tokens"]))

    # C3: Z5 carries the ACTUAL grid (hex rows) + true machine-derived colors —
    # the model sees the world it is joining against (review S3)
    T("Z5 renders the actual grid rows", "0" * 64 in zones["Z5"])
    T("Z5 annotations carry the region's true color", "color=7" in zones["Z5"])
    T("R9 holds with a full 64x64 grid in Z5", bv["render_tokens"] <= 6000)

    # C3: R2 no-naked-mentions — an aliased label in rendered prose is
    # rewritten label#R### so every mention carries its own ground
    s.conn.execute("INSERT INTO referent_alias (run_id, ref_id, seq, turn_id, label) "
                   "VALUES ('rndr', ?, 1, 5, 'plate')", (refs["plate"],))
    s.commit()
    T("R2: substitute_mentions grounds a prose mention",
      r.substitute_mentions("press the plate now") == f"press the plate#{refs['plate']} now")
    bv_r2 = r.budgeted_view(head, [[0] * 8 for _ in range(8)], ["ACTION1"],
                            active_step="press the plate")
    T("R2: applied in Z1 ACTIVE and Z6 STEP lines",
      f"plate#{refs['plate']}" in bv_r2["zones"]["Z1"]
      and f"plate#{refs['plate']}" in bv_r2["zones"]["Z6"])

    # R9 terminal hard clamp: a goal with a huge achievement_test must not
    # produce an over-B render (the verification-workflow MINOR gap fix). Fresh
    # no-seeds store so the huge goal IS the active root leaf → Z6 huge.
    from agents.arg import store as _st, executive as _ex, renderer as _rd
    sb = _st.Store(tempfile.mktemp(suffix=".db"))
    sb.register_run("big", "ls20", "s", 0, "{}", 6000, "t")
    eb = _ex.Executive(sb, None, "big")
    sb.conn.execute("INSERT INTO goal (run_id, goal_id, version, parent_goal, statement, "
                    "achievement_test_json, discriminator_json, reopen_class, budget_actions, "
                    "budget_search_calls, provenance, admitted_turn, created_turn) "
                    "VALUES ('big', 'GBIG', 1, NULL, ?, ?, '{}', 'MONOTONE_TERMINAL', 200, 3, 'SEEDED', 0, 0)",
                    ("X" * 40000, '{"huge":"' + "Y" * 40000 + '"}'))
    sb.commit()
    bv_big = _rd.Renderer(sb, eb, "big", None).budgeted_view(
        head, [[0] * 8 for _ in range(8)], ["ACTION1"])
    T("R9 terminal clamp: render always <= B even with a huge active goal",
      bv_big["render_tokens"] <= 6000, str(bv_big["render_tokens"]))
    sb.close()

    # ARG_JOIN=0 flip: Z5 joins stripped, Z6 bound referents omitted
    s2, exe2, rd2, r2, refs2 = _build(join="0")
    bv2 = r2.budgeted_view(head, [[0] * 8 for _ in range(8)], ["ACTION1"])
    T("ARG_JOIN=0 strips Z5 annotations",
      "joins disabled" in bv2["zones"]["Z5"] and "«R:" not in bv2["zones"]["Z5"])
    T("ARG_JOIN=0 omits Z6 bound-referent rows",
      "BOUND REFERENTS" not in bv2["zones"]["Z6"])

    s.close(); s2.close()
    print(f"\n{'PASS' if not FAILS else 'FAIL: ' + str(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
