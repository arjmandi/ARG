#!/usr/bin/env python3
"""probe_arg_health — Q13 meta-metric floor monitor over ARG's Log.

Reads the §8 metrics + the ZCR echo rates and prints a named diagnosis row per
breached floor: "write-path degradation", "render-budget breach", "revision
thrash", "low-grounding", "consumption rot" (zone-differential ZCR failure —
§2.5 diagnosis 2; the uniform failure is a Q11 matter handled by
probe_arg_legibility), and a positive token-vs-beat slope. Read-only.
Usage: uv run python probe_arg_health.py [--db ...] [--probe ...]
"""
import argparse
import sqlite3

from agents.arg import config
from probe_arg_metrics import compute

FLOORS = {"WER": ("write-path degradation", lambda v: v is not None and v > 0.25),
          "R9_ok": ("render-budget breach", lambda v: v is False),
          "RGR": ("low-grounding", lambda v: v is not None and v < 0.05),
          "SRR": ("revision thrash", lambda v: v is not None and v > 1.0),
          "tokens_vs_beat_slope": ("token growth (rot suspect)",
                                   lambda v: v is not None and v > 50.0)}


def zcr_zone_rates(probe: str, run: str) -> dict:
    """Post-warmup per-zone echo rates (§2.4.7: floors apply after the
    pre-registered warmup; falls back to all rows on short runs)."""
    try:
        c = sqlite3.connect(f"file:{probe}?mode=ro", uri=True)
        c.row_factory = sqlite3.Row
        rows = {r["zone_tier"]: round(r["r"], 3) for r in c.execute(
            "SELECT zone_tier, AVG(echoed) r FROM zcr_echo WHERE run_id=? AND call_idx > ? "
            "GROUP BY zone_tier", (run, config.ZCR_WARMUP_EPOCHS))}
        if not rows:
            rows = {r["zone_tier"]: round(r["r"], 3) for r in c.execute(
                "SELECT zone_tier, AVG(echoed) r FROM zcr_echo WHERE run_id=? GROUP BY zone_tier",
                (run,))}
        return rows
    except sqlite3.Error:
        return {}


def health(db="arg_state.db", probe="arg_probe.db", run=None) -> dict:
    m = compute(db, probe, run)
    diagnoses = []
    for key, (name, breached) in FLOORS.items():
        if key in m and breached(m[key]):
            diagnoses.append({"metric": key, "value": m[key], "diagnosis": name})
    # ZCR (§2.5): zone-differential failure = consumption rot (uniform failure
    # is Q11/legibility territory and invalidates the run there)
    rates = zcr_zone_rates(probe, m.get("run", "")) if m.get("run") else {}
    below = {z: r for z, r in rates.items() if r < config.ZCR_FLOOR}
    if rates and below and len(below) < len(rates):
        diagnoses.append({"metric": "ZCR", "value": rates, "diagnosis": "consumption rot"})
    print(f"=== ARG health — run {(m.get('run') or '?')[:24]} ===")
    if rates:
        print(f"  ZCR per-zone echo rates: {rates} (floor {config.ZCR_FLOOR})")
    if diagnoses:
        for d in diagnoses:
            print(f"  ✗ {d['diagnosis']}: {d['metric']}={d['value']}")
    else:
        print("  ✓ all pre-registered floors within bounds")
    return {"metrics": m, "diagnoses": diagnoses, "zcr_rates": rates}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="arg_state.db"); ap.add_argument("--probe", default="arg_probe.db")
    ap.add_argument("--run", default=None)
    a = ap.parse_args(); health(a.db, a.probe, a.run)
