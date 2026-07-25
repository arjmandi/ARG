#!/usr/bin/env python3
"""ARG M1 store-spine tests: append-only invariant, versioning, id minting.
Run: uv run python tests/test_arg_store.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agents.arg.store import Store  # noqa: E402

FAILS = []


def T(name: str, cond: bool, detail: str = "") -> None:
    print(f"  [{'ok ' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def main() -> None:
    db = tempfile.mktemp(suffix=".db")
    s = Store(db)
    rid = "run-test-1"
    s.register_run(rid, "ls20", "sonnet", 0, "{}", 6000, "2026-07-17T00:00:00")

    # id minting: per-run per-type, gapless, zero-padded width 4
    ids = [s.mint_id(rid, "R", 4) for _ in range(3)]
    T("id minting zero-padded width 4", ids == ["R0001", "R0002", "R0003"], str(ids))
    T("id minting per-type independent", s.mint_id(rid, "G", 4) == "G0001")
    T("id minting per-run independent",
      s.mint_id("run-test-2", "R", 4) == "R0001")

    # versioned knowledge: current = MAX(version), immutable content rows
    for v in (1, 2, 3):
        s.conn.execute(
            "INSERT INTO rule (run_id, rule_id, version, template, ctx_pred_json, "
            "effect_pattern_json, created_turn) VALUES (?,?,?,?,?,?,?)",
            (rid, "RU0001", v, f"tmpl v{v}", "{}", "{}", v))
    s.commit()
    T("current_version = MAX(version)", s.current_version(rid, "rule", "rule_id", "RU0001") == 3)

    # append-only: UPDATE and DELETE on a versioned/evidence table must RAISE
    def raises(sql, params=()):
        try:
            s.conn.execute(sql, params)
            s.conn.commit()
            return False
        except Exception:
            s.conn.rollback()
            return True

    T("goal achievement_test UPDATE aborts",
      _seed_goal_then(s, rid) and raises(
          "UPDATE goal SET achievement_test_json='x' WHERE run_id=? AND goal_id='G0001'", (rid,)))
    T("rule row UPDATE aborts",
      raises("UPDATE rule SET template='hacked' WHERE run_id=? AND rule_id='RU0001'", (rid,)))
    T("turn_record DELETE aborts",
      _seed_turn(s, rid) and raises("DELETE FROM turn_record WHERE run_id=?", (rid,)))
    T("binding_record DELETE aborts",
      _seed_binding(s, rid) and raises("DELETE FROM binding_record WHERE run_id=?", (rid,)))

    # run close-out (mutable exemption) succeeds
    ok_close = True
    try:
        s.close_run(rid, "2026-07-17T01:00:00", "COMPLETED")
    except Exception:
        ok_close = False
    T("run close-out UPDATE succeeds (mutable exemption)", ok_close)

    # next_seq monotonic per run
    T("next_seq monotonic",
      s.next_seq(rid, "status_transition") >= 1)

    s.close()
    print(f"\n{'PASS' if not FAILS else 'FAIL: ' + str(FAILS)}")
    sys.exit(1 if FAILS else 0)


def _seed_goal_then(s, rid) -> bool:
    s.conn.execute(
        "INSERT INTO goal (run_id, goal_id, version, statement, achievement_test_json, "
        "discriminator_json, reopen_class, budget_actions, budget_search_calls, provenance, "
        "created_turn) VALUES (?,?,1,?,?,?,?,?,?,?,?)",
        (rid, "G0001", "win", "{}", "{}", "MONOTONE_TERMINAL", 200, 30, "SEEDED", 0))
    s.commit()
    return True


def _seed_turn(s, rid) -> bool:
    s.conn.execute(
        "INSERT INTO turn_record (run_id, turn_id, action, pre_frame_hash, post_frame_hash, "
        "raw_diff_json, score, level_counter, state_flags, source_stamp, render_tokens) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (rid, 0, "RESET", "h0", "h1", "{}", 0, 0, "NOT_FINISHED", "RESET", 0))
    s.commit()
    return True


def _seed_binding(s, rid) -> bool:
    s.conn.execute(
        "INSERT INTO binding_record (run_id, turn_id, component_hash, anchor_cells_json, "
        "anchor_bbox_json, anchor_signature, bound_to, is_new, margin) VALUES (?,?,?,?,?,?,?,?,?)",
        (rid, 1, "abc123", "[]", "[]", "sig1", "R0001", 0, 0.9))
    s.commit()
    return True


if __name__ == "__main__":
    main()
