#!/usr/bin/env python3
"""ARG M4 Executive ingest-validator tests: every reject class fires; R8
containment; completeness invariant. Run: uv run python tests/test_arg_executive.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.arg.store import Store  # noqa: E402
from agents.arg.adapter import ARCAdapter, Component  # noqa: E402
from agents.arg.executive import Executive  # noqa: E402

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
    rid = "exec"
    s.register_run(rid, "ls20", "sonnet", 0, "{}", 6000, "t")
    exe = Executive(s, ARCAdapter(), rid)
    plate = _mk(7, [(21, 31), (22, 31), (21, 32)])   # 3-cell plate
    ref = exe.mint_referent(plate, 1)                 # → R0001, roster
    s.commit()
    cand = {plate.chash}

    def viols(ops, candidates=cand):
        return {r["violation"] for r in exe.validate_observer_ops(ops, candidates)["rejections"]}

    # off-candidate BIND: a hash not in the Executive-proposed candidate set
    T("OFF_CANDIDATE_BIND fires",
      "OFF_CANDIDATE_BIND" in viols([{"op": "BIND", "component_hash": "deadbeef", "to": "NEW"}],
                                    candidates={"other"}))
    # dangling ref: BIND to a non-existent R###
    T("DANGLING_REF (BIND) fires",
      "DANGLING_REF" in viols([{"op": "BIND", "component_hash": plate.chash, "to": "R9999"}]))
    # non-member event_kind (an event outside the verified signal vocabulary)
    T("NON_MEMBER_EVENT fires",
      "NON_MEMBER_EVENT" in viols(
          [{"op": "BIND", "component_hash": plate.chash, "to": ref},
           {"op": "NOTE_EVENT", "ref": ref, "event_kind": "glows", "turn_id": 1}]))
    # dangling relation
    T("DANGLING_REF (relation) fires",
      "DANGLING_REF" in {r["violation"] for r in exe.validate_observer_ops(
          [{"op": "BIND", "component_hash": plate.chash, "to": ref},
           {"op": "PROPOSE_RELATION", "verb": "enables", "src": ref, "dst": "R9999"}], cand)["rejections"]})
    # completeness: a candidate left without a verdict
    res = exe.validate_observer_ops([], cand)
    T("INCOMPLETE_COVERAGE fires on a silent candidate",
      not res["coverage_ok"] and any(r["violation"] == "INCOMPLETE_COVERAGE" for r in res["rejections"]))
    # a well-formed complete response is accepted
    good = exe.validate_observer_ops(
        [{"op": "BIND", "component_hash": plate.chash, "to": ref},
         {"op": "NOTE_EVENT", "ref": ref, "event_kind": "score", "turn_id": 1},
         {"op": "INTERPRET", "ref": ref, "label": "small-thing"}], cand)
    T("well-formed complete response accepted", good["coverage_ok"] and len(good["accepted"]) == 3)

    # R8 Actuator containment
    schema = {"x": [0, 63], "y": [0, 63]}
    T("R8 uncontained ACTION6 caught",
      exe.validate_actuator("ACTION6", 50, 50, ref, schema)["violation"] == "UNCONTAINED_PARAM")
    T("R8 in-anchor ACTION6 ok",
      exe.validate_actuator("ACTION6", 21, 31, ref, schema)["ok"] is True)
    T("R8 fallback is the anchor centroid",
      exe.validate_actuator("ACTION6", 50, 50, ref, schema)["fallback"] == plate.centroid)
    T("R8 out-of-schema caught",
      exe.validate_actuator("ACTION6", 99, 99, ref, schema)["violation"] == "OUT_OF_SCHEMA")
    T("non-ACTION6 needs no containment",
      exe.validate_actuator("ACTION1", 0, 0, None, {})["ok"] is True)

    # write_reject metering is append-only evidence
    exe.meter_write_reject(1, "OBSERVER", "BIND", "OFF_CANDIDATE_BIND", 2)
    s.commit()
    n = s.conn.execute("SELECT COUNT(*) c FROM write_reject WHERE run_id=?", (rid,)).fetchone()["c"]
    T("write_reject metered", n == 1)

    s.close()
    print(f"\n{'PASS' if not FAILS else 'FAIL: ' + str(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
