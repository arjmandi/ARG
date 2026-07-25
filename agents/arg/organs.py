"""The three LLM role contracts (build plan §5).

Observer / Surveyor / Actuator are hard-isolated dspy signatures around the one
store; the rendered views are the only shared state. Each emits typed proposals
in a closed vocabulary (JSON strings) plus a mandatory canary_echo — the LLM
proposes, the Executive (validate_ingest) disposes. configure_llm is local
infrastructure (mirrors the validated Sensi anthropic pattern) so ARG imports no
Sensi organ.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, List, Optional

import dspy

_CONFIGURED = False


def configure_llm(model: Optional[str] = None, effort: Optional[str] = None) -> None:
    """Configure dspy for ARG. Anthropic models reject `temperature` and take
    reasoning effort as adaptive thinking + output_config (verified live in the
    Sensi campaign)."""
    global _CONFIGURED
    from . import config as cfg
    model = model or cfg.MODEL
    effort = effort if effort is not None else cfg.REASONING_EFFORT
    lm = dspy.LM(model, cache=False)
    lm.kwargs.pop("max_completion_tokens", None)
    lm.kwargs["max_tokens"] = cfg.MAX_TOKENS
    if cfg.TEMPERATURE is not None:
        lm.kwargs["temperature"] = float(cfg.TEMPERATURE)
    elif model.startswith("anthropic/") or "fable" in model.lower():
        lm.kwargs["temperature"] = None
    else:
        lm.kwargs["temperature"] = 0.3
    if effort:
        if model.startswith("anthropic/"):
            # adaptive thinking + output_config is the Sonnet-5/Fable-class
            # surface; Haiku-class models reject it (batch-4 hk1 lesson:
            # every organ call 400'd) — they take standard extended thinking
            # with an effort-mapped budget under MAX_TOKENS
            if "haiku" in model.lower():
                budget = {"low": 1024, "medium": 4096, "high": 8192,
                          "xhigh": 12000, "max": 12000}.get(effort, 4096)
                lm.kwargs["thinking"] = {"type": "enabled",
                                         "budget_tokens": min(budget, cfg.MAX_TOKENS - 2000)}
            else:
                lm.kwargs["thinking"] = {"type": "adaptive"}
                lm.kwargs["output_config"] = {"effort": effort}
            lm.kwargs["temperature"] = None
        else:
            lm.kwargs["reasoning_effort"] = effort
    dspy.settings.configure(lm=lm)
    _CONFIGURED = True


def last_usage() -> dict:
    """Token usage of the most recent LM call from dspy's history — the real
    accounting the §8 cost tables require (Q9)."""
    try:
        lm = dspy.settings.lm
        hist = getattr(lm, "history", None) or []
        u = (hist[-1] or {}).get("usage") or {}
        return {"prompt_tokens": int(u.get("prompt_tokens") or 0),
                "completion_tokens": int(u.get("completion_tokens") or 0)}
    except Exception:
        return {"prompt_tokens": 0, "completion_tokens": 0}


def _strip_json(text: str) -> Any:
    """Robustly extract a JSON value from an LLM field (fences, prose wrap)."""
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    try:
        return json.loads(t)
    except ValueError:
        m = re.search(r"(\[.*\]|\{.*\})", t, re.S)
        if m:
            try:
                return json.loads(m.group(1))
            except ValueError:
                return None
        return None


def _echo_list(text: str) -> List[str]:
    v = _strip_json(text)
    if isinstance(v, list):
        return [str(x) for x in v]
    if text:
        return [s.strip() for s in re.split(r"[,\s]+", text) if s.strip().startswith("ZQ")]
    return []


# ---- Contract 1: Observer (B5, only on an unexplained ChangeSet) ----
class ObserverDelta(dspy.Signature):
    """You interpret a pre-computed change in a puzzle world. You are told
    NOTHING about what anything MEANS. The engine has already segmented the
    frame AND SETTLED IDENTITY deterministically — do NOT emit BIND ops and
    never invent an anchor or a coordinate. You emit typed deltas over the
    pre-anchored ids in a CLOSED vocabulary. Output `ops` as a JSON list of
    objects, each one of:
      {"op":"NOTE_EVENT","ref":"R####","event_kind":<one of: score |
       levels_completed | state | lives — NOTHING else is a valid event_kind>,
       "turn_id":<int>}
      {"op":"PROPOSE_RELATION","verb":<requires|enables|blocks|toggles|part_of|adjacent|same_as>,
       "src":"R####","dst":"R####","evidence":"..."}
      {"op":"PROPOSE_RULE","template":"<one-line prose>",
       "ctx":{"action":"ACTION1".."ACTION7","target":"R####" or null,"when":null},
       "effect":{"cells_changed":"zero"|"nonzero","score_event":0|1,"level_event":0|1}}
        (rules outside this EXACT ctx/effect vocabulary are REJECTED; the engine
         pre-registers your rule's prediction before acting and computes the
         match itself — only such rules can ever become TESTED)
      {"op":"INTERPRET","ref":"R####","label":"<cosmetic name>"}
      {"op":"ANNOTATE","text":"<free note, quarantined>"}
    Echo the zone-prefixed canary nonces you see in `canary_echo`."""
    changeset: str = dspy.InputField(desc="The pre-computed change: candidate hashes + their anchors.")
    log_tail: str = dspy.InputField(desc="Recent turns: action taken and its pre-committed prediction.")
    view: str = dspy.InputField(desc="Z1+Z2+Z5 of the fixed layout (roster + render joins).")
    ops: str = dspy.OutputField(desc="JSON list of typed ObservationDelta ops (closed vocabulary).")
    canary_echo: str = dspy.OutputField(desc="JSON list of the zone canary nonces observed.")


# ---- Contract 2: Surveyor (Epoch, event-triggered) ----
class SurveyorProposals(dspy.Signature):
    """You are the separate search mechanism: you reason over the referent
    structure and propose expansions of a live agenda — you never act, never
    write a fact, never mark a goal done, never touch an anchor. If the view
    carries a DEFICIT block, that is THE question: propose sub-goals that fill
    EXACTLY those holes (set "parent" to the deficient goal id and
    "fills_hole" to the hole id, e.g. "G0001/H0"); the engine PROVES each fill
    mechanically — aim the test at the hole's effect key, or at a knowledge
    milestone over a rule that carries it. At most ONE proposal per hole id
    per epoch, and NEVER restate an intent a live goal in the GOAL TREE
    already covers (near-duplicates are REJECTED and cost your write budget).
    "bindings" may ONLY name referent ids visible in the current roster (Z2)
    — an id you remember but do not see is REJECTED; use [] when no referent
    is load-bearing. Emit `proposals` as a JSON list, each one of:
      {"op":"PROPOSE_GOAL","statement":"...","bindings":["R####"],
       "achievement_test":<AST — ONLY this closed grammar, nothing else:
         leaf: {"op":"GT"|"GE"|"EQ","channel":"score"|"levels_completed"|"state"|"lives",
                "vs":"prev"} or {...,"value":<literal>}
         node: {"op":"AND"|"OR"|"NOT","args":[<AST>,...]}
         knowledge milestones over ENGINE-STAMPED records (the sub-goal
         vocabulary — nothing appearance-based can enter):
           {"op":"EXISTS"|"COUNT","entity":"consequence","where":{"action":"ACTION#",
            "target":"R####","match":0|1,"predictor":"RU####","score_event":0|1,
            "level_event":0|1},"value":<int — COUNT only>}
             e.g. "deliberately test RU0007" is {"op":"COUNT","entity":"consequence",
             "where":{"predictor":"RU0007","match":1},"value":2}
           {"op":"COUNT","entity":"rule","where":{"status":"HYPOTHESIS"|"TESTED"|"DEMOTED"},
            "value":<int>}
           {"op":"COUNT","entity":"referent","where":{"rung":"ANCHORED"|"ENGAGED"|
            "CHARACTERIZED"},"value":<int>}
           {"op":"RULE_STATUS","rule":"RU####","is":"TESTED"}
           {"op":"RUNG","ref":"R####","at_least":"ENGAGED"|"CHARACTERIZED"}
         e.g. {"op":"GT","channel":"score","vs":"prev"} — a test naming anything
         else (colors, positions, "door opens") is REJECTED as incompilable>,
       "discriminator":{"<how success differs from luck>"} — REQUIRED on EVERY
        PROPOSE_GOAL; omitting it is an automatic REJECT,
       "evidence_ptrs":[<turn numbers>],"parent":"G####",
       "fills_hole":"G####/H#" (ONLY when answering a DEFICIT hole)}
      {"op":"PROPOSE_RELATION","verb":<requires|enables|blocks|toggles|part_of|adjacent|same_as
       — NOTHING else is a valid verb>,"src":"R####","dst":"R####","test_plan":"..."}
      {"op":"PROPOSE_RULE","template":"<one-line prose>",
       "ctx":{"action":"ACTION1".."ACTION7","target":"R####" or null,"when":null},
       "effect":{"cells_changed":"zero"|"nonzero","score_event":0|1,"level_event":0|1},
       "test_plan":"..."}   (rules outside this EXACT ctx/effect vocabulary are REJECTED)
      {"op":"PROPOSE_EXPERIMENT","action":"ACTION1".."ACTION7","target":"R####" or null,
       "predicted":{<same closed effect vocabulary>},"discriminates":["RU####",...]}
      {"op":"ABORT_STEP","step_id":"...","evidence_ptr":"turn:<n>|rule:<id>|goal:<id>|step:<id>"}
        (ONLY for a step_id shown in the view's ACTIVE line; if no step is
         active there is nothing to abort — do not emit this op)
      {"op":"RANK_TIEBREAK","goal_id":"G####","before":"G####","evidence_ptr":"..."}
    Every achievement_test must compile in the closed predicate grammar, be
    evaluable now (false, not error), and NOT already be true — a test that is
    TRUE right now is REJECTED as zero-information (cite that record in
    evidence_ptrs for your NEXT goal instead). Echo the canary nonces in
    `canary_echo`."""
    trigger: str = dspy.InputField(desc="Which trigger fired (T1..T5).")
    budgeted_view: str = dspy.InputField(desc="Goal chain + frontier + stale/uncertain slices under B.")
    counterexample_buckets: str = dspy.InputField(desc="Mechanical counterexample aggregation per rule.")
    proposals: str = dspy.OutputField(desc="JSON list of PROPOSED, gated proposals.")
    canary_echo: str = dspy.OutputField(desc="JSON list of the zone canary nonces observed.")


# ---- Comparator contract: one decision per beat (bare/raw/B-CACHE, §8) ----
class BaselineDecide(dspy.Signature):
    """You are playing a grid puzzle game. Make verified progress: raise the
    score, complete levels, reach WIN. Pick exactly ONE next action from the
    AVAILABLE list in the view. Output the action name; for ACTION6 also give
    x and y (0-63)."""
    view: str = dspy.InputField(desc="Current state (and, if present, history).")
    action: str = dspy.OutputField(desc="One available action name, e.g. ACTION3.")
    x: str = dspy.OutputField(desc="ACTION6 column 0-63 (else 0).")
    y: str = dspy.OutputField(desc="ACTION6 row 0-63 (else 0).")


def run_baseline(view: str) -> dict:
    out = dspy.Predict(BaselineDecide)(view=view)

    def _int(v):
        try:
            return max(0, min(63, int(str(v).strip())))
        except (ValueError, TypeError):
            return 0
    return {"action": (out.action or "").strip().upper(), "x": _int(out.x), "y": _int(out.y),
            "raw": out}


# ---- Contract 3: Actuator (B1 exception, param realization only) ----
class ActuatorRealize(dspy.Signature):
    """A commitment step underdetermines a concrete command (e.g. WHERE within a
    target region to click). Realize ONLY the parameter. You cannot pick a goal
    or skip a step. The (x,y) you emit MUST lie inside the cited referent's cells
    — a coordinate copied from another row is a caught violation. Echo the canary
    nonces in `canary_echo`."""
    answer_view: str = dspy.InputField(desc="Z1+Z2+Z5+Z6; Z6 states the step imperatively with deps.")
    target_roster_row: str = dspy.InputField(desc="The target referent's roster row (only row on retry).")
    param_schema: str = dspy.InputField(desc="The step's parameter schema (e.g. {x:[0,63],y:[0,63]}).")
    action: str = dspy.OutputField(desc="The action name (Executive-fixed; validated equal).")
    x: str = dspy.OutputField(desc="ACTION6 column 0-63 (else 0).")
    y: str = dspy.OutputField(desc="ACTION6 row 0-63 (else 0).")
    canary_echo: str = dspy.OutputField(desc="JSON list of the zone canary nonces observed.")


def run_observer(changeset: str, log_tail: str, view: str) -> dict:
    out = dspy.Predict(ObserverDelta)(changeset=changeset, log_tail=log_tail, view=view)
    return {"ops": _strip_json(out.ops) or [], "canary_echo": _echo_list(out.canary_echo), "raw": out}


_OP_EXAMPLES_BLOCK = """
WORKED EXAMPLES — copy these SHAPES exactly (fields, casing, closed values);
change only the ids and values:
  {"op":"PROPOSE_GOAL","statement":"deliberately test RU0007","bindings":[],
   "achievement_test":{"op":"COUNT","entity":"consequence",
    "where":{"predictor":"RU0007","match":1},"value":2},
   "discriminator":{"rule_receipt":"RU0007"},"evidence_ptrs":[41],
   "parent":"G0001","fills_hole":"G0001/H0"}
  {"op":"PROPOSE_RULE","template":"clicking R0004 scores",
   "ctx":{"action":"ACTION6","target":"R0004","when":null},
   "effect":{"cells_changed":"nonzero","score_event":1,"level_event":0},
   "test_plan":"click R0004 twice and watch the score channel"}
  {"op":"PROPOSE_EXPERIMENT","action":"ACTION3","target":null,
   "predicted":{"cells_changed":"nonzero"},"discriminates":["RU0002"]}
  {"op":"PROPOSE_RELATION","verb":"blocks","src":"R0002","dst":"R0005",
   "test_plan":"move toward R0005 with R0002 present vs absent"}
EVERY PROPOSE_GOAL MUST carry non-empty "evidence_ptrs" — turn numbers you
actually observed in the view/log (omitting them is an automatic REJECT)."""


def _surveyor_sig():
    """The pinned contract, plus worked per-op examples when the small-backbone
    lever is on (ARG_OP_EXAMPLES; P4 emission aid — never the Sonnet default)."""
    from . import config as cfg
    if cfg.OP_EXAMPLES:
        return SurveyorProposals.with_instructions(
            SurveyorProposals.instructions + _OP_EXAMPLES_BLOCK)
    return SurveyorProposals


def run_surveyor(trigger: str, budgeted_view: str, counterexample_buckets: str) -> dict:
    out = dspy.Predict(_surveyor_sig())(trigger=trigger, budgeted_view=budgeted_view,
                                        counterexample_buckets=counterexample_buckets)
    return {"proposals": _strip_json(out.proposals) or [], "canary_echo": _echo_list(out.canary_echo),
            "raw": out}


def run_actuator(answer_view: str, target_roster_row: str, param_schema: str) -> dict:
    out = dspy.Predict(ActuatorRealize)(answer_view=answer_view, target_roster_row=target_roster_row,
                                        param_schema=param_schema)

    def _int(v):
        try:
            return int(str(v).strip())
        except (ValueError, TypeError):
            return 0
    return {"action": (out.action or "").strip(), "x": _int(out.x), "y": _int(out.y),
            "canary_echo": _echo_list(out.canary_echo), "raw": out}
