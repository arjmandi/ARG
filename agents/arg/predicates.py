"""Closed-predicate grammar (build plan §11 blocker, §3.3 gate-2).

Achievement tests, context predicates, and effect patterns live in ONE fixed
JSON-AST vocabulary over the adapter's verified signal channels. A test that
references an unverified channel, or fails to compile, is inadmissible — this is
what makes "understand the door" inexpressible as a goal while "ACTION2 on R14
produces a diff on 2 trials" is admissible.

AST node: {"op": <OP>, ...}. eval_now returns False (never error) for a
compiled test whose condition is not yet met (gate-2 requirement).
"""

from __future__ import annotations

from typing import Any, Callable, Optional

BOOL_OPS = {"AND", "OR", "NOT"}
CMP_OPS = {"GT", "GE", "EQ"}
RECORD_OPS = {"EXISTS", "COUNT"}          # quantify over ARG records
STATUS_OPS = {"RULE_STATUS", "RUNG"}      # knowledge milestones over stamped statuses (A1)
LEARN_OPS = {"LEARN_ACTIONS", "LEARN_RULES", "LEARN_ENV"}
ALL_OPS = BOOL_OPS | CMP_OPS | RECORD_OPS | STATUS_OPS | LEARN_OPS

# closed `where` vocabulary per entity (A1): every field resolves to a stamped
# column — nothing appearance-based can enter through a where-clause
WHERE_FIELDS = {
    "consequence": {"action", "target", "match", "predictor", "score_event",
                    "level_event", "context_class"},
    "rule": {"status"},
    "referent": {"rung"},
}
RULE_STATUSES = {"HYPOTHESIS", "TESTED", "DEMOTED"}
RUNGS = {"ANCHORED", "ENGAGED", "CHARACTERIZED"}

# channels whose progress cannot un-happen → a test keyed solely on them latches
MONOTONE_CHANNELS = {"score", "levels_completed", "state"}


class PredicateError(ValueError):
    pass


def compiles(ast: Any, channels: dict) -> tuple:
    """(ok, reason). Well-formedness + every referenced channel is a verified
    signal-vocabulary member (adapter.signal_channels())."""
    if not isinstance(ast, dict) or "op" not in ast:
        return False, "not an AST node"
    op = ast["op"]
    if op not in ALL_OPS:
        return False, f"unknown op {op}"
    if op in BOOL_OPS:
        args = ast.get("args", [])
        if op == "NOT" and len(args) != 1:
            return False, "NOT takes one arg"
        if op in ("AND", "OR") and not args:
            return False, f"{op} needs args"
        for a in args:
            ok, why = compiles(a, channels)
            if not ok:
                return False, why
        return True, ""
    if op in CMP_OPS:
        ch = ast.get("channel")
        if ch not in channels:
            return False, f"unverified channel {ch!r}"
        if "vs" not in ast and "value" not in ast:
            return False, f"{op} needs vs or value"
        return True, ""
    if op in RECORD_OPS:
        # COUNT/EXISTS over a record-set descriptor {entity, where} — where
        # fields are a CLOSED set per entity (A1)
        entity = ast.get("entity")
        if entity not in WHERE_FIELDS:
            return False, f"{op} entity must be one of {sorted(WHERE_FIELDS)}"
        where = ast.get("where") or {}
        if not isinstance(where, dict) or not set(where) <= WHERE_FIELDS[entity]:
            return False, f"where fields for {entity} must be ⊆ {sorted(WHERE_FIELDS[entity])}"
        if op == "COUNT" and "value" not in ast:
            return False, "COUNT needs value"
        return True, ""
    if op == "RULE_STATUS":
        if not ast.get("rule") or ast.get("is") not in RULE_STATUSES:
            return False, "RULE_STATUS needs rule + is∈{HYPOTHESIS,TESTED,DEMOTED}"
        return True, ""
    if op == "RUNG":
        if not ast.get("ref") or ast.get("at_least") not in RUNGS:
            return False, "RUNG needs ref + at_least∈{ANCHORED,ENGAGED,CHARACTERIZED}"
        return True, ""
    if op in LEARN_OPS:
        return True, ""       # template markers; evaluated by the record evaluator
    return False, "unreachable"


def classify_reopen(ast: Any) -> str:
    """MONOTONE_TERMINAL (keyed solely on monotone Log events → latch once
    fired) vs RECORD_QUANTIFIED (quantifies over ARG records → re-checked every
    beat, §3.4). Any LEARN_*/EXISTS/COUNT anywhere makes it RECORD_QUANTIFIED."""
    def scan(node: Any) -> bool:
        if not isinstance(node, dict):
            return False
        op = node.get("op")
        if op in LEARN_OPS or op in RECORD_OPS or op in STATUS_OPS:
            return True
        if op in CMP_OPS and node.get("channel") not in MONOTONE_CHANNELS:
            return True
        return any(scan(a) for a in node.get("args", []))
    return "RECORD_QUANTIFIED" if scan(ast) else "MONOTONE_TERMINAL"


def eval_now(ast: Any, ctx: dict, record_eval: Optional[Callable] = None) -> bool:
    """Evaluate a compiled test against the current context.
    ctx = {"cur": {channel: value}, "prev": {channel: value}}.
    record_eval(node) → bool for LEARN_*/EXISTS/COUNT (supplied by the Executive
    in M5; absent → those nodes evaluate False, never error)."""
    if not isinstance(ast, dict):
        return False
    op = ast["op"]
    if op == "AND":
        return all(eval_now(a, ctx, record_eval) for a in ast["args"])
    if op == "OR":
        return any(eval_now(a, ctx, record_eval) for a in ast["args"])
    if op == "NOT":
        return not eval_now(ast["args"][0], ctx, record_eval)
    if op in CMP_OPS:
        cur = ctx.get("cur", {}).get(ast["channel"])
        if cur is None:
            return False
        if "value" in ast:
            rhs = ast["value"]
        else:  # vs previous turn's value
            rhs = ctx.get("prev", {}).get(ast["channel"])
            if rhs is None:
                return False
        try:
            if op == "GT":
                return cur > rhs
            if op == "GE":
                return cur >= rhs
            if op == "EQ":
                return cur == rhs
        except TypeError:
            return cur == rhs
    if op in RECORD_OPS or op in LEARN_OPS or op in STATUS_OPS:
        return bool(record_eval(ast)) if record_eval else False
    return False
