#!/usr/bin/env python3
"""ARG M4 predicate-grammar tests: compile/admissibility, eval_now (false-not-
error), reopen_class classifier. Run: uv run python tests/test_arg_predicates.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.arg import predicates as P  # noqa: E402
from agents.arg.adapter import ARCAdapter  # noqa: E402

FAILS = []


def T(name, cond, detail=""):
    print(f"  [{'ok ' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def main() -> None:
    ch = ARCAdapter().signal_channels()

    # G0's disjunctive progress test compiles over the verified vocabulary
    g0 = {"op": "OR", "args": [
        {"op": "GT", "channel": "levels_completed", "vs": "prev"},
        {"op": "EQ", "channel": "state", "value": "WIN"},
        {"op": "GT", "channel": "score", "vs": "prev"}]}
    ok, why = P.compiles(g0, ch)
    T("G0 disjunctive test compiles", ok, why)

    # a test over an UNVERIFIED channel is inadmissible (gate-2)
    bad = {"op": "GT", "channel": "energy", "vs": "prev"}
    T("unverified channel rejected", not P.compiles(bad, ch)[0])

    # an appearance-based test (no channel) is inadmissible by grammar
    T("appearance-based test rejected", not P.compiles({"op": "EQ", "value": "looks_open"}, ch)[0])

    # eval_now returns FALSE, not error, when the condition is not met
    ctx = {"cur": {"levels_completed": 0, "state": "NOT_FINISHED", "score": 0},
           "prev": {"levels_completed": 0, "state": "NOT_FINISHED", "score": 0}}
    T("eval_now false when no progress", P.eval_now(g0, ctx) is False)
    ctx2 = {"cur": {"levels_completed": 1, "state": "NOT_FINISHED", "score": 0},
            "prev": {"levels_completed": 0, "state": "NOT_FINISHED", "score": 0}}
    T("eval_now true on a level increment", P.eval_now(g0, ctx2) is True)
    ctx3 = {"cur": {"state": "WIN"}, "prev": {}}
    T("eval_now true on WIN", P.eval_now(g0, ctx3) is True)

    # reopen_class: G0 (monotone channels only) latches; LEARN-* reopens
    T("G0 → MONOTONE_TERMINAL", P.classify_reopen(g0) == "MONOTONE_TERMINAL")
    T("LEARN_ACTIONS → RECORD_QUANTIFIED",
      P.classify_reopen({"op": "LEARN_ACTIONS"}) == "RECORD_QUANTIFIED")
    T("COUNT-over-records → RECORD_QUANTIFIED",
      P.classify_reopen({"op": "COUNT", "entity": "referent", "where": {}}) == "RECORD_QUANTIFIED")
    # a test on a non-monotone channel also reopens
    T("lives-keyed test → RECORD_QUANTIFIED",
      P.classify_reopen({"op": "GT", "channel": "lives", "vs": "prev"}) == "RECORD_QUANTIFIED")

    # LEARN_* evaluates via the record evaluator (absent → False, never error)
    T("LEARN_* false without evaluator", P.eval_now({"op": "LEARN_ACTIONS"}, {}) is False)
    T("LEARN_* uses evaluator when present",
      P.eval_now({"op": "LEARN_ACTIONS"}, {}, record_eval=lambda n: True) is True)

    print(f"\n{'PASS' if not FAILS else 'FAIL: ' + str(FAILS)}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
