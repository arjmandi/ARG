#!/usr/bin/env python3
"""probe_arg_hrt — Hop Reliability Table for each place the LLM is necessary.

For each organ hop: ingest-rejection rate (write_reject by organ / llm_calls by
organ) and, for the Observer-BIND hop, fission events per 100 binds (upper-bound
proxy). Read-only. Usage: uv run python probe_arg_hrt.py [--db ...] [--probe ...]
"""
import argparse
import sqlite3


def _ro(db):
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True); c.row_factory = sqlite3.Row; return c


def hrt(db="arg_state.db", probe="arg_probe.db", run=None) -> dict:
    m = _ro(db); p = _ro(probe)
    if not run:
        r = m.execute("SELECT run_id FROM run ORDER BY started_at DESC LIMIT 1").fetchone()
        run = r["run_id"] if r else None
    if not run:
        return {}
    rows = {}
    for organ in ("OBSERVER", "SURVEYOR", "ACTUATOR"):
        rej = m.execute("SELECT COUNT(*) n FROM write_reject WHERE run_id=? AND organ=?",
                        (run, organ)).fetchone()["n"]
        calls = p.execute("SELECT COUNT(*) n FROM llm_calls WHERE run_id=? AND organ=?",
                          (run, organ.lower())).fetchone()["n"]
        rows[organ] = {"rejections": rej, "calls": calls,
                       "reject_rate": round(rej / calls, 3) if calls else None}
    binds = m.execute("SELECT COUNT(*) n FROM binding_record WHERE run_id=?", (run,)).fetchone()["n"]
    rows["OBSERVER"]["binds"] = binds
    # §8 HRT ground-truth column: predicted-delta mismatch rate of
    # ACTUATOR_LLM-stamped actions vs paired COMMITMENT_STEP-stamped actions —
    # the pre-registered falsified-if for the param-realization hop
    match_rate = {}
    for stamp in ("COMMITMENT_STEP", "ACTUATOR_LLM", "FALLBACK", "PROBE"):
        r = m.execute("SELECT COUNT(*) n, COALESCE(SUM(match=0),0) miss FROM turn_record "
                      "WHERE run_id=? AND source_stamp=? AND match IS NOT NULL",
                      (run, stamp)).fetchone()
        match_rate[stamp] = {"n": r["n"],
                             "mismatch_rate": round(r["miss"] / r["n"], 3) if r["n"] else None}
    rows["mismatch_by_stamp"] = match_rate
    a = match_rate["ACTUATOR_LLM"]["mismatch_rate"]
    c = match_rate["COMMITMENT_STEP"]["mismatch_rate"]
    rows["actuator_vs_step_mismatch_delta"] = round(a - c, 3) \
        if (a is not None and c is not None) else None
    print(f"=== ARG HRT — run {run[:24]} ===")
    for organ in ("OBSERVER", "SURVEYOR", "ACTUATOR"):
        d = rows[organ]
        print(f"  {organ}: calls={d['calls']} rejects={d['rejections']} rate={d['reject_rate']}")
    print(f"  mismatch by stamp: { {k: v['mismatch_rate'] for k, v in match_rate.items()} } "
          f"| actuator-vs-step delta: {rows['actuator_vs_step_mismatch_delta']}")
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="arg_state.db"); ap.add_argument("--probe", default="arg_probe.db")
    ap.add_argument("--run", default=None)
    a = ap.parse_args(); hrt(a.db, a.probe, a.run)
