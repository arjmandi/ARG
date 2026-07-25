"""ARG model store — arg_state.db (build plan §3).

One database per run. Append-only where evidence-bearing; versioned knowledge
rows are immutable (a new belief is a new (run,id,version) row, current =
MAX(version)); status is never stored, always computed from status_transition.
BEFORE UPDATE/DELETE triggers make the append-only invariant unforgeable at the
SQL layer (the `run` registry and mutable counters are the only exemptions).
"""

from __future__ import annotations

import sqlite3
from typing import Optional

# ---- DDL (build plan §3; context_class ordered before consequence_record for FK safety) ----
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS run (
  run_id TEXT PRIMARY KEY, game_id TEXT NOT NULL, backbone TEXT NOT NULL,
  seed INTEGER NOT NULL, config_json TEXT NOT NULL, render_ceiling_B INTEGER NOT NULL,
  started_at TEXT NOT NULL, ended_at TEXT,
  status TEXT NOT NULL DEFAULT 'RUNNING'
);

CREATE TABLE IF NOT EXISTS id_counter (
  run_id TEXT NOT NULL, prefix TEXT NOT NULL, next_val INTEGER NOT NULL,
  PRIMARY KEY (run_id, prefix));

CREATE TABLE IF NOT EXISTS locator (run_id TEXT NOT NULL REFERENCES run(run_id), locator_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('GridRegion','ActionSlot','TextSpan')),
  created_turn INTEGER NOT NULL, PRIMARY KEY (run_id, locator_id));
CREATE TABLE IF NOT EXISTS locator_gridregion (run_id TEXT NOT NULL, locator_id TEXT NOT NULL,
  cells_json TEXT NOT NULL, colors_json TEXT NOT NULL,
  bbox_x0 INTEGER NOT NULL, bbox_y0 INTEGER NOT NULL, bbox_x1 INTEGER NOT NULL, bbox_y1 INTEGER NOT NULL,
  PRIMARY KEY (run_id, locator_id));
CREATE TABLE IF NOT EXISTS locator_actionslot (run_id TEXT NOT NULL, locator_id TEXT NOT NULL,
  action_id INTEGER NOT NULL CHECK (action_id BETWEEN 1 AND 7), param_schema_json TEXT NOT NULL,
  PRIMARY KEY (run_id, locator_id));
CREATE TABLE IF NOT EXISTS locator_textspan (run_id TEXT NOT NULL, locator_id TEXT NOT NULL, doc_id TEXT NOT NULL,
  start_off INTEGER NOT NULL, end_off INTEGER NOT NULL, PRIMARY KEY (run_id, locator_id));

CREATE TABLE IF NOT EXISTS referent (run_id TEXT NOT NULL REFERENCES run(run_id), ref_id TEXT NOT NULL,
  version INTEGER NOT NULL, kind TEXT NOT NULL CHECK (kind IN ('percept-cluster','region','action','signal')),
  anchor_locator_id TEXT NOT NULL, signature TEXT NOT NULL, first_seen INTEGER NOT NULL,
  provenance TEXT NOT NULL DEFAULT 'OBSERVER_BIND' CHECK (provenance IN ('OBSERVER_BIND','FISSION','MERGE')),
  created_turn INTEGER NOT NULL, PRIMARY KEY (run_id, ref_id, version));

CREATE TABLE IF NOT EXISTS referent_alias (
  run_id TEXT NOT NULL, ref_id TEXT NOT NULL, seq INTEGER NOT NULL, turn_id INTEGER NOT NULL,
  label TEXT NOT NULL, PRIMARY KEY (run_id, ref_id, seq));

CREATE TABLE IF NOT EXISTS relation (run_id TEXT NOT NULL, rel_id TEXT NOT NULL, version INTEGER NOT NULL,
  verb TEXT NOT NULL CHECK (verb IN ('requires','enables','blocks','toggles','part_of','adjacent','same_as')),
  src_ref TEXT NOT NULL, dst_ref TEXT NOT NULL, claim TEXT,
  scope TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK (scope IN ('WITHIN_LIFE','PERSISTENT','UNKNOWN')),
  created_turn INTEGER NOT NULL, PRIMARY KEY (run_id, rel_id, version));

CREATE TABLE IF NOT EXISTS rule (run_id TEXT NOT NULL, rule_id TEXT NOT NULL, version INTEGER NOT NULL,
  template TEXT NOT NULL, ctx_pred_json TEXT NOT NULL, effect_pattern_json TEXT NOT NULL,
  scope TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK (scope IN ('WITHIN_LIFE','PERSISTENT','UNKNOWN')),
  ttl_turn INTEGER, test_plan TEXT, created_turn INTEGER NOT NULL,
  PRIMARY KEY (run_id, rule_id, version));

CREATE TABLE IF NOT EXISTS goal (run_id TEXT NOT NULL, goal_id TEXT NOT NULL, version INTEGER NOT NULL,
  parent_goal TEXT, statement TEXT NOT NULL, achievement_test_json TEXT NOT NULL,
  discriminator_json TEXT NOT NULL,
  reopen_class TEXT NOT NULL CHECK (reopen_class IN ('MONOTONE_TERMINAL','RECORD_QUANTIFIED')),
  rejection_reason TEXT, budget_actions INTEGER NOT NULL, budget_search_calls INTEGER NOT NULL,
  provenance TEXT NOT NULL, admitted_turn INTEGER, created_turn INTEGER NOT NULL,
  PRIMARY KEY (run_id, goal_id, version));
CREATE TABLE IF NOT EXISTS goal_binding (run_id TEXT NOT NULL, goal_id TEXT NOT NULL, goal_version INTEGER NOT NULL,
  ref_id TEXT NOT NULL, PRIMARY KEY (run_id, goal_id, goal_version, ref_id));
-- goal-chain dependency edges: child FILLS a named hole of parent; verified=1
-- means the Executive mechanically proved the fill (an LLM cannot assert it)
CREATE TABLE IF NOT EXISTS goal_edge (run_id TEXT NOT NULL, parent_goal TEXT NOT NULL,
  child_goal TEXT NOT NULL, hole_json TEXT NOT NULL, verified INTEGER NOT NULL DEFAULT 0,
  created_turn INTEGER NOT NULL, PRIMARY KEY (run_id, parent_goal, child_goal));
-- the recognizer's auditable "chain incomplete HERE" record: typed holes with
-- their derivable evidence at stamp time (deduped per goal by the Executive)
CREATE TABLE IF NOT EXISTS deficit_stamp (run_id TEXT NOT NULL, seq INTEGER NOT NULL,
  turn_id INTEGER NOT NULL, goal_id TEXT NOT NULL, holes_json TEXT NOT NULL,
  PRIMARY KEY (run_id, seq));

CREATE TABLE IF NOT EXISTS commitment (run_id TEXT NOT NULL, commit_id TEXT NOT NULL, version INTEGER NOT NULL,
  goal_id TEXT NOT NULL, compiled_turn INTEGER NOT NULL, procedure_id TEXT, created_turn INTEGER NOT NULL,
  PRIMARY KEY (run_id, commit_id, version));
CREATE TABLE IF NOT EXISTS commitment_step (run_id TEXT NOT NULL, commit_id TEXT NOT NULL, commit_version INTEGER NOT NULL,
  step_id TEXT NOT NULL, step_ord INTEGER NOT NULL, kind TEXT NOT NULL CHECK (kind IN ('NAVIGATE','INTERACT','PROBE')),
  target_ref TEXT, action TEXT, param_schema_json TEXT NOT NULL, predicted_delta_json TEXT,
  then_slot_step TEXT, precond_json TEXT NOT NULL, compilation_turn_id INTEGER NOT NULL,
  lease_max_beats INTEGER NOT NULL, PRIMARY KEY (run_id, commit_id, commit_version, step_id));
CREATE TABLE IF NOT EXISTS step_premise (run_id TEXT NOT NULL, commit_id TEXT NOT NULL, commit_version INTEGER NOT NULL,
  step_id TEXT NOT NULL, member_kind TEXT NOT NULL CHECK (member_kind IN ('RULE','GOAL_BINDING','TARGET_REF')),
  member_id TEXT NOT NULL, PRIMARY KEY (run_id, commit_id, commit_version, step_id, member_kind, member_id));

CREATE TABLE IF NOT EXISTS procedure (run_id TEXT NOT NULL, proc_id TEXT NOT NULL, version INTEGER NOT NULL,
  scope_fingerprint TEXT NOT NULL, distilled_from_commit TEXT, created_turn INTEGER NOT NULL,
  PRIMARY KEY (run_id, proc_id, version));
CREATE TABLE IF NOT EXISTS procedure_slot (run_id TEXT NOT NULL, proc_id TEXT NOT NULL, proc_version INTEGER NOT NULL,
  slot_ord INTEGER NOT NULL, action_kind TEXT NOT NULL, referent_role_slot TEXT NOT NULL,
  expected_delta_shape_json TEXT NOT NULL, PRIMARY KEY (run_id, proc_id, proc_version, slot_ord));
CREATE TABLE IF NOT EXISTS experiment (run_id TEXT NOT NULL, exp_id TEXT NOT NULL, version INTEGER NOT NULL,
  proposed_turn INTEGER NOT NULL, epoch_id TEXT NOT NULL, target_ref TEXT, action TEXT,
  predicted_delta_json TEXT NOT NULL, discriminates_json TEXT NOT NULL, PRIMARY KEY (run_id, exp_id, version));

CREATE TABLE IF NOT EXISTS context_class (run_id TEXT NOT NULL, context_class_id TEXT NOT NULL, action_id INTEGER,
  partition_signature TEXT NOT NULL, minted_turn INTEGER NOT NULL, level_index INTEGER NOT NULL,
  PRIMARY KEY (run_id, context_class_id));

CREATE TABLE IF NOT EXISTS referent_lineage (run_id TEXT NOT NULL, seq INTEGER NOT NULL, turn_id INTEGER NOT NULL,
  op TEXT NOT NULL CHECK (op IN ('FISSION_SPLIT','MERGE_CANONICAL')), parent_ref TEXT NOT NULL,
  child_ref TEXT NOT NULL, PRIMARY KEY (run_id, seq));
CREATE TABLE IF NOT EXISTS binding_record (run_id TEXT NOT NULL, turn_id INTEGER NOT NULL, component_hash TEXT NOT NULL,
  anchor_cells_json TEXT NOT NULL, anchor_bbox_json TEXT NOT NULL, anchor_signature TEXT NOT NULL,
  bound_to TEXT NOT NULL, is_new INTEGER NOT NULL DEFAULT 0, runner_up TEXT, margin REAL NOT NULL,
  PRIMARY KEY (run_id, turn_id, component_hash));
CREATE TABLE IF NOT EXISTS consequence_record (run_id TEXT NOT NULL, turn_id INTEGER NOT NULL, seq INTEGER NOT NULL,
  action TEXT NOT NULL, target_ref TEXT, context_class_id TEXT NOT NULL,
  predicted_delta_json TEXT, observed_delta_json TEXT NOT NULL, match INTEGER,
  predictor_id TEXT, predictor_kind TEXT CHECK (predictor_kind IN ('STEP','RULE','EXPERIMENT')),
  score_event INTEGER NOT NULL DEFAULT 0, level_event INTEGER NOT NULL DEFAULT 0,
  life_event INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (run_id, turn_id, seq));
CREATE TABLE IF NOT EXISTS relevance_edge (run_id TEXT NOT NULL, seq INTEGER NOT NULL, turn_id INTEGER NOT NULL,
  goal_id TEXT NOT NULL, target_kind TEXT NOT NULL CHECK (target_kind IN ('RULE','REFERENT')),
  target_id TEXT NOT NULL, PRIMARY KEY (run_id, seq));
CREATE TABLE IF NOT EXISTS status_transition (run_id TEXT NOT NULL, seq INTEGER NOT NULL, turn_id INTEGER NOT NULL,
  entity_kind TEXT NOT NULL CHECK (entity_kind IN ('REFERENT_RUNG','REFERENT_CONTROLLABLE','RELATION','RULE',
    'GOAL','PROCEDURE','COMMITMENT_STEP','EXPERIMENT','REFERENT_FISSION','REFERENT_LIFE')),
  entity_id TEXT NOT NULL, from_status TEXT, to_status TEXT NOT NULL, reason TEXT,
  PRIMARY KEY (run_id, seq));
CREATE TABLE IF NOT EXISTS turn_record (run_id TEXT NOT NULL, turn_id INTEGER NOT NULL, action TEXT NOT NULL,
  params_json TEXT, target_ref TEXT, pre_frame_hash TEXT NOT NULL, post_frame_hash TEXT NOT NULL,
  raw_diff_json TEXT NOT NULL, predicted_delta_json TEXT, observed_delta_json TEXT, match INTEGER,
  score INTEGER NOT NULL, level_counter INTEGER NOT NULL, state_flags TEXT NOT NULL, lives INTEGER,
  commitment_step_id TEXT,
  source_stamp TEXT NOT NULL CHECK (source_stamp IN ('COMMITMENT_STEP','PROBE','ACTUATOR_LLM','FALLBACK','RESET')),
  render_tokens INTEGER NOT NULL, shadow_step_id TEXT, drift_ref TEXT CHECK (drift_ref IN ('LIVE','SHADOW')),
  PRIMARY KEY (run_id, turn_id));
CREATE TABLE IF NOT EXISTS write_reject (run_id TEXT NOT NULL, seq INTEGER NOT NULL, turn_id INTEGER NOT NULL,
  organ TEXT NOT NULL CHECK (organ IN ('OBSERVER','SURVEYOR','ACTUATOR')), op_type TEXT NOT NULL,
  violation_class TEXT NOT NULL, retry_count INTEGER NOT NULL, PRIMARY KEY (run_id, seq));
CREATE TABLE IF NOT EXISTS substitution_caught (run_id TEXT NOT NULL, seq INTEGER NOT NULL, turn_id INTEGER NOT NULL,
  step_target TEXT NOT NULL, landed_target TEXT, PRIMARY KEY (run_id, seq));
CREATE TABLE IF NOT EXISTS revision (run_id TEXT NOT NULL, seq INTEGER NOT NULL, turn_id INTEGER NOT NULL,
  step_id TEXT NOT NULL, evidence_ptr TEXT NOT NULL, PRIMARY KEY (run_id, seq));
CREATE TABLE IF NOT EXISTS annotate (run_id TEXT NOT NULL, seq INTEGER NOT NULL, turn_id INTEGER NOT NULL,
  text TEXT NOT NULL, PRIMARY KEY (run_id, seq));

CREATE TABLE IF NOT EXISTS action_model (run_id TEXT NOT NULL, seq INTEGER NOT NULL, turn_id INTEGER NOT NULL,
  action TEXT NOT NULL, dx INTEGER NOT NULL, dy INTEGER NOT NULL, quantum INTEGER NOT NULL,
  support INTEGER NOT NULL, mover_sig TEXT, PRIMARY KEY (run_id, seq));

CREATE TABLE IF NOT EXISTS seed_import (run_id TEXT NOT NULL, seq INTEGER NOT NULL, prior_run_id TEXT NOT NULL,
  imported_rule_id TEXT NOT NULL, new_rule_id TEXT NOT NULL, prior_support INTEGER NOT NULL,
  imported_turn INTEGER NOT NULL, PRIMARY KEY (run_id, seq));

CREATE INDEX IF NOT EXISTS idx_consequence_turn      ON consequence_record(run_id, turn_id);
CREATE INDEX IF NOT EXISTS idx_consequence_target    ON consequence_record(run_id, target_ref, context_class_id);
CREATE INDEX IF NOT EXISTS idx_consequence_predictor ON consequence_record(run_id, predictor_id, match);
CREATE INDEX IF NOT EXISTS idx_binding_turn          ON binding_record(run_id, turn_id);
CREATE INDEX IF NOT EXISTS idx_binding_bound         ON binding_record(run_id, bound_to);
CREATE INDEX IF NOT EXISTS idx_status_current        ON status_transition(run_id, entity_kind, entity_id, seq DESC);
CREATE INDEX IF NOT EXISTS idx_goal_binding_ref      ON goal_binding(run_id, ref_id);
CREATE INDEX IF NOT EXISTS idx_step_premise_member   ON step_premise(run_id, member_kind, member_id);
CREATE INDEX IF NOT EXISTS idx_relevance_goal        ON relevance_edge(run_id, goal_id);
"""

# Append-only invariant: no UPDATE, no DELETE on evidence + versioned knowledge.
# The `run` registry (close-out mutates ended_at/status) and `id_counter`
# (minting) are the deliberate exemptions.
_MUTABLE = {"run", "id_counter"}
_PROTECTED = [
    "locator", "locator_gridregion", "locator_actionslot", "locator_textspan",
    "referent", "referent_alias", "relation", "rule", "goal", "goal_binding", "goal_edge",
    "deficit_stamp",
    "commitment", "commitment_step", "step_premise", "procedure", "procedure_slot",
    "experiment", "context_class", "referent_lineage", "binding_record",
    "consequence_record", "relevance_edge", "status_transition", "turn_record",
    "write_reject", "substitution_caught", "revision", "annotate", "action_model",
    "seed_import",
]


def _append_only_triggers() -> str:
    out = []
    for t in _PROTECTED:
        out.append(
            f"CREATE TRIGGER IF NOT EXISTS trg_{t}_noupd BEFORE UPDATE ON {t} "
            f"BEGIN SELECT RAISE(ABORT, 'append-only: {t} is immutable'); END;")
        out.append(
            f"CREATE TRIGGER IF NOT EXISTS trg_{t}_nodel BEFORE DELETE ON {t} "
            f"BEGIN SELECT RAISE(ABORT, 'append-only: {t} is immutable'); END;")
    return "\n".join(out)


class Store:
    """Owns the model DB connection and the append-only + versioning invariants."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA_SQL)
        self.conn.executescript(_append_only_triggers())
        self.conn.commit()

    # ---- id minting: per-run, per-type, gapless, zero-padded, widen-not-wrap ----
    def mint_id(self, run_id: str, prefix: str, width: int) -> str:
        cur = self.conn.execute(
            "SELECT next_val FROM id_counter WHERE run_id=? AND prefix=?", (run_id, prefix))
        row = cur.fetchone()
        n = row["next_val"] if row else 1
        self.conn.execute(
            "INSERT INTO id_counter (run_id, prefix, next_val) VALUES (?,?,?) "
            "ON CONFLICT(run_id, prefix) DO UPDATE SET next_val=?",
            (run_id, prefix, n + 1, n + 1))
        digits = max(width, len(str(n)))   # widen, never wrap
        return f"{prefix}{n:0{digits}d}"

    def next_seq(self, run_id: str, table: str) -> int:
        row = self.conn.execute(
            f"SELECT COALESCE(MAX(seq), 0) + 1 AS s FROM {table} WHERE run_id=?", (run_id,)).fetchone()
        return int(row["s"])

    def current_version(self, run_id: str, table: str, id_col: str, entity_id: str) -> int:
        row = self.conn.execute(
            f"SELECT MAX(version) AS v FROM {table} WHERE run_id=? AND {id_col}=?",
            (run_id, entity_id)).fetchone()
        return int(row["v"]) if row and row["v"] is not None else 0

    def register_run(self, run_id: str, game_id: str, backbone: str, seed: int,
                     config_json: str, render_ceiling_B: int, started_at: str) -> None:
        self.conn.execute(
            "INSERT OR IGNORE INTO run (run_id, game_id, backbone, seed, config_json, "
            "render_ceiling_B, started_at) VALUES (?,?,?,?,?,?,?)",
            (run_id, game_id, backbone, seed, config_json, render_ceiling_B, started_at))
        self.conn.commit()

    def close_run(self, run_id: str, ended_at: str, status: str = "COMPLETED") -> None:
        self.conn.execute("UPDATE run SET ended_at=?, status=? WHERE run_id=?",
                          (ended_at, status, run_id))
        self.conn.commit()

    def commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        try:
            self.conn.commit()
        finally:
            self.conn.close()
