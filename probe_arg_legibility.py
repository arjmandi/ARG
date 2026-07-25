#!/usr/bin/env python3
"""probe_arg_legibility — the Q11 legibility harness + run-validity verdict.

Read-only inputs, but WRITES the verdict to arg_probe.run_validity (its own
table, never the model store). Checks the offline-checkable subset of Q11: R9
per-beat render ceiling, drift_ref stamped every beat, api↔Log agreement,
startup-probe pass, shadow byte-identity where captured. A run with an R9
breach, a silent-degrade, or a WER-floor breach is INVALID for attribution.

Usage: uv run python probe_arg_legibility.py [--db arg_state.db] [--probe arg_probe.db] [--run RUN]
"""
import argparse
import json
import sqlite3
from typing import Optional

from agents.arg import config


def _ro(db: str) -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def verify(db: str, probe: str, run: Optional[str] = None) -> dict:
    m = _ro(db)
    if not run:
        r = m.execute("SELECT run_id FROM run ORDER BY started_at DESC LIMIT 1").fetchone()
        run = r["run_id"] if r else None
    if not run:
        return {"verdict": "NO_RUN"}
    turns = m.execute("SELECT turn_id, action, render_tokens, drift_ref FROM turn_record WHERE run_id=? "
                      "ORDER BY turn_id", (run,)).fetchall()
    r9_breaches = sum(1 for t in turns if t["render_tokens"] > config.B_RENDER)
    silent_degrade = sum(1 for t in turns if t["drift_ref"] is None and t["action"] != "RESET")

    p = _ro(probe)
    # R9 is per LLM CALL (§2.5 R9): every rendered view an organ received
    r9_breaches += sum(1 for r in p.execute(
        "SELECT render_tokens FROM llm_calls WHERE run_id=?", (run,))
        if (r["render_tokens"] or 0) > config.B_RENDER)
    startup = p.execute("SELECT image_receipt_ok FROM startup_probe WHERE run_id=?", (run,)).fetchone()
    # tri-state: NULL = no vision path in use (not applicable → pass); 0 = a
    # vision path failed its round-trip (fail); 1 = passed
    startup_ok = bool(startup) and (startup["image_receipt_ok"] is None
                                    or startup["image_receipt_ok"] == 1)
    # shadow byte-identity: for turns with both shadow_flag 0 and 1 captures, views must match
    shadow_ok = True
    rc = p.execute("SELECT turn_id, zone_tier, shadow_flag, view_bytes FROM render_capture WHERE run_id=?",
                   (run,)).fetchall()
    by = {}
    for r in rc:
        by.setdefault((r["turn_id"], r["zone_tier"]), {})[r["shadow_flag"]] = r["view_bytes"]
    for k, v in by.items():
        if 0 in v and 1 in v and v[0] != v[1]:
            shadow_ok = False
            break
    # §2.1 WER floor, per organ (pre-registered in config): a breach
    # disqualifies the run from architecture attribution. Applies only once an
    # organ has ≥ WER_MIN_OPS write ops (tiny-sample noise guard).
    rej_by = {r["organ"]: r["n"] for r in m.execute(
        "SELECT organ, COUNT(*) n FROM write_reject WHERE run_id=? GROUP BY organ", (run,))}
    acc_by = {r["organ"].upper(): (r["a"] or 0) for r in p.execute(
        "SELECT organ, SUM(ops_accepted) a FROM llm_calls WHERE run_id=? GROUP BY organ", (run,))}
    wer_floor_ok = True
    wer_by_organ = {}
    for organ in set(rej_by) | set(acc_by):
        n_ops = rej_by.get(organ, 0) + acc_by.get(organ, 0)
        if n_ops >= config.WER_MIN_OPS:
            w = rej_by.get(organ, 0) / n_ops
            wer_by_organ[organ] = round(w, 3)
            if w > config.WER_FLOOR:
                wer_floor_ok = False

    # ZCR uniform-failure (§2.5 diagnosis 1): every salted zone below the floor
    # = adapter/transport defect → Q11-class, run invalid for attribution.
    # Floors apply AFTER the pre-registered warmup (§2.4.7): each organ's first
    # ZCR_WARMUP_EPOCHS salted calls are excluded from the rate.
    zcr_rows = p.execute("SELECT zone_tier, AVG(echoed) r, COUNT(*) n FROM zcr_echo "
                         "WHERE run_id=? AND call_idx > ? GROUP BY zone_tier",
                         (run, config.ZCR_WARMUP_EPOCHS)).fetchall()
    if not zcr_rows:   # short run: everything inside warmup → fall back to all rows
        zcr_rows = p.execute("SELECT zone_tier, AVG(echoed) r, COUNT(*) n FROM zcr_echo "
                             "WHERE run_id=? GROUP BY zone_tier", (run,)).fetchall()
    zcr_rates = {r["zone_tier"]: round(r["r"], 3) for r in zcr_rows}
    zcr_uniform_fail = 1 if (zcr_rows and all(r["r"] < config.ZCR_FLOOR for r in zcr_rows)) else 0

    verdict = "VALID"
    if r9_breaches > 0 or silent_degrade > 0 or not startup_ok or not shadow_ok \
            or zcr_uniform_fail or not wer_floor_ok:
        verdict = "INVALID"
    detail = {"r9_breaches": r9_breaches, "silent_degrade": silent_degrade,
              "startup_ok": startup_ok, "shadow_ok": shadow_ok, "beats": len(turns),
              "zcr_rates": zcr_rates, "zcr_uniform_fail": bool(zcr_uniform_fail),
              "wer_by_organ": wer_by_organ, "wer_floor_ok": wer_floor_ok}

    # persist to the probe store (write-separate; never the model store)
    try:
        w = sqlite3.connect(probe)
        w.execute(
            "INSERT OR REPLACE INTO run_validity (run_id, verdict, r9_breaches, silent_degrade_count, "
            "wer_floor_ok, zcr_uniform_fail, detail_json) VALUES (?,?,?,?,?,?,?)",
            (run, verdict, r9_breaches, silent_degrade, 1 if wer_floor_ok else 0,
             zcr_uniform_fail, json.dumps(detail)))
        w.commit(); w.close()
    except sqlite3.Error as e:
        detail["persist_error"] = str(e)

    print(f"=== ARG legibility — run {run[:24]} ===")
    print(f"  R9 breaches: {r9_breaches} | silent-degrade: {silent_degrade} | "
          f"startup_ok: {startup_ok} | shadow_ok: {shadow_ok}")
    print(f"  VERDICT: {verdict}" + ("" if verdict == "VALID" else "  (excluded from attribution)"))
    return {"verdict": verdict, **detail}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="arg_state.db")
    ap.add_argument("--probe", default="arg_probe.db")
    ap.add_argument("--run", default=None)
    a = ap.parse_args()
    verify(a.db, a.probe, a.run)


if __name__ == "__main__":
    main()
