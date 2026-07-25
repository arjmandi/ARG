#!/usr/bin/env python3
"""ARG M1 identity tests: signature/component_hash golden, composite-margin
re-identification (auto-bind / ambiguous / NEW+same_as routing).
Run: uv run python tests/test_arg_identity.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.arg.adapter import ARCAdapter, Component, shape_hash, component_hash  # noqa: E402
from agents.arg import executive as ex  # noqa: E402
from agents.arg import config  # noqa: E402

FAILS = []


def T(name, cond, detail=""):
    print(f"  [{'ok ' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def comp(color, cells):
    xs = [c[0] for c in cells]; ys = [c[1] for c in cells]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    n = len(cells)
    return Component(color=color, cells=frozenset(cells), bbox=(x0, y0, x1, y1),
                     centroid=(round(sum(xs) / n), round(sum(ys) / n)), size=n,
                     shape=frozenset((x - x0, y - y0) for x, y in cells))


def main() -> None:
    # signature is translation-invariant; component_hash is position-inclusive
    a = comp(3, [(21, 31), (22, 31), (21, 32)])
    b = comp(3, [(41, 51), (42, 51), (41, 52)])   # same shape+color, translated
    d = comp(3, [(21, 31), (22, 31), (22, 32)])   # different shape
    T("signature translation-invariant", a.signature == b.signature)
    T("signature shape-sensitive", a.signature != d.signature)
    T("component_hash position-inclusive", a.chash != b.chash)
    T("signature golden (stable hash)", a.signature == shape_hash(3, a.shape))
    T("component_hash golden", a.chash == component_hash(3, a.cells))

    # segmentation is salience-blind: a 1-cell and a big region come out equal-shaped rows
    adapter = ARCAdapter()
    grid = [[0] * 8 for _ in range(8)]
    grid[1][1] = 5                       # 1-cell plate
    for y in range(4, 8):
        for x in range(4, 8):
            grid[y][x] = 9               # 16-cell wall
    comps = adapter.segment(grid)
    sizes = sorted(c.size for c in comps if c.color != 0)
    T("segmentation finds both regions salience-blind", sizes == [1, 16], str(sizes))

    # composite-margin re-identification
    cand_exact = {"ref_id": "R0001", "signature": a.signature, "bbox": list(a.bbox),
                  "centroid": a.centroid}
    dec = ex.reidentify(a, [cand_exact])
    T("exact match → AUTO_BIND", dec["decision"] == ex.AUTO_BIND and dec["bound_to"] == "R0001",
      str(dec))

    # two near-equal candidates → small margin → ambiguous or NEW+same_as
    c1 = {"ref_id": "R0001", "signature": a.signature, "bbox": [21, 31, 22, 32], "centroid": (21, 31)}
    c2 = {"ref_id": "R0002", "signature": a.signature, "bbox": [21, 31, 22, 32], "centroid": (21, 31)}
    dec2 = ex.reidentify(a, [c1, c2])
    T("two identical candidates → margin ~0 → NEW+same_as",
      dec2["decision"] == ex.NEW_WITH_SAMEAS and dec2["same_as"] in ("R0001", "R0002"),
      str(dec2))

    # no candidate → NEW_FRESH
    T("no candidate → NEW_FRESH", ex.reidentify(a, [])["decision"] == ex.NEW_FRESH)

    # a clearly-better top1 vs a weak top2 → margin ≥ τ (bind), and ≥ τ_auto ⇒ auto
    weak = {"ref_id": "R0009", "signature": "different", "bbox": [50, 50, 51, 51], "centroid": (50, 50)}
    dec3 = ex.reidentify(a, [cand_exact, weak])
    T("strong top1 vs weak top2 → AUTO_BIND", dec3["decision"] == ex.AUTO_BIND
      and dec3["runner_up"] == "R0009", str(dec3))

    # routing thresholds honored
    T("τ default 0.15", abs(config.TAU - 0.15) < 1e-9)
    T("τ_auto default 0.40", abs(config.TAU_AUTO - 0.40) < 1e-9)

    print(f"\n{'PASS' if not FAILS else 'FAIL: ' + str(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
