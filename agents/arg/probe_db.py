"""ARG observability store — arg_probe.db (build plan §8).

WRITE-SEPARATE from the model store: a distinct connection so probe writes can
never mutate ARG's beliefs and a probe is never a model-facing surface. Captures
the owner's required "full picture": every ARC HTTP round-trip, the scorecard of
each play, per-call LLM cost, run config, rendered views, ZCR canaries, and the
run-validity verdict — all keyed run_id then turn_id.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Optional

PROBE_SCHEMA = """
CREATE TABLE IF NOT EXISTS run_config (
  run_id TEXT PRIMARY KEY, card_id TEXT, game_id TEXT, guid TEXT,
  cell_json TEXT, baseline TEXT, backbone TEXT, seed INTEGER, config_json TEXT,
  arm TEXT, comparison_group TEXT, started_at TEXT, ended_at TEXT);

-- every HTTP round-trip regardless of issuer; columns aligned to Sensi so
-- probe_rhae.py runs unmodified (action, levels_completed, game_id, card_id).
CREATE TABLE IF NOT EXISTS api_log (
  run_id TEXT NOT NULL, turn_id INTEGER NOT NULL, step_id INTEGER NOT NULL,
  action TEXT NOT NULL, source_stamp TEXT, request_json TEXT, response_json TEXT,
  status_code INTEGER, game_id TEXT, card_id TEXT, guid TEXT,
  score INTEGER, levels_completed INTEGER, state TEXT, frame_received INTEGER NOT NULL DEFAULT 0,
  ts TEXT, PRIMARY KEY (run_id, turn_id, step_id));

CREATE TABLE IF NOT EXISTS scorecards (
  run_id TEXT NOT NULL, seq INTEGER NOT NULL, turn_id INTEGER NOT NULL,
  card_id TEXT, game_id TEXT, scorecard_json TEXT, captured_at TEXT,
  PRIMARY KEY (run_id, seq));

CREATE TABLE IF NOT EXISTS llm_calls (
  run_id TEXT NOT NULL, seq INTEGER NOT NULL, turn_id INTEGER NOT NULL, organ TEXT NOT NULL,
  backbone TEXT, call_idx INTEGER, retry_count INTEGER NOT NULL DEFAULT 0,
  prompt_tokens INTEGER, completion_tokens INTEGER, reasoning_tokens INTEGER,
  render_tokens INTEGER, ops_accepted INTEGER DEFAULT 0, ops_rejected INTEGER DEFAULT 0,
  effort TEXT, zcr_json TEXT, ts TEXT, PRIMARY KEY (run_id, seq));

CREATE TABLE IF NOT EXISTS render_capture (
  run_id TEXT NOT NULL, turn_id INTEGER NOT NULL, call_idx INTEGER NOT NULL, organ TEXT,
  zone_tier TEXT, view_bytes TEXT, render_tokens INTEGER, shadow_flag INTEGER DEFAULT 0,
  rank_snapshot TEXT, PRIMARY KEY (run_id, turn_id, call_idx, zone_tier));

CREATE TABLE IF NOT EXISTS zcr_salt (
  run_id TEXT NOT NULL, seq INTEGER NOT NULL, turn_id INTEGER NOT NULL, organ TEXT,
  call_idx INTEGER, zone_tier TEXT, nonce TEXT, PRIMARY KEY (run_id, seq));
CREATE TABLE IF NOT EXISTS zcr_echo (
  run_id TEXT NOT NULL, seq INTEGER NOT NULL, turn_id INTEGER NOT NULL, organ TEXT,
  call_idx INTEGER, zone_tier TEXT, nonce TEXT, echoed INTEGER NOT NULL, PRIMARY KEY (run_id, seq));

CREATE TABLE IF NOT EXISTS startup_probe (
  run_id TEXT PRIMARY KEY, image_receipt_ok INTEGER, signal_vocab_json TEXT,
  action_interface_json TEXT);

CREATE TABLE IF NOT EXISTS run_validity (
  run_id TEXT PRIMARY KEY, verdict TEXT, r9_breaches INTEGER DEFAULT 0,
  silent_degrade_count INTEGER DEFAULT 0, wer_floor_ok INTEGER, zcr_uniform_fail INTEGER,
  detail_json TEXT);

CREATE INDEX IF NOT EXISTS idx_api_turn ON api_log(run_id, turn_id);
CREATE INDEX IF NOT EXISTS idx_llm_turn ON llm_calls(run_id, turn_id, organ);
"""


class ProbeStore:
    """Executive-owned, model-store-separate observability sink."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(PROBE_SCHEMA)
        self.conn.commit()
        self.write_failures = 0

    def _seq(self, table: str, run_id: str) -> int:
        row = self.conn.execute(
            f"SELECT COALESCE(MAX(seq),0)+1 AS s FROM {table} WHERE run_id=?", (run_id,)).fetchone()
        return int(row["s"])

    def register(self, run_id: str, **cols: Any) -> None:
        keys = ["run_id"] + list(cols.keys())
        vals = [run_id] + [cols[k] for k in cols]
        ph = ",".join("?" * len(keys))
        try:
            self.conn.execute(
                f"INSERT OR REPLACE INTO run_config ({','.join(keys)}) VALUES ({ph})", vals)
            self.conn.commit()
        except sqlite3.Error:
            self.write_failures += 1

    def log_api(self, run_id: str, turn_id: int, step_id: int, action: str,
                source_stamp: str, request: dict, response: Optional[dict],
                status_code: Optional[int], ts: str) -> None:
        """Capture one HTTP round-trip. response is the full raw body (incl.
        frame grids) — the offline-replay source; an orphan row (response NULL)
        is a caught HTTP failure."""
        r = response or {}
        frame_received = 1 if r.get("frame") else 0
        try:
            self.conn.execute(
                "INSERT OR REPLACE INTO api_log (run_id, turn_id, step_id, action, source_stamp, "
                "request_json, response_json, status_code, game_id, card_id, guid, score, "
                "levels_completed, state, frame_received, ts) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, turn_id, step_id, action, source_stamp, json.dumps(request),
                 json.dumps(response) if response is not None else None, status_code,
                 r.get("game_id"), r.get("card_id"), r.get("guid"), r.get("score"),
                 r.get("levels_completed"), r.get("state"), frame_received, ts))
            self.conn.commit()
        except sqlite3.Error:
            self.write_failures += 1

    def log_scorecard(self, run_id: str, turn_id: int, card_id: str, game_id: str,
                      scorecard: dict, captured_at: str) -> None:
        try:
            self.conn.execute(
                "INSERT INTO scorecards (run_id, seq, turn_id, card_id, game_id, scorecard_json, "
                "captured_at) VALUES (?,?,?,?,?,?,?)",
                (run_id, self._seq("scorecards", run_id), turn_id, card_id, game_id,
                 json.dumps(scorecard), captured_at))
            self.conn.commit()
        except sqlite3.Error:
            self.write_failures += 1

    def log_llm_call(self, run_id: str, turn_id: int, organ: str, **cols: Any) -> None:
        keys = ["run_id", "seq", "turn_id", "organ"] + list(cols.keys())
        vals = [run_id, self._seq("llm_calls", run_id), turn_id, organ] + list(cols.values())
        ph = ",".join("?" * len(keys))
        try:
            self.conn.execute(f"INSERT INTO llm_calls ({','.join(keys)}) VALUES ({ph})", vals)
            self.conn.commit()
        except sqlite3.Error:
            self.write_failures += 1

    def log_startup(self, run_id: str, image_receipt_ok: Optional[bool], signal_vocab: dict,
                    action_interface: dict) -> None:
        """image_receipt_ok is tri-state: None = no vision path in use (the
        check is not applicable); 1/0 = the round-trip passed/failed."""
        try:
            self.conn.execute(
                "INSERT OR REPLACE INTO startup_probe (run_id, image_receipt_ok, signal_vocab_json, "
                "action_interface_json) VALUES (?,?,?,?)",
                (run_id, None if image_receipt_ok is None else (1 if image_receipt_ok else 0),
                 json.dumps(signal_vocab), json.dumps(action_interface)))
            self.conn.commit()
        except sqlite3.Error:
            self.write_failures += 1

    def finish(self, run_id: str, ended_at: str) -> None:
        try:
            self.conn.execute("UPDATE run_config SET ended_at=? WHERE run_id=?", (ended_at, run_id))
            self.conn.commit()
        except sqlite3.Error:
            self.write_failures += 1

    def close(self) -> None:
        try:
            self.conn.commit()
        finally:
            self.conn.close()
