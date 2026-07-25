"""Seeded goal axioms (build plan §7, §3.2) — written once at store init.

Game-agnostic: no game nouns anywhere. G0 is the VALIDATED root with a
disjunctive progress test (kills the WIN-vs-levels_completed circular gate);
LEARN-* are RECORD_QUANTIFIED expansion templates the Surveyor instantiates
per game through the six gates (M5/M7). Ablatable via ARG_SEEDS=0 (A6).
"""

from __future__ import annotations

import json
from typing import Any

from . import config

# G0 disjunctive progress test (AST is data now; predicates.py evaluates it in M5)
G0_TEST: dict = {"op": "OR", "args": [
    {"op": "GT", "channel": "levels_completed", "vs": "prev"},
    {"op": "EQ", "channel": "state", "value": "WIN"},
    {"op": "GT", "channel": "score", "vs": "prev"},
]}
G0_DISCRIMINATOR: dict = {"any_monotone_progress_event": True}

# LEARN-* template markers — expanded per game (M5); RECORD_QUANTIFIED so they
# REOPEN when a fresh context class is minted (§3.4).
LEARN_TEMPLATES = [
    ("LEARN-ACTIONS", {"op": "LEARN_ACTIONS"}),
    ("LEARN-RULES", {"op": "LEARN_RULES"}),
    ("LEARN-ENV", {"op": "LEARN_ENV"}),
]


def write_seeds(store, run_id: str, turn_id: int = 0) -> dict:
    """Write G0 (VALIDATED) and the LEARN-* templates (PROPOSED). Returns the
    minted goal ids. No-op body if ARG_SEEDS=0 except G0 (the root is not a
    curriculum template — its absence would leave nothing to pursue)."""
    c = store.conn
    ids: dict = {}

    g0 = store.mint_id(run_id, "G", config.ID_WIDTH)
    c.execute(
        "INSERT INTO goal (run_id, goal_id, version, parent_goal, statement, "
        "achievement_test_json, discriminator_json, reopen_class, budget_actions, "
        "budget_search_calls, provenance, admitted_turn, created_turn) "
        "VALUES (?,?,1,NULL,?,?,?,?,?,?,?,?,?)",
        (run_id, g0, "win the game", json.dumps(G0_TEST), json.dumps(G0_DISCRIMINATOR),
         "MONOTONE_TERMINAL", config.MAX_ACTIONS, config.SURVEYOR_CALLS_PER_EPOCH,
         "SEEDED", turn_id, turn_id))
    _status(store, run_id, turn_id, "GOAL", g0, None, "VALIDATED", "seeded root")
    ids["G0"] = g0

    if config.SEEDS_ON:
        for name, test in LEARN_TEMPLATES:
            gid = store.mint_id(run_id, "G", config.ID_WIDTH)
            c.execute(
                "INSERT INTO goal (run_id, goal_id, version, parent_goal, statement, "
                "achievement_test_json, discriminator_json, reopen_class, budget_actions, "
                "budget_search_calls, provenance, admitted_turn, created_turn) "
                "VALUES (?,?,1,?,?,?,?,?,?,?,?,?,?)",
                (run_id, gid, g0, name, json.dumps(test), json.dumps({"template": name}),
                 "RECORD_QUANTIFIED", config.MAX_ACTIONS, config.SURVEYOR_CALLS_PER_EPOCH,
                 "SEEDED", turn_id, turn_id))
            _status(store, run_id, turn_id, "GOAL", gid, None, "PROPOSED", "seeded template")
            ids[name] = gid
    store.commit()
    return ids


def _status(store, run_id: str, turn_id: int, kind: str, eid: str,
            frm: Any, to: str, reason: str) -> None:
    seq = store.next_seq(run_id, "status_transition")
    store.conn.execute(
        "INSERT INTO status_transition (run_id, seq, turn_id, entity_kind, entity_id, "
        "from_status, to_status, reason) VALUES (?,?,?,?,?,?,?,?)",
        (run_id, seq, turn_id, kind, eid, frm, to, reason))
