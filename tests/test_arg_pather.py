#!/usr/bin/env python3
"""ARG M6 pather tests: action-model learning, routing (no-route until learned,
then a plan), NAVIGATE compilation with the arrival handoff.
Run: uv run python tests/test_arg_pather.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.arg.store import Store  # noqa: E402
from agents.arg.adapter import ARCAdapter, Component  # noqa: E402
from agents.arg.executive import Executive  # noqa: E402
from agents.arg import pather  # noqa: E402

FAILS = []


def T(name, cond, detail=""):
    print(f"  [{'ok ' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def _grid_with_mover(mx, my):
    """A grid with a single 1-cell mover (color 7) at (mx,my), bg 0."""
    g = [[0] * 16 for _ in range(16)]
    g[my][mx] = 7
    return g


def main() -> None:
    adapter = ARCAdapter()
    s = Store(tempfile.mktemp(suffix=".db"))
    rid = "path"
    s.register_run(rid, "ls20", "sonnet", 0, "{}", 6000, "t")
    exe = Executive(s, adapter, rid)

    # before any learning: no deltas, no route
    T("no action model yet → empty deltas", pather.action_deltas(s, rid) == {})
    T("route None without a model", pather.route({}, (5, 5), (10, 10, 11, 11)) is None)

    # observe ACTION4 move the mover right by (1,0) three times; ACTION2 down (0,1)
    for i in range(3):
        exe.learn_from_movement("ACTION4", _grid_with_mover(5 + i, 5), _grid_with_mover(6 + i, 5), 10 + i)
    for i in range(2):
        exe.learn_from_movement("ACTION2", _grid_with_mover(8, 5 + i), _grid_with_mover(8, 6 + i), 20 + i)
    s.commit()

    deltas = pather.action_deltas(s, rid)
    T("learned ACTION4 = (+1,0)", deltas.get("ACTION4", (0, 0, 0))[:2] == (1, 0), str(deltas))
    T("learned ACTION2 = (0,+1)", deltas.get("ACTION2", (0, 0, 0))[:2] == (0, 1))
    T("quantum inferred", pather.quantum(deltas) == 1)

    # route from (5,5) to a target at (8,7): reachable via ACTION4×3 + ACTION2×2
    plan = pather.route(deltas, (5, 5), (8, 7, 8, 7), adjacent_ok=False)
    T("route found after learning", plan is not None and len(plan) > 0, str(plan))
    T("route uses learned actions only",
      plan is not None and all(a in deltas for a in plan))

    # NAVIGATE compilation with arrival handoff (then: INTERACT slot)
    # mint a target referent so compile_navigate can find its bbox
    tgt = exe.mint_referent(Component(color=5, cells=frozenset([(8, 7)]), bbox=(8, 7, 8, 7),
                                      centroid=(8, 7), size=1, shape=frozenset([(0, 0)])), 1)
    s.commit()
    nav = exe.compile_navigate(tgt, mover_centroid=(5, 5))
    T("compile_navigate returns steps", nav is not None and nav["steps"], str(nav is not None))
    T("NAVIGATE ends in a then: INTERACT handoff",
      nav and nav["steps"][-1]["kind"] == "INTERACT" and nav["steps"][-1].get("then"))
    T("all-but-last steps are NAVIGATE",
      nav and all(st["kind"] == "NAVIGATE" for st in nav["steps"][:-1]))

    # unreachable target (off-grid via learned deltas) → None (→ Z4 probe fallback)
    T("compile_navigate None when no model",
      Executive(Store(tempfile.mktemp(suffix='.db')), adapter, "empty").compile_navigate("R0001") is None)

    # write_commitment persists the plan
    cid = exe.write_commitment("G0001", nav["steps"], 30)
    s.commit()
    n = s.conn.execute("SELECT COUNT(*) c FROM commitment_step WHERE run_id=? AND commit_id=?",
                       (rid, cid)).fetchone()["c"]
    T("commitment steps persisted", n == len(nav["steps"]))

    s.close()
    print(f"\n{'PASS' if not FAILS else 'FAIL: ' + str(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
