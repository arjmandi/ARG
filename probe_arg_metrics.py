#!/usr/bin/env python3
"""probe_arg_metrics — the §8 metric table over ARG's Log.

Read-only. Every figure is computed from mechanically-stamped rows (turn_record,
consequence_record, status_transition, commitment_step, step_premise,
goal_binding, relevance_edge, write_reject, llm_calls). Definitions follow
docs_arg_design.md §8; where a build-1 approximation is made it is noted inline.

Usage: uv run python probe_arg_metrics.py [--db arg_state.db] [--probe arg_probe.db] [--run RUN]
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


def _latest_status_count(m, run, kind, status) -> int:
    return m.execute(
        "SELECT COUNT(DISTINCT entity_id) n FROM status_transition st WHERE run_id=? AND "
        "entity_kind=? AND to_status=? AND st.seq=(SELECT MAX(seq) FROM status_transition s2 "
        "WHERE s2.run_id=st.run_id AND s2.entity_id=st.entity_id AND s2.entity_kind=st.entity_kind)",
        (run, kind, status)).fetchone()["n"]


def _latest_goal_status(m, run, goal_id) -> Optional[str]:
    row = m.execute(
        "SELECT to_status s FROM status_transition WHERE run_id=? AND entity_kind='GOAL' "
        "AND entity_id=? ORDER BY seq DESC LIMIT 1", (run, goal_id)).fetchone()
    return row["s"] if row else None


def _slope(points: list) -> Optional[float]:
    """Least-squares slope of (x,y) points; None under 3 points."""
    n = len(points)
    if n < 3:
        return None
    sx = sum(p[0] for p in points); sy = sum(p[1] for p in points)
    sxx = sum(p[0] * p[0] for p in points); sxy = sum(p[0] * p[1] for p in points)
    den = n * sxx - sx * sx
    return round((n * sxy - sx * sy) / den, 4) if den else None


def compute(db: str, probe: str, run: Optional[str] = None) -> dict:
    m = _ro(db); p = _ro(probe)
    if not run:
        r = m.execute("SELECT run_id FROM run ORDER BY started_at DESC LIMIT 1").fetchone()
        run = r["run_id"] if r else None
    if not run:
        return {}
    mt: dict = {"run": run}
    turns = [dict(r) for r in m.execute(
        "SELECT turn_id, action, target_ref, commitment_step_id, shadow_step_id, drift_ref, "
        "source_stamp, render_tokens, match, params_json FROM turn_record WHERE run_id=? "
        "ORDER BY turn_id", (run,))]
    acted = [t for t in turns if t["action"] != "RESET"]
    mt["actions"] = len(turns)
    mt["completions"] = m.execute("SELECT COALESCE(MAX(level_counter),0) c FROM turn_record "
                                  "WHERE run_id=?", (run,)).fetchone()["c"]
    mt["decision_mix"] = {r["source_stamp"]: r["n"] for r in m.execute(
        "SELECT source_stamp, COUNT(*) n FROM turn_record WHERE run_id=? GROUP BY source_stamp", (run,))}

    # ---- grounding ----
    mt["referents"] = m.execute("SELECT COUNT(DISTINCT ref_id) n FROM referent WHERE run_id=?",
                                (run,)).fetchone()["n"]
    bound_refs = {r["ref_id"] for r in m.execute(
        "SELECT DISTINCT ref_id FROM goal_binding WHERE run_id=?", (run,))}
    mt["goal_bound_referents"] = len(bound_refs)

    def rung_of(ref):
        r = m.execute("SELECT to_status FROM status_transition WHERE run_id=? AND "
                      "entity_kind='REFERENT_RUNG' AND entity_id=? ORDER BY seq DESC LIMIT 1",
                      (run, ref)).fetchone()
        return r["to_status"] if r else "ANCHORED"
    # RGR (§8): CHARACTERIZED ("TESTED+") share among GOAL-BOUND referents
    mt["RGR"] = round(sum(1 for r in bound_refs if rung_of(r) == "CHARACTERIZED")
                      / len(bound_refs), 3) if bound_refs else 0.0
    rung = {}
    for r in m.execute(
            "SELECT to_status s, COUNT(DISTINCT entity_id) n FROM status_transition st WHERE run_id=? "
            "AND entity_kind='REFERENT_RUNG' AND st.seq=(SELECT MAX(seq) FROM status_transition s2 "
            "WHERE s2.run_id=st.run_id AND s2.entity_id=st.entity_id AND s2.entity_kind='REFERENT_RUNG') "
            "GROUP BY to_status", (run,)):
        rung[r["s"]] = r["n"]
    mt["rung_distribution"] = rung
    total_rung = sum(rung.values()) or 1
    mt["grounding_rate_all"] = round(
        (rung.get("ENGAGED", 0) + rung.get("CHARACTERIZED", 0)) / total_rung, 3)

    # ---- agenda / drift (reference step per beat via drift_ref, §8) ----
    steps_written = m.execute("SELECT COUNT(*) n FROM commitment_step WHERE run_id=?",
                              (run,)).fetchone()["n"]
    steps_consumed = _latest_status_count(m, run, "COMMITMENT_STEP", "CONSUMED")
    mt["steps_written"] = steps_written
    mt["steps_consumed"] = steps_consumed
    mt["ICR"] = round(steps_consumed / steps_written, 3) if steps_written else None
    step_info = {r["step_id"]: (r["target_ref"], r["action"]) for r in m.execute(
        "SELECT step_id, target_ref, action FROM commitment_step WHERE run_id=?", (run,))}
    n_ref = bind_miss = abandon = 0
    for t in acted:
        ref_step = None
        if t["commitment_step_id"]:
            ref_step = step_info.get(t["commitment_step_id"])
        elif t["shadow_step_id"]:
            parts = t["shadow_step_id"].split("|")
            if len(parts) >= 3:
                ref_step = (None if parts[2] == "-" else parts[2], parts[1])
        if ref_step is None:
            continue
        n_ref += 1
        st_target, st_action = ref_step
        # Operational GDS taxonomy (§8; the join seam exists only where an
        # AIMED emission lands somewhere):
        #   bind    = join loss at the emission/landing seam — an aimed
        #             emission on the plan's action landed on the wrong
        #             referent (substitution-class) or on background (dangling)
        #   abandon = commitment loss — the beat did not follow the reference
        #             step (different action, or a different deliberate target)
        #   aligned = faithful execution; untargeted step actions have no aim
        #             parameter, so landing is not a join surface for them
        aimed = bool(t["params_json"])
        live = bool(t["commitment_step_id"])
        on_plan_action = (not st_action) or t["action"] == st_action
        if on_plan_action and st_target and aimed and t["target_ref"] != st_target:
            bind_miss += 1
        elif live:
            pass                  # faithful execution of the live step (aligned)
        elif not on_plan_action or (st_target and (t["target_ref"] or None) != st_target):
            abandon += 1          # shadow plan not followed (A-dimension loss)
    mt["drift_ref_beats"] = n_ref
    mt["gds_bind"] = round(bind_miss / n_ref, 3) if n_ref else None
    mt["gds_abandon"] = round(abandon / n_ref, 3) if n_ref else None
    mt["drift_total"] = round((bind_miss + abandon) / n_ref, 3) if n_ref else None
    # GA (build-1 approximation: binding closure = union of goal bindings)
    mt["GA"] = round(sum(1 for t in acted if t["target_ref"] in bound_refs) / len(acted), 3) \
        if acted and bound_refs else None

    # ---- lifecycle rates ----
    n100 = max(len(acted), 1) / 100.0
    mt["FBR"] = round(m.execute(
        "SELECT COUNT(*) n FROM status_transition WHERE run_id=? AND entity_kind='RULE' "
        "AND to_status='DEMOTED'", (run,)).fetchone()["n"] / n100, 3)
    accepts = m.execute("SELECT COUNT(*) n FROM status_transition WHERE run_id=? AND "
                        "entity_kind='GOAL' AND to_status='ACCEPTED'", (run,)).fetchone()["n"]
    reopens = m.execute("SELECT COUNT(*) n FROM status_transition WHERE run_id=? AND "
                        "entity_kind='GOAL' AND to_status='REOPENED'", (run,)).fetchone()["n"]
    mt["FCR"] = round(reopens / accepts, 3) if accepts else None
    mt["FSN"] = round(m.execute(
        "SELECT COUNT(*) n FROM status_transition WHERE run_id=? AND entity_kind='REFERENT_FISSION'",
        (run,)).fetchone()["n"] / n100, 3)
    # APR: actions whose step chains to a goal terminally REJECTED NEVER_VALIDATED
    nv_goals = {r["entity_id"] for r in m.execute(
        "SELECT DISTINCT entity_id FROM status_transition WHERE run_id=? AND entity_kind='GOAL' "
        "AND to_status='REJECTED' AND reason='NEVER_VALIDATED'", (run,))}
    step_goal = {r["step_id"]: r["goal_id"] for r in m.execute(
        "SELECT cs.step_id, c.goal_id FROM commitment_step cs JOIN commitment c ON c.run_id=cs.run_id "
        "AND c.commit_id=cs.commit_id AND c.version=cs.commit_version WHERE cs.run_id=?", (run,))}
    mt["APR"] = round(sum(1 for t in acted if step_goal.get(t["commitment_step_id"]) in nv_goals)
                      / max(len(acted), 1), 3) if acted else None
    # DTL: goal-bind turn (relevance REFERENT edge) → first interaction
    dtl_samples = []
    for r in m.execute("SELECT target_id, MIN(turn_id) t FROM relevance_edge WHERE run_id=? AND "
                       "target_kind='REFERENT' GROUP BY target_id", (run,)):
        first = m.execute("SELECT MIN(turn_id) t FROM consequence_record WHERE run_id=? AND "
                          "target_ref=? AND turn_id>=?", (run, r["target_id"], r["t"])).fetchone()["t"]
        if first is not None:
            dtl_samples.append(first - r["t"])
    mt["DTL"] = round(sum(dtl_samples) / len(dtl_samples), 2) if dtl_samples else None
    # SCL: premise demotion → step BLOCKED latency
    scl_samples = []
    for b in m.execute("SELECT entity_id, turn_id FROM status_transition WHERE run_id=? AND "
                       "entity_kind='COMMITMENT_STEP' AND to_status='BLOCKED' AND "
                       "reason='premise demoted'", (run,)):
        dem = m.execute(
            "SELECT MAX(st.turn_id) t FROM step_premise sp JOIN status_transition st ON "
            "st.run_id=sp.run_id AND st.entity_kind='RULE' AND st.entity_id=sp.member_id AND "
            "st.to_status='DEMOTED' AND st.turn_id<=? WHERE sp.run_id=? AND sp.step_id=? AND "
            "sp.member_kind='RULE'", (b["turn_id"], run, b["entity_id"])).fetchone()["t"]
        if dem is not None:
            scl_samples.append(b["turn_id"] - dem)
    mt["SCL"] = round(sum(scl_samples) / len(scl_samples), 2) if scl_samples else None

    # ---- write path (per organ; WER = rejected / (accepted + rejected)) ----
    rej_by = {r["organ"]: r["n"] for r in m.execute(
        "SELECT organ, COUNT(*) n FROM write_reject WHERE run_id=? GROUP BY organ", (run,))}
    acc_by = {r["organ"].upper(): (r["a"] or 0) for r in p.execute(
        "SELECT organ, SUM(ops_accepted) a FROM llm_calls WHERE run_id=? GROUP BY organ", (run,))}
    wer_per = {}
    for organ in ("OBSERVER", "SURVEYOR", "ACTUATOR"):
        rj, ac = rej_by.get(organ, 0), acc_by.get(organ, 0)
        wer_per[organ] = round(rj / (rj + ac), 3) if (rj + ac) else None
    mt["wer_per_organ"] = wer_per
    tot_rej = sum(rej_by.values()); tot_acc = sum(acc_by.values())
    mt["WER"] = round(tot_rej / (tot_rej + tot_acc), 3) if (tot_rej + tot_acc) else 0.0
    mt["write_rejects"] = tot_rej
    # SRR: gate-rejected agenda revisions per Surveyor epoch
    srr_rej = m.execute("SELECT COUNT(*) n FROM write_reject WHERE run_id=? AND organ='SURVEYOR' "
                        "AND op_type IN ('ABORT_STEP','RANK_TIEBREAK')", (run,)).fetchone()["n"]
    epochs = p.execute("SELECT COUNT(*) n FROM llm_calls WHERE run_id=? AND organ='surveyor'",
                       (run,)).fetchone()["n"]
    mt["SRR"] = round(srr_rej / epochs, 3) if epochs else None
    # ECR: R8/R5 validator catches per 100 LLM outputs
    llm_n = p.execute("SELECT COUNT(*) n FROM llm_calls WHERE run_id=?", (run,)).fetchone()["n"]
    ecr_n = m.execute("SELECT COUNT(*) n FROM write_reject WHERE run_id=? AND violation_class IN "
                      "('UNCONTAINED_PARAM','OUT_OF_SCHEMA','DANGLING_REF')", (run,)).fetchone()["n"]
    mt["ECR"] = round(ecr_n / (llm_n / 100.0), 3) if llm_n else None
    # DPR (§2.1): proposals dropped after retry exhaustion / total write ops —
    # a retry_count≥1 write_reject row IS the drop marker, any organ
    dropped = m.execute("SELECT COUNT(*) n FROM write_reject WHERE run_id=? AND retry_count>=1",
                        (run,)).fetchone()["n"]
    total_ops = tot_rej + tot_acc
    mt["DPR"] = round(dropped / total_ops, 3) if total_ops else None

    # ---- rules / goals ----
    mt["rules_tested"] = _latest_status_count(m, run, "RULE", "TESTED")
    goals = {}
    for r in m.execute(
            "SELECT to_status s, COUNT(DISTINCT entity_id) n FROM status_transition st WHERE run_id=? "
            "AND entity_kind='GOAL' AND st.seq=(SELECT MAX(seq) FROM status_transition s2 WHERE "
            "s2.run_id=st.run_id AND s2.entity_id=st.entity_id AND s2.entity_kind='GOAL') "
            "GROUP BY to_status", (run,)):
        goals[r["s"]] = r["n"]
    mt["goal_status"] = goals

    # ---- chain (G1–G3): recognizer stamps, milestones, verified edges ----
    # tolerant of pre-chain DBs (batches 1–3 lack these tables)
    def _maybe(sql, args=()):
        try:
            return m.execute(sql, args).fetchone()["n"]
        except sqlite3.OperationalError:
            return None
    mt["deficit_stamps"] = _maybe(
        "SELECT COUNT(*) n FROM deficit_stamp WHERE run_id=?", (run,))
    mt["deficit_goals"] = _maybe(
        "SELECT COUNT(DISTINCT goal_id) n FROM deficit_stamp WHERE run_id=?", (run,))
    mt["edges_verified"] = _maybe(
        "SELECT COUNT(*) n FROM goal_edge WHERE run_id=? AND verified=1", (run,))
    mt["edges_unverified"] = _maybe(
        "SELECT COUNT(*) n FROM goal_edge WHERE run_id=? AND verified=0", (run,))
    ms = [r["goal_id"] for r in m.execute(
        "SELECT DISTINCT goal_id FROM goal WHERE run_id=? AND provenance='DEFICIT'", (run,))]
    mt["milestone_goals"] = len(ms)
    mt["milestone_accepted"] = sum(
        1 for g in ms if _latest_goal_status(m, run, g) == "ACCEPTED")
    mt["milestone_conversion"] = round(mt["milestone_accepted"] / len(ms), 3) if ms else None

    # ---- render/token compliance (R9 per beat AND per LLM call) ----
    max_turn_rt = m.execute("SELECT COALESCE(MAX(render_tokens),0) x FROM turn_record WHERE run_id=?",
                            (run,)).fetchone()["x"]
    max_call_rt = p.execute("SELECT COALESCE(MAX(render_tokens),0) x FROM llm_calls WHERE run_id=?",
                            (run,)).fetchone()["x"]
    mt["max_render_tokens"] = max(max_turn_rt, max_call_rt)
    mt["render_ceiling_B"] = config.B_RENDER
    mt["R9_ok"] = mt["max_render_tokens"] <= config.B_RENDER
    llm = p.execute("SELECT COUNT(*) n, COALESCE(SUM(prompt_tokens),0) pt, "
                    "COALESCE(SUM(completion_tokens),0) ct FROM llm_calls WHERE run_id=?",
                    (run,)).fetchone()
    mt["llm_calls"] = llm["n"]
    mt["llm_tokens"] = llm["pt"] + llm["ct"]
    pts = [(r["turn_id"], (r["prompt_tokens"] or 0) + (r["completion_tokens"] or 0))
           for r in p.execute("SELECT turn_id, prompt_tokens, completion_tokens FROM llm_calls "
                              "WHERE run_id=? ORDER BY turn_id", (run,))]
    mt["tokens_vs_beat_slope"] = _slope(pts)

    # ---- §8 length-stratified readout (anti-rot bins) ----
    bins: dict = {}
    for lo, hi, name in ((1, 50, "1-50"), (51, 150, "51-150"), (151, 10 ** 9, "151+")):
        seg = [t for t in acted if lo <= t["turn_id"] <= hi]
        if not seg:
            bins[name] = None
            continue
        withm = [t for t in seg if t["match"] is not None]
        step_beats = [t for t in withm if t["commitment_step_id"]]
        bins[name] = {
            "n": len(seg),
            "decision_accuracy": round(sum(1 for t in step_beats if t["match"] == 1)
                                       / len(step_beats), 3) if step_beats else None,
            "match_rate": round(sum(1 for t in withm if t["match"] == 1)
                                / len(withm), 3) if withm else None,
            "GA": round(sum(1 for t in seg if t["target_ref"] in bound_refs)
                        / len(seg), 3) if bound_refs else None,
        }
    mt["bins"] = bins
    return mt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="arg_state.db")
    ap.add_argument("--probe", default="arg_probe.db")
    ap.add_argument("--run", default=None)
    a = ap.parse_args()
    print(json.dumps(compute(a.db, a.probe, a.run), indent=1))


if __name__ == "__main__":
    main()
