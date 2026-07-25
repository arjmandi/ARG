"""The Executive — deterministic disposal (build plan §4).

"The LLM proposes, the Executive disposes": no LLM output mutates the store
directly, and every state transition is executed here against invariants the
LLM cannot forge. Built up milestone by milestone; M1 delivers the identity /
re-identification machinery (the composite-margin bipartite bind).
"""

from __future__ import annotations

import hashlib
import json
from typing import Optional

from . import config
from . import predicates
from . import pather
from .adapter import Component
from .store import Store

RUNG_ORDER = {"ANCHORED": 1, "ENGAGED": 2, "CHARACTERIZED": 3}


def frame_hash(grid: list) -> str:
    return hashlib.sha1(json.dumps(grid, separators=(",", ":")).encode()).hexdigest()[:16]

# re-identification decisions (build plan §2.6, §11 margin resolution)
AUTO_BIND = "AUTO_BIND"          # margin ≥ τ_auto → Executive binds, 0 LLM calls
AMBIGUOUS_BIND = "AMBIGUOUS"     # τ ≤ margin < τ_auto → residue, goes to Observer
NEW_WITH_SAMEAS = "NEW_SAMEAS"   # margin < τ but a plausible candidate → NEW + same_as HYPOTHESIS
NEW_FRESH = "NEW_FRESH"          # no plausible candidate → NEW


def bbox_iou(a: tuple, b: tuple) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    ix0, iy0 = max(ax0, bx0), max(ay0, by0)
    ix1, iy1 = min(ax1, bx1), min(ay1, by1)
    if ix1 < ix0 or iy1 < iy0:
        return 0.0
    inter = (ix1 - ix0 + 1) * (iy1 - iy0 + 1)
    area_a = (ax1 - ax0 + 1) * (ay1 - ay0 + 1)
    area_b = (bx1 - bx0 + 1) * (by1 - by0 + 1)
    union = area_a + area_b - inter
    return inter / union if union else 0.0


def bind_score(comp: Component, cand: dict) -> float:
    """Composite similarity of an observed component to a candidate referent
    (build plan §3/§11): 0.5·[sig==] + 0.3·bbox_IoU + 0.2·(1 − min(L1/8, 1))."""
    sig_eq = 1.0 if comp.signature == cand["signature"] else 0.0
    iou = bbox_iou(comp.bbox, tuple(cand["bbox"]))
    ccx, ccy = cand["centroid"]
    l1 = abs(comp.centroid[0] - ccx) + abs(comp.centroid[1] - ccy)
    cent = 1.0 - min(l1 / 8.0, 1.0)
    return 0.5 * sig_eq + 0.3 * iou + 0.2 * cent


def reidentify(comp: Component, candidates: list) -> dict:
    """Forced-choice re-identification against Executive-proposed candidates.
    Returns the routing decision + bound_to/runner_up/margin — the LLM never
    invents an anchor; below τ the Executive mints NEW + a testable same_as
    HYPOTHESIS instead of a destructive union."""
    if not candidates:
        return {"decision": NEW_FRESH, "bound_to": None, "runner_up": None,
                "margin": 1.0, "is_new": True, "same_as": None}
    scored = sorted(((bind_score(comp, c), c) for c in candidates), key=lambda t: -t[0])
    s1, c1 = scored[0]
    s2 = scored[1][0] if len(scored) > 1 else 0.0
    runner = scored[1][1]["ref_id"] if len(scored) > 1 else None
    margin = round(s1 - s2, 6)
    if margin >= config.TAU:
        decision = AUTO_BIND if margin >= config.TAU_AUTO else AMBIGUOUS_BIND
        return {"decision": decision, "bound_to": c1["ref_id"], "runner_up": runner,
                "margin": margin, "is_new": False, "same_as": None}
    # below τ: never a destructive merge — mint NEW + same_as HYPOTHESIS to the best cand
    return {"decision": NEW_WITH_SAMEAS, "bound_to": None, "runner_up": c1["ref_id"],
            "margin": margin, "is_new": True, "same_as": c1["ref_id"]}


class Executive:
    """Holds the store + adapter + run scope; owns every deterministic transition."""

    def __init__(self, store: Store, adapter, run_id: str) -> None:
        self.store = store
        self.adapter = adapter
        self.run_id = run_id
        # tool seam (cold-start delta 3): targetedness comes from descriptors,
        # never from string-matching action names above the adapter
        self._targeted = (set(adapter.targeted_actions())
                          if hasattr(adapter, "targeted_actions") else set())

    # ---- referent / locator writes (Executive-only) ----
    def _write_gridregion_locator(self, comp: Component, turn_id: int) -> str:
        loc_id = self.store.mint_id(self.run_id, "L", config.ID_WIDTH)
        c = self.store.conn
        c.execute("INSERT INTO locator (run_id, locator_id, kind, created_turn) VALUES (?,?,?,?)",
                  (self.run_id, loc_id, "GridRegion", turn_id))
        x0, y0, x1, y1 = comp.bbox
        c.execute("INSERT INTO locator_gridregion (run_id, locator_id, cells_json, colors_json, "
                  "bbox_x0, bbox_y0, bbox_x1, bbox_y1) VALUES (?,?,?,?,?,?,?,?)",
                  (self.run_id, loc_id, json.dumps(sorted(comp.cells)), json.dumps([comp.color]),
                   x0, y0, x1, y1))
        return loc_id

    def mint_referent(self, comp: Component, turn_id: int,
                      provenance: str = "OBSERVER_BIND") -> str:
        """Create a new referent (version 1) anchored to a fresh GridRegion
        locator. kind is MACHINE-DERIVED from Locator provenance (never LLM)."""
        loc_id = self._write_gridregion_locator(comp, turn_id)
        ref_id = self.store.mint_id(self.run_id, "R", config.ID_WIDTH)
        self.store.conn.execute(
            "INSERT INTO referent (run_id, ref_id, version, kind, anchor_locator_id, "
            "signature, first_seen, provenance, created_turn) VALUES (?,?,1,?,?,?,?,?,?)",
            (self.run_id, ref_id, "percept-cluster", loc_id, comp.signature, turn_id,
             provenance, turn_id))
        # rung starts ANCHORED (§2.3)
        self._append_status(turn_id, "REFERENT_RUNG", ref_id, None, "ANCHORED", "minted")
        return ref_id

    def write_binding(self, turn_id: int, comp: Component, decision: dict) -> None:
        """Append the replayable BindingRecord for this beat's assignment."""
        self.store.conn.execute(
            "INSERT INTO binding_record (run_id, turn_id, component_hash, anchor_cells_json, "
            "anchor_bbox_json, anchor_signature, bound_to, is_new, runner_up, margin) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (self.run_id, turn_id, comp.chash, json.dumps(sorted(comp.cells)),
             json.dumps(list(comp.bbox)), comp.signature,
             decision.get("bound_to") or "", 1 if decision["is_new"] else 0,
             decision.get("runner_up"), decision["margin"]))

    def _append_status(self, turn_id: int, entity_kind: str, entity_id: str,
                       from_status: Optional[str], to_status: str, reason: str) -> None:
        seq = self.store.next_seq(self.run_id, "status_transition")
        self.store.conn.execute(
            "INSERT INTO status_transition (run_id, seq, turn_id, entity_kind, entity_id, "
            "from_status, to_status, reason) VALUES (?,?,?,?,?,?,?,?)",
            (self.run_id, seq, turn_id, entity_kind, entity_id, from_status, to_status, reason))

    def current_status(self, entity_kind: str, entity_id: str) -> Optional[str]:
        row = self.store.conn.execute(
            "SELECT to_status FROM status_transition WHERE run_id=? AND entity_kind=? "
            "AND entity_id=? ORDER BY seq DESC LIMIT 1",
            (self.run_id, entity_kind, entity_id)).fetchone()
        return row["to_status"] if row else None

    # ---- B2/B3/B4 beat helpers (M2) ----
    def write_consequence(self, turn_id: int, action: str, target_ref: Optional[str],
                          context_class_id: str, observed_delta: dict,
                          predicted_delta: Optional[dict] = None, match: Optional[bool] = None,
                          predictor_id: Optional[str] = None, predictor_kind: Optional[str] = None,
                          score_event: int = 0, level_event: int = 0, life_event: int = 0) -> None:
        seq = self.store.next_seq(self.run_id, "consequence_record")
        self.store.conn.execute(
            "INSERT INTO consequence_record (run_id, turn_id, seq, action, target_ref, "
            "context_class_id, predicted_delta_json, observed_delta_json, match, predictor_id, "
            "predictor_kind, score_event, level_event, life_event) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (self.run_id, turn_id, seq, action, target_ref, context_class_id,
             json.dumps(predicted_delta) if predicted_delta is not None else None,
             json.dumps(observed_delta),
             None if match is None else (1 if match else 0),
             predictor_id, predictor_kind, score_event, level_event, life_event))

    def stamp_target(self, action: str, params: dict) -> Optional[str]:
        """target_ref by CONTAINMENT of the actually-emitted coordinates — never
        copied from a commitment step (§4.3). A targeted tool's (x,y) → the
        MOST SPECIFIC (smallest) current referent whose anchor cells contain
        it: under nesting/overlap, first-by-id attribution stamped the
        enclosing board instead of the aimed component (tn36: 96 receipts
        mis-attributed R0089→R0004, starving the aimed rule and printing fake
        bind drift in every cell). Geometry still decides — nothing is copied
        from the step."""
        if action not in self._targeted or "x" not in params:
            return None
        x, y = int(params["x"]), int(params["y"])
        best = None
        for cand in self.current_referents_with_cells():
            if [x, y] in cand["cells"] or (x, y) in {tuple(p) for p in cand["cells"]}:
                if best is None or len(cand["cells"]) < len(best["cells"]):
                    best = cand
        return best["ref_id"] if best else None

    def current_referents_with_cells(self) -> list:
        c = self.store.conn
        rows = c.execute(
            "SELECT r.ref_id, g.cells_json, g.bbox_x0, g.bbox_y0, g.bbox_x1, g.bbox_y1, r.signature "
            "FROM referent r JOIN locator_gridregion g "
            "  ON g.run_id=r.run_id AND g.locator_id=r.anchor_locator_id "
            "WHERE r.run_id=? AND r.version=(SELECT MAX(version) FROM referent r2 "
            "  WHERE r2.run_id=r.run_id AND r2.ref_id=r.ref_id)", (self.run_id,)).fetchall()
        dormant = self._dormant_refs()
        out = []
        for row in rows:
            if row["ref_id"] in dormant:
                continue
            cells = json.loads(row["cells_json"])
            out.append({"ref_id": row["ref_id"], "cells": cells, "signature": row["signature"],
                        "bbox": (row["bbox_x0"], row["bbox_y0"], row["bbox_x1"], row["bbox_y1"])})
        return out

    def interaction_counts(self) -> dict:
        """consequence_record counts per action — the frontier ordering key."""
        rows = self.store.conn.execute(
            "SELECT action, COUNT(*) n FROM consequence_record WHERE run_id=? GROUP BY action",
            (self.run_id,)).fetchall()
        return {row["action"]: row["n"] for row in rows}

    def frontier_probe(self, available: list, turn_id: int) -> dict:
        """Z4 probe: cheapest untested action, salience-blind; a targeted tool
        aims at the LEAST-TRIED referent (fewest receipts, then smallest, then
        id) — untouched (referent × action) pairs first, never a pet target."""
        acts = [a for a in available if a != "RESET"]
        if not acts and hasattr(self.adapter, "tools"):
            acts = [t["name"] for t in self.adapter.tools()
                    if t["side"] == "actuate" and not t["targeted"]][:1]
        counts = self.interaction_counts()
        acts.sort(key=lambda a: (counts.get(a, 0), a))
        chosen = acts[0]
        params: dict = {}
        target = None
        if chosen in self._targeted:
            refs = self.current_referents_with_cells()
            if refs:
                per_ref = {r["target_ref"]: r["n"] for r in self.store.conn.execute(
                    "SELECT target_ref, COUNT(*) n FROM consequence_record WHERE run_id=? "
                    "AND target_ref IS NOT NULL GROUP BY target_ref", (self.run_id,))}
                refs.sort(key=lambda r: (per_ref.get(r["ref_id"], 0), len(r["cells"]), r["ref_id"]))
                cell = min(refs[0]["cells"])           # a real cell of the chosen referent
                params = {"x": int(cell[0]), "y": int(cell[1])}
                target = refs[0]["ref_id"]
            else:
                params = {"x": 0, "y": 0}
        return {"action": chosen, "params": params, "target_ref": target, "source_stamp": "PROBE"}

    def record_turn(self, turn_id: int, action: str, params: dict, target_ref: Optional[str],
                    pre_hash: str, post_hash: str, raw_diff: dict, observed_delta: Optional[dict],
                    score: int, level_counter: int, state_flags: str, lives: Optional[int],
                    source_stamp: str, commitment_step_id: Optional[str] = None,
                    predicted_delta: Optional[dict] = None, match: Optional[bool] = None,
                    render_tokens: int = 0, shadow_step_id: Optional[str] = None,
                    drift_ref: Optional[str] = None) -> None:
        self.store.conn.execute(
            "INSERT INTO turn_record (run_id, turn_id, action, params_json, target_ref, "
            "pre_frame_hash, post_frame_hash, raw_diff_json, predicted_delta_json, "
            "observed_delta_json, match, score, level_counter, state_flags, lives, "
            "commitment_step_id, source_stamp, render_tokens, shadow_step_id, drift_ref) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (self.run_id, turn_id, action, json.dumps(params) if params else None, target_ref,
             pre_hash, post_hash, json.dumps(raw_diff),
             json.dumps(predicted_delta) if predicted_delta is not None else None,
             json.dumps(observed_delta) if observed_delta is not None else None,
             None if match is None else (1 if match else 0), score, level_counter, state_flags,
             lives, commitment_step_id, source_stamp, render_tokens, shadow_step_id, drift_ref))

    def perceive_bind(self, turn_id: int, changeset) -> dict:
        """B3: re-identify each changed component against the Executive-proposed
        candidates — proposed by ANCHOR-OVERLAP OR SIGNATURE (§4.1); a referent
        with neither relation is never a candidate (the background cannot soak
        up a disjoint shape). Assignment is EXCLUSIVE within the beat: one
        referent binds one component. Auto-bind or mint NEW (+ same_as
        HYPOTHESIS below τ); a BindingRecord per assignment."""
        bound, minted = [], []
        cands = self.find_candidates()
        claimed: set = set()
        for comp in changeset.changed_components:
            eligible = [c for c in cands
                        if c["ref_id"] not in claimed
                        and (c["signature"] == comp.signature or (comp.cells & c["cellset"]))]
            decision = reidentify(comp, eligible)
            if not decision["is_new"]:
                claimed.add(decision["bound_to"])
            if decision["is_new"]:
                ref_id = self.mint_referent(comp, turn_id)
                minted.append(ref_id)
                if decision.get("same_as"):
                    self._propose_same_as(turn_id, ref_id, decision["same_as"])
            else:
                ref_id = decision["bound_to"]
                bound.append(ref_id)
                self._reanchor_if_moved(ref_id, comp, turn_id)
            decision["_ref"] = ref_id
            self.write_binding(turn_id, comp, decision)
        return {"cells_changed": changeset.cells_changed, "bound": bound, "minted": minted,
                "n_changed": len(changeset.changed_components)}

    def _propose_same_as(self, turn_id: int, new_ref: str, other_ref: str) -> None:
        rel_id = self.store.mint_id(self.run_id, "REL", config.ID_WIDTH)
        self.store.conn.execute(
            "INSERT INTO relation (run_id, rel_id, version, verb, src_ref, dst_ref, claim, "
            "scope, created_turn) VALUES (?,?,1,'same_as',?,?,?,'UNKNOWN',?)",
            (self.run_id, rel_id, new_ref, other_ref, "sub-τ merge candidate", turn_id))
        self._append_status(turn_id, "RELATION", rel_id, None, "HYPOTHESIS", "sub-τ same_as")

    def _reanchor_if_moved(self, ref_id: str, comp: Component, turn_id: int) -> None:
        """B3 'anchors updated': a re-bound referent whose observed cells differ
        from its current anchor gets a NEW VERSION row (append-only §2.2) with
        a fresh locator — the roster/Z5/Z6 join tracks the thing where it IS,
        containment checks stay live, and bind margins stop decaying (review
        S8a)."""
        row = self.store.conn.execute(
            "SELECT r.version, r.kind, r.first_seen, g.cells_json FROM referent r "
            "JOIN locator_gridregion g ON g.run_id=r.run_id AND g.locator_id=r.anchor_locator_id "
            "WHERE r.run_id=? AND r.ref_id=? ORDER BY r.version DESC LIMIT 1",
            (self.run_id, ref_id)).fetchone()
        if not row:
            return
        cur_cells = frozenset(tuple(c) for c in json.loads(row["cells_json"]))
        if cur_cells == comp.cells:
            return
        loc_id = self._write_gridregion_locator(comp, turn_id)
        self.store.conn.execute(
            "INSERT INTO referent (run_id, ref_id, version, kind, anchor_locator_id, "
            "signature, first_seen, provenance, created_turn) VALUES (?,?,?,?,?,?,?,?,?)",
            (self.run_id, ref_id, row["version"] + 1, row["kind"], loc_id, comp.signature,
             row["first_seen"], "OBSERVER_BIND", turn_id))

    def _dormant_refs(self) -> set:
        """Referents retired at a level boundary (§2.4.6 'instances reset') —
        out of the roster/candidates/frontier, never out of the store."""
        return {r["entity_id"] for r in self.store.conn.execute(
            "SELECT entity_id FROM status_transition st WHERE run_id=? AND "
            "entity_kind='REFERENT_LIFE' AND to_status='DORMANT' AND st.seq=(SELECT MAX(seq) "
            "FROM status_transition s2 WHERE s2.run_id=st.run_id AND s2.entity_id=st.entity_id "
            "AND s2.entity_kind='REFERENT_LIFE')", (self.run_id,))}

    def level_boundary_pass(self, turn_id: int) -> dict:
        """T5 demotion + re-seeding pass (§2.4.6, §4.2): every TESTED Rule
        demotes to HYPOTHESIS with prior support noted (the 0/16 lesson —
        hypotheses to re-test cheaply, never facts to trust); current referent
        INSTANCES go DORMANT; ACTIVE commitment steps abort."""
        demoted = 0
        for r in self.store.conn.execute(
                "SELECT DISTINCT entity_id FROM status_transition st WHERE run_id=? AND "
                "entity_kind='RULE' AND to_status='TESTED' AND st.seq=(SELECT MAX(seq) FROM "
                "status_transition s2 WHERE s2.run_id=st.run_id AND s2.entity_id=st.entity_id "
                "AND s2.entity_kind='RULE')", (self.run_id,)).fetchall():
            sup, mis = self.rule_support_mismatch(r["entity_id"])
            self._append_status(turn_id, "RULE", r["entity_id"], "TESTED", "HYPOTHESIS",
                                f"level-boundary demotion (prior_support={sup})")
            demoted += 1
        dormanted = 0
        for ref in sorted(self._roster_ids()):
            self._append_status(turn_id, "REFERENT_LIFE", ref, None, "DORMANT", "level boundary")
            dormanted += 1
        aborted = 0
        for s in self.store.conn.execute(
                "SELECT DISTINCT entity_id FROM status_transition st WHERE run_id=? AND "
                "entity_kind='COMMITMENT_STEP' AND to_status='ACTIVE' AND st.seq=(SELECT MAX(seq) "
                "FROM status_transition s2 WHERE s2.run_id=st.run_id AND s2.entity_id=st.entity_id "
                "AND s2.entity_kind='COMMITMENT_STEP')", (self.run_id,)).fetchall():
            self.mark_step(s["entity_id"], "ABORTED", turn_id, "level boundary")
            aborted += 1
        # §5.4: Procedures demote on any level/game change
        for p in self.store.conn.execute(
                "SELECT DISTINCT proc_id FROM procedure WHERE run_id=?", (self.run_id,)).fetchall():
            if self.current_status("PROCEDURE", p["proc_id"]) == "TESTED":
                self._append_status(turn_id, "PROCEDURE", p["proc_id"], "TESTED", "HYPOTHESIS",
                                    "level-boundary demotion")
        return {"rules_demoted": demoted, "referents_dormant": dormanted, "steps_aborted": aborted}

    def check_goal_budgets(self, turn_id: int) -> list:
        """§3.4 terminal rule (Executive-computed, no organ judgment): a goal
        whose committed-action budget is spent while its status is below
        VALIDATED auto-REJECTs with reason NEVER_VALIDATED — reactivity is not
        validation; decoys cannot immortalize their goals."""
        c = self.store.conn
        out = []
        for g in c.execute(
                "SELECT goal_id, budget_actions FROM goal WHERE run_id=? AND version=(SELECT "
                "MAX(version) FROM goal g2 WHERE g2.run_id=goal.run_id AND g2.goal_id=goal.goal_id)",
                (self.run_id,)).fetchall():
            st = self.current_status("GOAL", g["goal_id"])
            if st not in ("PROPOSED", "EXPLORED"):
                continue
            spent = c.execute(
                "SELECT COUNT(*) n FROM turn_record tr JOIN commitment_step cs ON cs.run_id=tr.run_id "
                "AND cs.step_id=tr.commitment_step_id JOIN commitment c2 ON c2.run_id=cs.run_id AND "
                "c2.commit_id=cs.commit_id AND c2.version=cs.commit_version "
                "WHERE tr.run_id=? AND c2.goal_id=?", (self.run_id, g["goal_id"])).fetchone()["n"]
            if g["budget_actions"] is not None and spent >= g["budget_actions"]:
                self._append_status(turn_id, "GOAL", g["goal_id"], st, "REJECTED", "NEVER_VALIDATED")
                out.append(g["goal_id"])
        return out

    def ttl_sweep(self, turn_id: int) -> list:
        """§2.3: negative evidence decays on TTL — a DEMOTED rule/procedure
        older than TTL turns becomes re-probeable (HYPOTHESIS). Beliefs decay
        toward doubt, not confidence; one refused press never walls off a goal."""
        out = []
        for kind in ("RULE", "PROCEDURE"):
            for r in self.store.conn.execute(
                    "SELECT entity_id, MAX(turn_id) t FROM status_transition WHERE run_id=? AND "
                    "entity_kind=? AND to_status='DEMOTED' GROUP BY entity_id",
                    (self.run_id, kind)).fetchall():
                if self.current_status(kind, r["entity_id"]) != "DEMOTED":
                    continue
                if turn_id - r["t"] >= config.TTL:
                    self._append_status(turn_id, kind, r["entity_id"], "DEMOTED", "HYPOTHESIS",
                                        "ttl-expired re-probeable")
                    out.append(r["entity_id"])
        return out

    def persist_relation(self, turn_id: int, verb: str, src: str, dst: str,
                         claim: Optional[str]) -> Optional[str]:
        verbs = {"requires", "enables", "blocks", "toggles", "part_of", "adjacent", "same_as"}
        if verb not in verbs:
            return None
        rel_id = self.store.mint_id(self.run_id, "REL", config.ID_WIDTH)
        self.store.conn.execute(
            "INSERT INTO relation (run_id, rel_id, version, verb, src_ref, dst_ref, claim, "
            "scope, created_turn) VALUES (?,?,1,?,?,?,?,'UNKNOWN',?)",
            (self.run_id, rel_id, verb, src, dst, claim, turn_id))
        self._append_status(turn_id, "RELATION", rel_id, None, "HYPOTHESIS", "proposed")
        return rel_id

    def resolve_evidence(self, ptr) -> Optional[dict]:
        """Resolve an evidence pointer to an Executive-stamped record in the
        closed contradiction class (§5.3a). The kind/turn/subject come from the
        ROW, never from the claimant — a merely-claimable record is not a
        contradiction (review S6). Pointer forms: 'turn:<n>' (a match=0 receipt
        at n), 'rule:<id>' (DEMOTED), 'goal:<id>' (REOPENED), 'step:<id>'
        (EXPIRED), 'fission:<ref>'."""
        if not isinstance(ptr, str) or ":" not in ptr:
            return None
        kind, _, ident = ptr.partition(":")
        c = self.store.conn
        if kind == "turn":
            try:
                t = int(ident)
            except ValueError:
                return None
            row = c.execute("SELECT target_ref, predictor_id FROM consequence_record WHERE run_id=? "
                            "AND turn_id=? AND match=0 LIMIT 1", (self.run_id, t)).fetchone()
            if row:
                return {"kind": "CONSEQUENCE_MISMATCH", "turn": t,
                        "subject": row["target_ref"] or row["predictor_id"] or ""}
        elif kind == "rule":
            row = c.execute("SELECT MAX(turn_id) t FROM status_transition WHERE run_id=? AND "
                            "entity_kind='RULE' AND entity_id=? AND to_status='DEMOTED'",
                            (self.run_id, ident)).fetchone()
            if row and row["t"] is not None:
                return {"kind": "DEMOTION", "turn": row["t"], "subject": ident}
        elif kind == "goal":
            row = c.execute("SELECT MAX(turn_id) t FROM status_transition WHERE run_id=? AND "
                            "entity_kind='GOAL' AND entity_id=? AND to_status='REOPENED'",
                            (self.run_id, ident)).fetchone()
            if row and row["t"] is not None:
                return {"kind": "REOPENED", "turn": row["t"], "subject": ident}
        elif kind == "step":
            row = c.execute("SELECT MAX(turn_id) t FROM status_transition WHERE run_id=? AND "
                            "entity_kind='COMMITMENT_STEP' AND entity_id=? AND to_status='EXPIRED'",
                            (self.run_id, ident)).fetchone()
            if row and row["t"] is not None:
                return {"kind": "LEASE_EXPIRY", "turn": row["t"], "subject": ident}
        elif kind == "fission":
            row = c.execute("SELECT MAX(turn_id) t FROM status_transition WHERE run_id=? AND "
                            "entity_kind='REFERENT_FISSION' AND entity_id=?",
                            (self.run_id, ident)).fetchone()
            if row and row["t"] is not None:
                return {"kind": "FISSION", "turn": row["t"], "subject": ident}
        return None

    def gate_abort_step(self, step_id: Optional[str], evidence_ptr, turn_id: int) -> dict:
        """The §5.3 Revision-Evidence gate on AbortStep, with the pointer
        RESOLVED against the store; an accepted abort writes the replayable
        REVISION record and ABORTs the step."""
        if not step_id:
            return {"ok": False, "reason": "NO_SUCH_STEP"}
        srow = self.store.conn.execute(
            "SELECT commit_id, commit_version, compilation_turn_id FROM commitment_step "
            "WHERE run_id=? AND step_id=?", (self.run_id, step_id)).fetchone()
        if not srow:
            return {"ok": False, "reason": "NO_SUCH_STEP"}
        ev = self.resolve_evidence(evidence_ptr)
        if ev is None:
            return {"ok": False, "reason": "NOT_CONTRADICTION_CLASS"}
        premise = {r["member_id"] for r in self.store.conn.execute(
            "SELECT member_id FROM step_premise WHERE run_id=? AND commit_id=? AND "
            "commit_version=? AND step_id=?",
            (self.run_id, srow["commit_id"], srow["commit_version"], step_id))}
        premise.add(step_id)
        gate = self.revision_evidence_gate(premise, srow["compilation_turn_id"],
                                           ev["kind"], ev["turn"], ev["subject"])
        if not gate["ok"]:
            return gate
        seq = self.store.next_seq(self.run_id, "revision")
        self.store.conn.execute(
            "INSERT INTO revision (run_id, seq, turn_id, step_id, evidence_ptr) VALUES (?,?,?,?,?)",
            (self.run_id, seq, turn_id, step_id, str(evidence_ptr)))
        self.mark_step(step_id, "ABORTED", turn_id, f"surveyor abort ({evidence_ptr})")
        return {"ok": True, "reason": None}

    # ---- M4: ingest validation (the "Executive disposes" half) ----
    def _roster_ids(self) -> set:
        return {r["ref_id"] for r in self.current_referents_with_cells()}

    def validate_observer_ops(self, ops: list, candidate_hashes: set) -> dict:
        """Reject any op that references an entity/hash/channel it may not, and
        enforce the completeness invariant: every proposed candidate hash must
        get a BIND verdict. Returns {accepted, rejections:[{op,violation}]}."""
        roster = self._roster_ids()
        signals = set(self.adapter.signal_channels().keys())
        accepted, rejections = [], []
        verdicted = set()
        for op in ops:
            if not isinstance(op, dict) or "op" not in op:
                rejections.append({"op": op, "violation": "MALFORMED"})
                continue
            kind = op["op"]
            if kind == "BIND":
                h = op.get("component_hash")
                if h not in candidate_hashes:
                    rejections.append({"op": op, "violation": "OFF_CANDIDATE_BIND"})
                    continue
                to = op.get("to")
                if to != "NEW" and to not in roster:
                    rejections.append({"op": op, "violation": "DANGLING_REF"})
                    continue
                verdicted.add(h)
                accepted.append(op)
            elif kind == "NOTE_EVENT":
                if op.get("ref") not in roster:
                    rejections.append({"op": op, "violation": "DANGLING_REF"})
                elif op.get("event_kind") not in signals:
                    rejections.append({"op": op, "violation": "NON_MEMBER_EVENT"})
                else:
                    accepted.append(op)
            elif kind in ("PROPOSE_RELATION",):
                if op.get("src") not in roster or op.get("dst") not in roster:
                    rejections.append({"op": op, "violation": "DANGLING_REF"})
                else:
                    accepted.append(op)
            elif kind == "PROPOSE_RULE":
                ok, why = self.validate_rule_shape(op.get("ctx"), op.get("effect"))
                if ok:
                    accepted.append(op)
                else:
                    rejections.append({"op": op, "violation": why})
            elif kind in ("INTERPRET", "ANNOTATE"):
                if kind == "INTERPRET" and op.get("ref") not in roster:
                    rejections.append({"op": op, "violation": "DANGLING_REF"})
                else:
                    accepted.append(op)
            else:
                rejections.append({"op": op, "violation": "UNKNOWN_OP"})
        # completeness: every candidate must have been verdicted
        missing = candidate_hashes - verdicted
        for h in missing:
            rejections.append({"op": {"component_hash": h}, "violation": "INCOMPLETE_COVERAGE"})
        return {"accepted": accepted, "rejections": rejections, "coverage_ok": not missing}

    def validate_actuator(self, action: str, x: int, y: int, cited_ref: Optional[str],
                          param_schema: dict) -> dict:
        """R8: the realized parameter must lie inside the cited referent's anchor
        cells and match the step's schema — a coordinate copied from an adjacent
        row is a CAUGHT violation. Returns {ok, violation, fallback:(x,y)?}."""
        if action not in self._targeted:
            return {"ok": True, "violation": None, "fallback": None}
        # schema bounds
        xb = param_schema.get("x", [0, 63]); yb = param_schema.get("y", [0, 63])
        if not (xb[0] <= x <= xb[1] and yb[0] <= y <= yb[1]):
            return {"ok": False, "violation": "OUT_OF_SCHEMA", "fallback": self._centroid(cited_ref)}
        if cited_ref is None:
            return {"ok": False, "violation": "NO_CITED_REF", "fallback": None}
        cells = self._ref_cells(cited_ref)
        if (x, y) not in cells:
            return {"ok": False, "violation": "UNCONTAINED_PARAM", "fallback": self._centroid(cited_ref)}
        return {"ok": True, "violation": None, "fallback": None}

    def _ref_cells(self, ref_id: str) -> set:
        for r in self.current_referents_with_cells():
            if r["ref_id"] == ref_id:
                return {tuple(c) for c in r["cells"]}
        return set()

    def _centroid(self, ref_id: Optional[str]) -> Optional[tuple]:
        if ref_id is None:
            return None
        cells = self._ref_cells(ref_id)
        if not cells:
            return None
        n = len(cells)
        return (round(sum(c[0] for c in cells) / n), round(sum(c[1] for c in cells) / n))

    def meter_write_reject(self, turn_id: int, organ: str, op_type: str,
                           violation_class: str, retry_count: int) -> None:
        seq = self.store.next_seq(self.run_id, "write_reject")
        self.store.conn.execute(
            "INSERT INTO write_reject (run_id, seq, turn_id, organ, op_type, violation_class, "
            "retry_count) VALUES (?,?,?,?,?,?,?)",
            (self.run_id, seq, turn_id, organ, op_type, violation_class, retry_count))

    # ===== W1: closed rule format + pre-registration (B4 as designed) =====
    # A rule is mechanically testable iff its ctx/effect live in this closed
    # vocabulary (buildplan §11 match tolerance): the Executive can then
    # pre-register its prediction BEFORE emission and compute the match itself.
    RULE_EFFECT_KEYS = frozenset({"cells_changed", "score_event", "level_event"})

    def validate_rule_shape(self, ctx, effect) -> tuple:
        """(ok, violation). ctx = {action: <vocab>, target: R###|null, when: AST|null};
        effect ⊆ {cells_changed: zero|nonzero|int, score_event: 0/1, level_event: 0/1}.
        A rule outside this vocabulary is untestable → inadmissible (§9.2 trade)."""
        actions = {s["action"] for s in self.adapter.action_vocab()}
        if not isinstance(ctx, dict) or ctx.get("action") not in actions:
            return False, "RULE_CTX_NOT_CLOSED"
        tgt = ctx.get("target")
        if tgt is not None and tgt not in self._roster_ids():
            return False, "RULE_TARGET_DANGLING"
        when = ctx.get("when")
        if when is not None:
            ok, _ = predicates.compiles(when, self.adapter.signal_channels())
            if not ok:
                return False, "RULE_WHEN_INCOMPILABLE"
        if not isinstance(effect, dict) or not effect or not set(effect) <= self.RULE_EFFECT_KEYS:
            return False, "RULE_EFFECT_NOT_CLOSED"
        cc = effect.get("cells_changed")
        if cc is not None and cc not in ("zero", "nonzero") and not isinstance(cc, int):
            return False, "RULE_EFFECT_NOT_CLOSED"
        if any(effect.get(k) not in (None, 0, 1) for k in ("score_event", "level_event")):
            return False, "RULE_EFFECT_NOT_CLOSED"
        return True, ""

    def applicable_rules(self, action: str, target: Optional[str], signals_ctx: dict) -> list:
        """Non-DEMOTED current-version rules whose closed ctx matches this
        (action, target) under the current signals. TESTED first, then id —
        deterministic pre-registration order."""
        rows = self.store.conn.execute(
            "SELECT rule_id, ctx_pred_json, effect_pattern_json FROM rule r WHERE r.run_id=? "
            "AND r.version=(SELECT MAX(version) FROM rule r2 WHERE r2.run_id=r.run_id "
            "AND r2.rule_id=r.rule_id)", (self.run_id,)).fetchall()
        out = []
        for r in rows:
            st = self.current_status("RULE", r["rule_id"]) or "HYPOTHESIS"
            if st == "DEMOTED":
                continue
            try:
                ctx = json.loads(r["ctx_pred_json"])
                effect = json.loads(r["effect_pattern_json"])
            except (ValueError, TypeError):
                continue
            if not isinstance(ctx, dict) or ctx.get("action") != action:
                continue
            tgt = ctx.get("target")
            if tgt is not None and tgt != target:
                continue
            when = ctx.get("when")
            if when is not None and not predicates.eval_now(when, signals_ctx):
                continue
            out.append({"rule_id": r["rule_id"], "status": st, "effect": effect, "target": tgt})
        out.sort(key=lambda p: (0 if p["status"] == "TESTED" else 1, p["rule_id"]))
        return out

    def match_effect(self, effect: dict, cells_changed: int, score_event: int,
                     level_event: int) -> bool:
        """Deterministic subset-exact effect match (buildplan §11 tolerance)."""
        cc = effect.get("cells_changed")
        if cc == "zero" and cells_changed != 0:
            return False
        if cc == "nonzero" and cells_changed <= 0:
            return False
        if isinstance(cc, int) and cells_changed != cc:
            return False
        if "score_event" in effect and effect["score_event"] != score_event:
            return False
        if "level_event" in effect and effect["level_event"] != level_event:
            return False
        return True

    def stamp_fission_check(self, ref_id: str, turn_id: int) -> dict:
        """Run the fission statistic on a mismatch and stamp it when it fires
        (FSN source; the destructive re-split stays gated off in build-1)."""
        fc = self.fission_check(ref_id)
        if fc["fired"]:
            self._append_status(turn_id, "REFERENT_FISSION", ref_id, None, "FISSION_CHECK",
                                f"r={fc['r']} mismatches={fc['mismatches']}")
        return fc

    # ===== G1: the sufficiency recognizer (goal-chain proposal §2.2) =====

    def _goal_test(self, goal_id: str) -> Optional[dict]:
        row = self.store.conn.execute(
            "SELECT achievement_test_json FROM goal WHERE run_id=? AND goal_id=? "
            "ORDER BY version DESC LIMIT 1", (self.run_id, goal_id)).fetchone()
        return json.loads(row["achievement_test_json"]) if row else None

    def _milestone_rule_of(self, test: Optional[dict]) -> Optional[str]:
        """A knowledge-milestone test names its rule: RULE_STATUS(RU, TESTED)
        or EXISTS/COUNT consequence{predictor: RU, match: 1}."""
        if not isinstance(test, dict):
            return None
        if test.get("op") == "RULE_STATUS" and test.get("is") == "TESTED":
            return test.get("rule")
        if test.get("op") in ("EXISTS", "COUNT") and test.get("entity") == "consequence":
            w = test.get("where") or {}
            if w.get("predictor") and w.get("match") == 1:
                return w["predictor"]
        return None

    def _milestone_means(self, goal_id: str) -> Optional[str]:
        """A milestone goal is executable iff its named rule exists, is not
        DEMOTED, and is EXERCISABLE now — compiling it = the
        experiment-commitment toward that rule."""
        ru = self._milestone_rule_of(self._goal_test(goal_id))
        if ru and self.store.conn.execute(
                "SELECT 1 FROM rule WHERE run_id=? AND rule_id=? LIMIT 1",
                (self.run_id, ru)).fetchone():
            if self.current_status("RULE", ru) != "DEMOTED" and self._rule_exercisable(ru):
                return ru
        return None

    def _rule_exercisable(self, rule_id: str) -> bool:
        """A target-scoped rule reached via an UNTARGETED action needs a
        navigate route: an untargeted emission stamps target=None, so the
        rule's receipt can never land without arriving first — compiling it
        anyway is the gen4 degenerate loop (336 blind commitments)."""
        row = self.store.conn.execute(
            "SELECT ctx_pred_json FROM rule WHERE run_id=? AND rule_id=? "
            "ORDER BY version DESC LIMIT 1", (self.run_id, rule_id)).fetchone()
        try:
            ctx = json.loads(row["ctx_pred_json"]) if row else None
        except (ValueError, TypeError):
            return False
        if not isinstance(ctx, dict) or not ctx.get("action"):
            return False
        action, target = ctx.get("action"), ctx.get("target")
        if target and action not in self._targeted:
            return self.compile_navigate(target) is not None
        return True

    def needs(self, goal_id: str, ctx: dict) -> list:
        """Unmet requirement descriptors of a goal's test: effect keys from its
        channel comparisons + the record/status predicates currently FALSE.
        Records-only; no LLM."""
        test = self._goal_test(goal_id)
        if test is None:
            return []
        out = [{"kind": "effect", "key": k} for k in sorted(self._test_effect_keys(test))]
        rec = self._record_eval_factory(ctx)

        def scan(n):
            if not isinstance(n, dict):
                return
            op = n.get("op")
            if op in ("EXISTS", "COUNT", "RULE_STATUS", "RUNG",
                      "LEARN_ACTIONS", "LEARN_RULES", "LEARN_ENV"):
                if not predicates.eval_now(n, ctx, rec):
                    out.append({"kind": "record", "pred": n})
            for a in n.get("args", []):
                scan(a)
        scan(test)
        return out

    def _hole_evidence(self, effect_key: str) -> dict:
        """The derivable evidence for an effect hole: non-DEMOTED rules whose
        closed effect carries the key (the auto-fill candidates), whether an
        action model exists (can we even navigate), and the most-RECEIPTED
        referents (wave-E observation: receipt density feeds hypothesizing —
        concrete anchors beat an open sky when no candidate rule exists)."""
        cands = []
        for r in self.store.conn.execute(
                "SELECT rule_id, effect_pattern_json FROM rule WHERE run_id=? AND "
                "version=(SELECT MAX(version) FROM rule r2 WHERE r2.run_id=rule.run_id "
                "AND r2.rule_id=rule.rule_id)", (self.run_id,)).fetchall():
            try:
                eff = json.loads(r["effect_pattern_json"])
            except (ValueError, TypeError):
                continue
            if eff.get(effect_key) == 1 and self.current_status("RULE", r["rule_id"]) != "DEMOTED":
                cands.append(r["rule_id"])
        has_model = bool(self.store.conn.execute(
            "SELECT 1 FROM action_model WHERE run_id=? LIMIT 1", (self.run_id,)).fetchone())
        receipted = [f"{r['target_ref']}:{r['n']}" for r in self.store.conn.execute(
            "SELECT target_ref, COUNT(*) n FROM consequence_record WHERE run_id=? AND "
            "target_ref IS NOT NULL GROUP BY target_ref ORDER BY n DESC, target_ref LIMIT 5",
            (self.run_id,))]
        return {"candidate_rules": sorted(cands), "action_model": has_model,
                "receipted_refs": receipted}

    def verify_fill(self, parent_goal: str, child_test: dict, ctx: dict) -> tuple:
        """(verified, hole). Mechanical fill proof — an LLM cannot assert it:
        (i) knowledge fill: the child's milestone rule carries a closed effect
        covering one of the parent's unmet effect keys; (ii) signal fill: the
        child's own effect keys ⊆ the parent's unmet effect keys."""
        pkeys = {n["key"] for n in self.needs(parent_goal, ctx) if n["kind"] == "effect"}
        if not pkeys:
            return False, None
        ckeys = self._test_effect_keys(child_test or {})
        if ckeys and ckeys <= pkeys:
            return True, {"kind": "effect", "keys": sorted(ckeys), "via": "signal"}
        ru = self._milestone_rule_of(child_test)
        if ru:
            row = self.store.conn.execute(
                "SELECT effect_pattern_json FROM rule WHERE run_id=? AND rule_id=? "
                "ORDER BY version DESC LIMIT 1", (self.run_id, ru)).fetchone()
            if row:
                try:
                    eff = json.loads(row["effect_pattern_json"])
                except (ValueError, TypeError):
                    eff = {}
                keys = [k for k in pkeys if eff.get(k) == 1]
                if keys:
                    return True, {"kind": "effect", "keys": sorted(keys), "via": ru}
        return False, None

    def add_goal_edge(self, parent_goal: str, child_goal: str, hole: Optional[dict],
                      verified: bool, turn_id: int) -> None:
        self.store.conn.execute(
            "INSERT OR IGNORE INTO goal_edge (run_id, parent_goal, child_goal, hole_json, "
            "verified, created_turn) VALUES (?,?,?,?,?,?)",
            (self.run_id, parent_goal, child_goal, json.dumps(hole or {}),
             1 if verified else 0, turn_id))

    def _verified_children(self, goal_id: str) -> list:
        return [(r["child_goal"], json.loads(r["hole_json"] or "{}"))
                for r in self.store.conn.execute(
                    "SELECT child_goal, hole_json FROM goal_edge WHERE run_id=? AND "
                    "parent_goal=? AND verified=1", (self.run_id, goal_id))]

    def chain_status(self, goal_id: str, ctx: dict, _seen: Optional[set] = None) -> dict:
        """THE sufficiency recognizer: {status, holes} — deterministic,
        bottom-up, records-only. COMPILABLE = means analysis (or a milestone's
        rule) serves it NOW; REDUCIBLE = every effect need covered by a
        verified, non-DEFICIT child (or no effect needs — record pursuits
        reduce via probes); DEFICIT = typed holes with derivable evidence.
        'Enough goals exist' ⇔ holes = ∅ (owner's load-bearing question)."""
        _seen = (_seen or set()) | {goal_id}
        st = self.current_status("GOAL", goal_id)
        if st == "ACCEPTED":
            return {"status": "COMPILABLE", "holes": []}
        if st == "REJECTED":
            # NEVER_VALIDATED/terminal: contributes nothing and covers nothing
            # — the parent's hole re-opens (§3 budget-exhaustion clause)
            return {"status": "DEFICIT", "holes": [{"kind": "terminal", "goal": goal_id}]}
        if self._select_means(goal_id, ctx) is not None or self._milestone_means(goal_id):
            return {"status": "COMPILABLE", "holes": []}
        eff_needs, rec_needs = [], []
        for n in self.needs(goal_id, ctx):
            (eff_needs if n["kind"] == "effect" else rec_needs).append(n)
        holes = []
        # a milestone pursuit whose named rule is DEMOTED or missing is a dead
        # end — the chain re-opens honestly instead of resting on it (§9.3);
        # other record pursuits (LEARN-class) reduce via probes, never blocking
        for n in rec_needs:
            ru = self._milestone_rule_of(n.get("pred"))
            if not ru:
                continue
            exists = self.store.conn.execute(
                "SELECT 1 FROM rule WHERE run_id=? AND rule_id=? LIMIT 1",
                (self.run_id, ru)).fetchone()
            st = (self.current_status("RULE", ru) or "HYPOTHESIS") if exists else "MISSING"
            if st in ("DEMOTED", "MISSING"):
                holes.append({"kind": "record", "pred": n["pred"],
                              "evidence": {"rule": ru, "rule_status": st}})
        children = self._verified_children(goal_id)
        for n in eff_needs:
            covered = False
            for child, hole in children:
                if child in _seen:
                    continue
                keys = set((hole or {}).get("keys") or [])
                if n["key"] in keys and \
                        self.chain_status(child, ctx, _seen)["status"] != "DEFICIT":
                    covered = True
                    break
            if not covered:
                holes.append({"kind": "effect", "key": n["key"],
                              "evidence": self._hole_evidence(n["key"])})
        if not holes:
            return {"status": "REDUCIBLE", "holes": []}
        return {"status": "DEFICIT", "holes": holes}

    def auto_fill_holes(self, goal_id: str, holes: list, turn_id: int) -> list:
        """Deterministic auto-fill (amendment A2, 0 LLM): a hole that names its
        own fill — HYPOTHESIS rules carrying the needed effect — is derivable;
        the Executive drafts the milestone sub-goals ('test RU####' := COUNT
        matched receipts ≥ k, the promotion bar) through the SAME six gates,
        provenance DEFICIT, and creates the verified edge. Returns admitted
        child goal ids; holes with no candidates are the Surveyor's question."""
        made: list = []
        roster = {r["ref_id"] for r in self.current_referents_with_cells()}
        for h in holes:
            if h.get("kind") != "effect":
                continue
            for ru in (h.get("evidence") or {}).get("candidate_rules", []):
                row = self.store.conn.execute(
                    "SELECT ctx_pred_json, created_turn FROM rule WHERE run_id=? AND rule_id=? "
                    "ORDER BY version DESC LIMIT 1", (self.run_id, ru)).fetchone()
                if not row:
                    continue
                try:
                    rctx = json.loads(row["ctx_pred_json"])
                except (ValueError, TypeError):
                    rctx = {}
                target = rctx.get("target") if isinstance(rctx, dict) else None
                test = {"op": "COUNT", "entity": "consequence",
                        "where": {"predictor": ru, "match": 1}, "value": config.K_SUPPORT}
                proposal = {"statement": f"test {ru} (deliberate matched receipts)",
                            "bindings": [target] if target in roster else [],
                            "achievement_test": test,
                            "discriminator": {"rule_receipt": ru},
                            "evidence_ptrs": [row["created_turn"]],
                            # a milestone is an EXPERIMENT, not a campaign: its
                            # budget scales with the promotion bar so exhaustion
                            # → NEVER_VALIDATED → the chain re-opens (§3) —
                            # gen3 spent 379/400 beats on unbounded milestones,
                            # starving exploration
                            "budget_actions": max(8, 6 * config.K_SUPPORT),
                            "provenance": "DEFICIT"}
                res = self.admit_goal(proposal, turn_id, parent=goal_id)
                if not res.get("ok"):
                    continue      # duplicate sibling / budgets — the gates hold
                child = res["goal_id"]
                verified, hole = self.verify_fill(goal_id, test, {"cur": {}, "prev": {}})
                self.add_goal_edge(goal_id, child, hole if verified else h,
                                   verified=verified, turn_id=turn_id)
                made.append(child)
        return made

    def deficit_stamp(self, goal_id: str, holes: list, turn_id: int) -> bool:
        """Append-only DEFICIT stamp: 'the chain is incomplete HERE, with THIS
        evidence' — the Surveyor's directed question (T3) and the campaign's
        auditable trace that the system knew. Deduped against the goal's last
        stamp so a probing stretch does not spam identical rows."""
        hj = json.dumps(holes, sort_keys=True)
        last = self.store.conn.execute(
            "SELECT holes_json FROM deficit_stamp WHERE run_id=? AND goal_id=? "
            "ORDER BY seq DESC LIMIT 1", (self.run_id, goal_id)).fetchone()
        if last and last["holes_json"] == hj:
            return False
        seq = self.store.next_seq(self.run_id, "deficit_stamp")
        self.store.conn.execute(
            "INSERT INTO deficit_stamp (run_id, seq, turn_id, goal_id, holes_json) "
            "VALUES (?,?,?,?,?)", (self.run_id, seq, turn_id, goal_id, hj))
        return True

    def open_deficits(self) -> list:
        """Latest stamped holes per live goal — the epoch view's DEFICIT block
        feed (G3). A goal whose chain has since closed is filtered by rechecking
        nothing here: stamps are historical; the CALLER recomputes chain_status
        for live truth. Returns [{goal_id, holes, turn_id}] newest-first."""
        rows = self.store.conn.execute(
            "SELECT goal_id, holes_json, MAX(seq) s, turn_id FROM deficit_stamp "
            "WHERE run_id=? GROUP BY goal_id ORDER BY s DESC", (self.run_id,)).fetchall()
        out = []
        for r in rows:
            if self.current_status("GOAL", r["goal_id"]) in ("ACCEPTED", "REJECTED"):
                continue
            out.append({"goal_id": r["goal_id"], "holes": json.loads(r["holes_json"]),
                        "turn_id": r["turn_id"]})
        return out

    def walk_candidates(self) -> list:
        """The walk's visit order (§4.3 + chain §2.5): chain leaf first, then
        the root's rank-ordered live children, then the chain ancestors
        deepest-first — the root's own deficit stays visible while curriculum
        children live. Shared by the beat walk and the epoch DEFICIT block."""
        chain = self.goal_chain()
        if not chain:
            return []
        out = [chain[-1]]
        for gid in self.compute_rank(chain[0] if len(chain) > 1 else None)["order"]:
            if gid not in out:
                out.append(gid)
        for gid in reversed(chain[:-1]):
            if gid not in out:
                out.append(gid)
        return out

    def deficit_view_block(self, ctx: dict) -> str:
        """The epoch view's DEFICIT block (chain §2.4 tier 2): live holes
        recomputed NOW per walked goal — the machine-stated question the
        Surveyor answers with fills_hole proposals. Stamps are history; this
        is truth at render time."""
        lines = []
        for gid in self.walk_candidates():
            if self.current_status("GOAL", gid) in ("ACCEPTED", "REJECTED"):
                continue
            cs = self.chain_status(gid, ctx)
            if cs["status"] != "DEFICIT":
                continue
            for i, h in enumerate(cs["holes"]):
                lines.append(f"  {gid}/H{i}: {json.dumps(h, sort_keys=True)[:220]}")
        if not lines:
            return ("DEFICIT: none — the goal chain is complete or reducible; "
                    "do NOT invent sub-goals.")
        out = ("DEFICIT (the goal chain is INCOMPLETE exactly here; propose "
               "PROPOSE_GOAL ops that fill THESE holes — set parent to the "
               "deficient goal id and fills_hole to the hole id; the engine "
               "PROVES each fill mechanically, so aim the test at the hole's "
               "effect key or at a rule carrying it):\n" + "\n".join(lines))
        if any('"candidate_rules": []' in ln for ln in lines):
            # feedstock steering (4d lever 1 + wave-F refinement): an
            # empty-evidence hole means NO rule carrying that effect exists —
            # a fills_hole goal cannot help; the productive answer is the rule
            # itself, and TARGET-SCOPED beats untargeted (every untargeted
            # single-action effect rule so far has demoted)
            out += ("\nFor a hole whose candidate_rules is EMPTY, no rule "
                    "carrying that effect exists yet: propose a PROPOSE_RULE "
                    "whose effect includes that key (score_event/level_event) "
                    "with a test_plan — the engine will draft and run its "
                    "test-milestone automatically once the rule exists. PREFER "
                    "rules SCOPED to a specific referent (\"target\":\"R####\") "
                    "— each hole's receipted_refs lists the most-interacted "
                    "referents as concrete anchors; untargeted single-action "
                    "effect rules have consistently demoted on this class of "
                    "game (the effect needs the RIGHT object, not just the "
                    "right button).")
        return out

    def chain_frontier(self, goal_id: str, ctx: dict, _seen: Optional[set] = None) -> Optional[str]:
        """The chain frontier (§2.5): the DEEPEST live compilable goal along
        verified edges — children execute before the parents they serve.
        Returns a goal id whose compile_plan should succeed now, or None."""
        _seen = (_seen or set()) | {goal_id}
        if self.current_status("GOAL", goal_id) in ("ACCEPTED", "REJECTED"):
            return None
        for child, _hole in self._verified_children(goal_id):
            if child in _seen:
                continue
            deep = self.chain_frontier(child, ctx, _seen)
            if deep is not None:
                return deep
        if self._select_means(goal_id, ctx) is not None or self._milestone_means(goal_id):
            return goal_id
        return None

    # ===== W2: the agenda acts — walk, means analysis, step lifecycle =====

    def goal_chain(self) -> list:
        """Root→leaf active chain: descend from the root into the first live
        child by compute_rank until none remains. §4.3's 'tree walk over an
        Executive-computed order' — literal, and recomputed per beat."""
        c = self.store.conn
        root = c.execute("SELECT goal_id FROM goal WHERE run_id=? AND parent_goal IS NULL "
                         "ORDER BY goal_id LIMIT 1", (self.run_id,)).fetchone()
        if not root:
            return []
        chain = [root["goal_id"]]
        while True:
            nxt = None
            for gid in self.compute_rank(chain[-1])["order"]:
                if self.current_status("GOAL", gid) not in ("ACCEPTED", "REJECTED"):
                    nxt = gid
                    break
            if nxt is None:
                break
            chain.append(nxt)
        return chain

    def _test_effect_keys(self, test: dict) -> set:
        """Which closed effect keys advance this achievement test (means
        analysis, §4.3 step 2). state-WIN routes through level progress."""
        keys: set = set()

        def scan(n):
            if not isinstance(n, dict):
                return
            ch = n.get("channel")
            if ch == "score":
                keys.add("score_event")
            elif ch in ("levels_completed", "state"):
                keys.add("level_event")
            for a in n.get("args", []):
                scan(a)
        scan(test)
        return keys

    def _select_means(self, leaf_goal: str, signals_ctx: dict) -> Optional[tuple]:
        """Means analysis (§4.3 step 2): the first TESTED rule (deterministic
        order) whose closed effect advances the leaf's test under the current
        signals. Pure read — shared verbatim by live compile and shadow compile
        so the A-off instrumentation plans EXACTLY as FULL would."""
        g = self.store.conn.execute(
            "SELECT achievement_test_json FROM goal WHERE run_id=? AND goal_id=? "
            "ORDER BY version DESC LIMIT 1", (self.run_id, leaf_goal)).fetchone()
        if not g:
            return None
        wanted = self._test_effect_keys(json.loads(g["achievement_test_json"]))
        if not wanted:
            return None
        rows = self.store.conn.execute(
            "SELECT rule_id, ctx_pred_json, effect_pattern_json FROM rule r WHERE r.run_id=? "
            "AND r.version=(SELECT MAX(version) FROM rule r2 WHERE r2.run_id=r.run_id "
            "AND r2.rule_id=r.rule_id) ORDER BY rule_id", (self.run_id,)).fetchall()
        for r in rows:
            if self.current_status("RULE", r["rule_id"]) != "TESTED":
                continue
            try:
                ctx = json.loads(r["ctx_pred_json"])
                effect = json.loads(r["effect_pattern_json"])
            except (ValueError, TypeError):
                continue
            if not isinstance(ctx, dict) or not any(effect.get(k) == 1 for k in wanted):
                continue
            when = ctx.get("when")
            if when is not None and not predicates.eval_now(when, signals_ctx):
                continue
            # §2.2 scope discipline: a WITHIN_LIFE effect vanished after the
            # last death — it needs re-arming (re-probing) before a plan may
            # rest on it; a post-death match flips it back via rule_scope.
            if self.rule_scope(r["rule_id"]) == "WITHIN_LIFE":
                continue
            return (r["rule_id"], ctx, effect)
        return None

    def plan_shadow_step(self, signals_ctx: dict) -> Optional[str]:
        """§8 shadow-agenda instrumentation: per-beat recompile from the live
        store EXACTLY as FULL would — never persisted, never rendered, never
        executed. Chain-aware since §3.5: the shadow mirrors the chain-frontier
        walk (frontier → TESTED means → milestone means), and computes the
        auto-fill tier VIRTUALLY — FULL would draft a milestone toward a hole's
        candidate rule, so the shadow references that rule's (action, target)
        without writing a goal (the write tier cannot run in a pure read).
        The descriptor names the beat's reference step for GDS metrics:
        'goal|action|target|rule'."""
        def _rule_descriptor(gid, ru):
            row = self.store.conn.execute(
                "SELECT ctx_pred_json FROM rule WHERE run_id=? AND rule_id=? "
                "ORDER BY version DESC LIMIT 1", (self.run_id, ru)).fetchone()
            try:
                rctx = json.loads(row["ctx_pred_json"]) if row else {}
            except (ValueError, TypeError):
                rctx = {}
            return (f"{gid}|{rctx.get('action')}|{rctx.get('target') or '-'}|{ru}"
                    if isinstance(rctx, dict) and rctx.get("action") else None)

        for gid in self.walk_candidates():
            if self.current_status("GOAL", gid) in ("ACCEPTED", "REJECTED"):
                continue
            fr = self.chain_frontier(gid, signals_ctx) or gid
            sel = self._select_means(fr, signals_ctx)
            if sel is not None:
                rule_id, ctx, _ = sel
                return f"{fr}|{ctx.get('action')}|{ctx.get('target') or '-'}|{rule_id}"
            ru = self._milestone_means(fr)
            if ru:
                d = _rule_descriptor(fr, ru)
                if d:
                    return d
            cs = self.chain_status(gid, signals_ctx)
            if cs["status"] == "DEFICIT":
                for h in cs["holes"]:
                    for cand in (h.get("evidence") or {}).get("candidate_rules", []):
                        if self._rule_exercisable(cand):
                            d = _rule_descriptor(gid, cand)   # virtual auto-fill
                            if d:
                                return d
        return None

    def compile_plan(self, leaf_goal: str, turn_id: int, signals_ctx: dict) -> Optional[str]:
        """§4.3 steps 2–3: means analysis over TESTED rules whose effect
        advances the leaf's test, compiled to Commitment steps with premise
        closure + predictions; relevance_edges and goal bindings stamped as a
        by-product. None → the caller probes (and T3 arms)."""
        # §5.4: applicable Procedures compile BEFORE fresh means analysis
        level = (signals_ctx.get("cur") or {}).get("levels_completed", 0) or 0
        via_proc = self.compile_from_procedure(leaf_goal, turn_id, level)
        if via_proc is not None:
            return via_proc
        chosen = self._select_means(leaf_goal, signals_ctx)
        if chosen is None:
            # milestone goals compile toward their named rule even while it is
            # HYPOTHESIS — the experiment-commitment path (proposal §2.3)
            return self._compile_milestone(leaf_goal, turn_id)
        rule_id, ctx, effect = chosen
        return self._compile_rule_steps(leaf_goal, rule_id, ctx, effect, turn_id)

    def _compile_rule_steps(self, goal_id: str, rule_id: str, ctx: dict, effect: dict,
                            turn_id: int) -> Optional[str]:
        """NAVIGATE* + INTERACT toward a rule's (action, target), the rule's
        closed effect pre-registered as the step prediction, the rule itself as
        premise (auto-block on demotion)."""
        action, target = ctx.get("action"), ctx.get("target")
        steps: list = []
        if action not in self._targeted and target:
            nav = self.compile_navigate(target)
            if nav:
                steps = nav["steps"][:-1]     # NAVIGATE prefix; our INTERACT replaces the slot
        steps.append({"kind": "INTERACT", "action": action, "target_ref": target,
                      "predicted": effect})
        commit_id = self.write_commitment(goal_id, steps, turn_id, premise_rules=[rule_id])
        self.stamp_relevance(turn_id, goal_id, "RULE", rule_id)
        if target:
            self.stamp_relevance(turn_id, goal_id, "REFERENT", target)
            self.bind_goal_ref(goal_id, target)
        return commit_id

    def _compile_milestone(self, goal_id: str, turn_id: int) -> Optional[str]:
        """Experiment-commitment toward the milestone's named rule (§2.3): the
        HYPOTHESIS rule's prediction is pre-registered on the INTERACT step and
        B4a additionally mints the RULE receipt the milestone's own test
        quantifies over — navigate-then-interact EMERGES as this compilation."""
        ru = self._milestone_means(goal_id)
        if ru is None:
            return None
        row = self.store.conn.execute(
            "SELECT ctx_pred_json, effect_pattern_json FROM rule WHERE run_id=? AND rule_id=? "
            "ORDER BY version DESC LIMIT 1", (self.run_id, ru)).fetchone()
        try:
            ctx = json.loads(row["ctx_pred_json"])
            effect = json.loads(row["effect_pattern_json"])
        except (ValueError, TypeError):
            return None
        if not isinstance(ctx, dict) or not ctx.get("action"):
            return None
        return self._compile_rule_steps(goal_id, ru, ctx, effect, turn_id)

    def stamp_relevance(self, turn_id: int, goal_id: str, kind: str, target_id: str) -> None:
        seq = self.store.next_seq(self.run_id, "relevance_edge")
        self.store.conn.execute(
            "INSERT INTO relevance_edge (run_id, seq, turn_id, goal_id, target_kind, target_id) "
            "VALUES (?,?,?,?,?,?)", (self.run_id, seq, turn_id, goal_id, kind, target_id))

    def bind_goal_ref(self, goal_id: str, ref_id: str) -> None:
        v = self.store.current_version(self.run_id, "goal", "goal_id", goal_id) or 1
        self.store.conn.execute(
            "INSERT OR IGNORE INTO goal_binding (run_id, goal_id, goal_version, ref_id) "
            "VALUES (?,?,?,?)", (self.run_id, goal_id, v, ref_id))

    def mark_step(self, step_id: str, to_status: str, turn_id: int, reason: str) -> None:
        cur = self.current_status("COMMITMENT_STEP", step_id)
        self._append_status(turn_id, "COMMITMENT_STEP", step_id, cur, to_status, reason)

    def step_premises_ok(self, commit_id: str, commit_version: int, step_id: str) -> bool:
        """§4.3 step 3 auto-block: a step resting on a DEMOTED rule premise
        (or a REJECTED goal) cannot execute — the agent cannot act on a dead
        belief."""
        rows = self.store.conn.execute(
            "SELECT member_kind, member_id FROM step_premise WHERE run_id=? AND commit_id=? "
            "AND commit_version=? AND step_id=?",
            (self.run_id, commit_id, commit_version, step_id)).fetchall()
        for r in rows:
            if r["member_kind"] == "RULE" and self.current_status("RULE", r["member_id"]) == "DEMOTED":
                return False
        return True

    def step_beats_used(self, step_id: str) -> int:
        return self.store.conn.execute(
            "SELECT COUNT(*) c FROM turn_record WHERE run_id=? AND commitment_step_id=?",
            (self.run_id, step_id)).fetchone()["c"]

    def next_executable_step(self, turn_id: int) -> tuple:
        """(step_row_or_None, flags). Walk the LATEST commitment's steps in
        order: consumed → next; blocked/aborted/expired anywhere → dead plan
        (None, recompile); activate the next pending step; enforce premise
        auto-block and the lease bound (§5.3)."""
        flags = {"lease_expired": False}
        c = self.store.conn
        com = c.execute(
            "SELECT commit_id, version, goal_id FROM commitment WHERE run_id=? "
            "ORDER BY created_turn DESC, commit_id DESC LIMIT 1", (self.run_id,)).fetchone()
        if not com:
            return None, flags
        if self.current_status("GOAL", com["goal_id"]) in ("ACCEPTED", "REJECTED"):
            return None, flags
        steps = c.execute(
            "SELECT * FROM commitment_step WHERE run_id=? AND commit_id=? AND commit_version=? "
            "ORDER BY step_ord", (self.run_id, com["commit_id"], com["version"])).fetchall()
        for s in steps:
            st = self.current_status("COMMITMENT_STEP", s["step_id"])
            if st == "CONSUMED":
                continue
            if st in ("BLOCKED", "ABORTED", "EXPIRED"):
                return None, flags
            if st != "ACTIVE":
                self.mark_step(s["step_id"], "ACTIVE", turn_id, "predecessor consumed")
            if not self.step_premises_ok(com["commit_id"], com["version"], s["step_id"]):
                self.mark_step(s["step_id"], "BLOCKED", turn_id, "premise demoted")
                return None, flags
            if self.step_beats_used(s["step_id"]) >= s["lease_max_beats"]:
                self.mark_step(s["step_id"], "EXPIRED", turn_id, "lease expired")
                flags["lease_expired"] = True
                return None, flags
            out = dict(s)
            out["goal_id"] = com["goal_id"]
            return out, flags
        return None, flags

    def consume_step(self, step: dict, turn_id: int, level_index: int = 0) -> None:
        """Consume-on-success (§4.3): advance the cursor; the goal's status
        machine moves with it — EXPLORED on first consumed step; VALIDATED when
        an INTERACT resting on a TESTED-rule premise confirms. A fully-consumed
        commitment DISTILLS into a Procedure (§5.4); a fully-consumed replay of
        a Procedure promotes it to TESTED within scope."""
        self.mark_step(step["step_id"], "CONSUMED", turn_id, "Executive-confirmed match")
        goal_id = step["goal_id"]
        st = self.current_status("GOAL", goal_id)
        if st == "PROPOSED":
            self._append_status(turn_id, "GOAL", goal_id, st, "EXPLORED", "first step consumed")
            st = "EXPLORED"
        if step["kind"] == "INTERACT" and st == "EXPLORED":
            has_rule = self.store.conn.execute(
                "SELECT 1 FROM step_premise WHERE run_id=? AND commit_id=? AND commit_version=? "
                "AND step_id=? AND member_kind='RULE' LIMIT 1",
                (self.run_id, step["commit_id"], step["commit_version"], step["step_id"])).fetchone()
            if has_rule:
                self._append_status(turn_id, "GOAL", goal_id, st, "VALIDATED",
                                    "tested-rule path confirmed")
        # §5.4: distill on full consume; one confirming REPLAY → TESTED in scope
        proc = self.procedure_of_commit(step["commit_id"])
        all_consumed = all(
            self.current_status("COMMITMENT_STEP", s["step_id"]) == "CONSUMED"
            for s in self.store.conn.execute(
                "SELECT step_id FROM commitment_step WHERE run_id=? AND commit_id=? AND "
                "commit_version=?", (self.run_id, step["commit_id"], step["commit_version"])))
        if all_consumed:
            if proc:
                cur = self.current_status("PROCEDURE", proc)
                if cur == "HYPOTHESIS":
                    self._append_status(turn_id, "PROCEDURE", proc, cur, "TESTED",
                                        "replay confirmed within scope")
            else:
                self.distill_procedure(step["commit_id"], step["commit_version"], goal_id,
                                       turn_id, level_index)

    # ---- experiments (§4.2): probes with pre-registered predictions ----
    def _effect_shape_ok(self, effect) -> bool:
        if not isinstance(effect, dict) or not effect or not set(effect) <= self.RULE_EFFECT_KEYS:
            return False
        cc = effect.get("cells_changed")
        if cc is not None and cc not in ("zero", "nonzero") and not isinstance(cc, int):
            return False
        return not any(effect.get(k) not in (None, 0, 1) for k in ("score_event", "level_event"))

    def add_experiment(self, turn_id: int, epoch_id: str, action: str, target: Optional[str],
                       predicted: dict, discriminates: list) -> str:
        exp_id = self.store.mint_id(self.run_id, "E", config.ID_WIDTH)
        self.store.conn.execute(
            "INSERT INTO experiment (run_id, exp_id, version, proposed_turn, epoch_id, target_ref, "
            "action, predicted_delta_json, discriminates_json) VALUES (?,?,1,?,?,?,?,?,?)",
            (self.run_id, exp_id, turn_id, epoch_id, target, action,
             json.dumps(predicted), json.dumps(discriminates)))
        self._append_status(turn_id, "EXPERIMENT", exp_id, None, "PROPOSED", "surveyor experiment")
        return exp_id

    def next_experiment(self, available: set) -> Optional[dict]:
        rows = self.store.conn.execute(
            "SELECT exp_id, action, target_ref, predicted_delta_json FROM experiment WHERE run_id=? "
            "ORDER BY exp_id", (self.run_id,)).fetchall()
        for r in rows:
            if self.current_status("EXPERIMENT", r["exp_id"]) != "PROPOSED":
                continue
            if r["action"] in available:
                return {"exp_id": r["exp_id"], "action": r["action"], "target": r["target_ref"],
                        "predicted": json.loads(r["predicted_delta_json"])}
        return None

    def mark_experiment_done(self, exp_id: str, turn_id: int) -> None:
        self._append_status(turn_id, "EXPERIMENT", exp_id, "PROPOSED", "DONE", "receipt written")

    def counterexample_buckets(self) -> str:
        """Mechanical per-rule mismatch aggregation for the Surveyor (§4.2)."""
        rows = self.store.conn.execute(
            "SELECT predictor_id, COUNT(*) n FROM consequence_record WHERE run_id=? AND match=0 "
            "AND predictor_kind='RULE' GROUP BY predictor_id ORDER BY n DESC", (self.run_id,)).fetchall()
        if not rows:
            return "(none)"
        return "; ".join(f"{r['predictor_id']}: {r['n']} mismatches" for r in rows[:12])

    # ---- context regimes (per level): base class + divergence minting ----
    def current_context_class(self, level_index: int, turn_id: int) -> str:
        """The CURRENT regime for this level = the latest-minted class; a base
        class CC-L{n} is minted on first use. Receipts land in the current
        regime; LEARN-ACTIONS quantifies over live (= current) classes."""
        row = self.store.conn.execute(
            "SELECT context_class_id FROM context_class WHERE run_id=? AND level_index=? "
            "ORDER BY minted_turn DESC, context_class_id DESC LIMIT 1",
            (self.run_id, level_index)).fetchone()
        if row:
            return row["context_class_id"]
        cc_id = f"CC-L{level_index}"
        self.store.conn.execute(
            "INSERT INTO context_class (run_id, context_class_id, action_id, partition_signature, "
            "minted_turn, level_index) VALUES (?,?,NULL,'base',?,?)",
            (self.run_id, cc_id, turn_id, level_index))
        return cc_id

    def maybe_diverge_context(self, action: str, cells_changed: int, level_index: int,
                              turn_id: int) -> Optional[str]:
        """§2.2 divergence: when an action's observed delta mismatches every
        receipt for (action, current class) — bucketed zero/nonzero so innocuous
        magnitude variation never mints — mint a NEW class (the new regime).
        The fresh class flips LEARN-ACTIONS false → the goal reopens (§3.4)."""
        cur = self.current_context_class(level_index, turn_id)
        bucket = "zero" if cells_changed == 0 else "nonzero"
        rows = self.store.conn.execute(
            "SELECT observed_delta_json FROM consequence_record WHERE run_id=? AND action=? "
            "AND context_class_id=? AND observed_delta_json IS NOT NULL",
            (self.run_id, action, cur)).fetchall()
        if not rows:
            return None
        seen = set()
        for r in rows:
            try:
                n = json.loads(r["observed_delta_json"]).get("cells_changed", 0)
            except (ValueError, TypeError):
                continue
            seen.add("zero" if n == 0 else "nonzero")
        if bucket not in seen:
            return self.mint_context_class(
                int(action[-1]) if action.startswith("ACTION") else None,
                f"diverge:{action}:{bucket}", turn_id, level_index)
        return None

    # ================= M5: the thesis engine =================

    # ---- consequence-grounded rule status (§2.3; consequence-grounding fix) ----
    def add_rule(self, turn_id: int, template: str, ctx_pred: dict, effect_pattern: dict,
                 scope: str = "UNKNOWN", test_plan: Optional[str] = None) -> str:
        rule_id = self.store.mint_id(self.run_id, "RU", config.ID_WIDTH)
        self.store.conn.execute(
            "INSERT INTO rule (run_id, rule_id, version, template, ctx_pred_json, "
            "effect_pattern_json, scope, ttl_turn, test_plan, created_turn) "
            "VALUES (?,?,1,?,?,?,?,?,?,?)",
            (self.run_id, rule_id, template, json.dumps(ctx_pred), json.dumps(effect_pattern),
             scope, None, test_plan, turn_id))
        self._append_status(turn_id, "RULE", rule_id, None, "HYPOTHESIS", "proposed")
        return rule_id

    def rule_support_mismatch(self, rule_id: str) -> tuple:
        """Support/mismatch counting ONLY the rule's OWN pre-registered receipts
        with turn_id > created_turn. A retrospective or ctx-only receipt
        (predictor_id NULL) never promotes a rule — the consequence-grounding
        invariant (a referent can reach CHARACTERIZED only via a prediction
        pre-registered BEFORE acting and matched by code)."""
        created = self.store.conn.execute(
            "SELECT MIN(created_turn) t FROM rule WHERE run_id=? AND rule_id=?",
            (self.run_id, rule_id)).fetchone()["t"] or 0
        rows = self.store.conn.execute(
            "SELECT match, turn_id FROM consequence_record WHERE run_id=? AND predictor_id=? "
            "AND predictor_kind='RULE'", (self.run_id, rule_id)).fetchall()
        support = sum(1 for r in rows if r["match"] == 1 and r["turn_id"] > created)
        mismatch = sum(1 for r in rows if r["match"] == 0 and r["turn_id"] > created)
        return support, mismatch

    def recompute_rule_status(self, rule_id: str, turn_id: int) -> str:
        """Promotion needs support ≥ k with mismatch ratio < θ; demotion needs
        K mismatches (§2.3 — 'mismatches beyond K demote back'; θ governs
        promotion only, so TESTED is sticky until actually contradicted)."""
        support, mismatch = self.rule_support_mismatch(rule_id)
        total = support + mismatch
        cur = self.current_status("RULE", rule_id) or "HYPOTHESIS"
        if not config.CONSEQ_ON and cur == "HYPOTHESIS":
            # A4 (ARG_CONSEQ=0): consequence gating disabled — assertions
            # promote without receipts; the anti-cascade invariant is OFF.
            self._append_status(turn_id, "RULE", rule_id, cur, "TESTED", "A4: appearance promotes")
            return "TESTED"
        if mismatch >= config.K_DEMOTE:
            new = "DEMOTED"
        elif support >= config.K_SUPPORT and (mismatch / total if total else 0) < config.THETA:
            new = "TESTED"
        elif cur == "TESTED":
            new = "TESTED"
        else:
            new = "HYPOTHESIS"
        if new != cur:
            self._append_status(turn_id, "RULE", rule_id, cur, new,
                                f"support={support} mismatch={mismatch}")
        return new

    def recompute_rung(self, ref_id: str, turn_id: int) -> str:
        """ANCHORED → ENGAGED (≥1 consequence with this ref in scope, incl. null
        effect) → CHARACTERIZED (referenced by ≥1 TESTED-rule matched receipt).
        Appearance never grounds mechanism (§2.3)."""
        c = self.store.conn
        # CHARACTERIZED: a matched receipt whose predictor is a currently-TESTED rule targets this ref
        if config.CONSEQ_ON:
            char = c.execute(
                "SELECT cr.predictor_id FROM consequence_record cr WHERE cr.run_id=? AND cr.target_ref=? "
                "AND cr.predictor_kind='RULE' AND cr.match=1", (self.run_id, ref_id)).fetchall()
            is_char = any(self.current_status("RULE", r["predictor_id"]) == "TESTED" for r in char)
        else:
            # A4: appearance grounds — any rule receipt characterizes
            is_char = bool(c.execute(
                "SELECT 1 FROM consequence_record WHERE run_id=? AND target_ref=? AND "
                "predictor_kind='RULE' LIMIT 1", (self.run_id, ref_id)).fetchone())
        engaged = False
        if not is_char:
            for row in c.execute(
                    "SELECT observed_delta_json, target_ref FROM consequence_record WHERE run_id=?",
                    (self.run_id,)):
                if row["target_ref"] == ref_id:
                    engaged = True
                    break
                od = row["observed_delta_json"]
                if od and ref_id in od:   # ref appears in bound/minted of the observed delta
                    engaged = True
                    break
        new = "CHARACTERIZED" if is_char else ("ENGAGED" if engaged else "ANCHORED")
        cur = self.current_status("REFERENT_RUNG", ref_id) or "ANCHORED"
        if RUNG_ORDER.get(new, 1) > RUNG_ORDER.get(cur, 1):   # rungs climb; demotion is via fission
            self._append_status(turn_id, "REFERENT_RUNG", ref_id, cur, new, "recomputed")
        return new

    # ---- goal admission: the six gates (§3.3) ----
    def live_goals(self) -> list:
        c = self.store.conn
        rows = c.execute(
            "SELECT goal_id FROM goal WHERE run_id=? AND version=(SELECT MAX(version) FROM goal g2 "
            "WHERE g2.run_id=goal.run_id AND g2.goal_id=goal.goal_id)", (self.run_id,)).fetchall()
        out = []
        for r in rows:
            st = self.current_status("GOAL", r["goal_id"])
            if st not in ("REJECTED", "ACCEPTED"):
                out.append(r["goal_id"])
        return out

    def _sum_live_bindings(self) -> int:
        live = self.live_goals()
        if not live:
            return 0
        qs = ",".join("?" * len(live))
        return self.store.conn.execute(
            f"SELECT COUNT(*) n FROM goal_binding WHERE run_id=? AND goal_id IN ({qs})",
            (self.run_id, *live)).fetchone()["n"]

    def admit_goal(self, proposal: dict, turn_id: int, parent: Optional[str] = None,
                   ctx: Optional[dict] = None) -> dict:
        """Six admission gates. An intention is admissible exactly when it is
        checkable; inadmissible intentions are inexpressible, not discouraged."""
        channels = self.adapter.signal_channels()
        bindings = proposal.get("bindings", [])
        roster = {r["ref_id"] for r in self.current_referents_with_cells()}
        # gate 1 — referential closure (root G0 waived)
        if parent is not None:
            for ref in bindings:
                if ref not in roster:
                    return {"ok": False, "reason": "GATE1_UNRESOLVED_BINDING", "ref": ref}
        test = proposal.get("achievement_test")
        # gate 2 — mechanical test compiles & is evaluable now (false, not error)
        ok, why = predicates.compiles(test, channels)
        if not ok:
            return {"ok": False, "reason": "GATE2_TEST_INCOMPILABLE", "detail": why}
        # gate 2, A3 (2026-07-17): the test must evaluate FALSE at admission —
        # a test already true buys no information (achievement without work;
        # batch-4: "confirm RU demoted" trio auto-ACCEPTED on admission). With
        # no signals ctx supplied, record-quantified truths still evaluate
        # against the store, which is where the live pollution came from.
        ectx = ctx or {"cur": {}, "prev": {}}
        if predicates.eval_now(test, ectx, self._record_eval_factory(ectx)):
            return {"ok": False, "reason": "GATE2_TRUE_AT_ADMISSION"}
        # gate 3 — discriminator present
        if not proposal.get("discriminator"):
            return {"ok": False, "reason": "GATE3_NO_DISCRIMINATOR"}
        # gate 4 — non-duplication + anti-oscillation
        if self._duplicate_live_test(test):
            return {"ok": False, "reason": "GATE4_DUPLICATE_SIBLING"}
        anti = self._anti_oscillation_ok(test, proposal.get("evidence_ptrs", []))
        if not anti:
            return {"ok": False, "reason": "GATE4_ANTI_OSCILLATION"}
        # gate 5 — provenance + budget
        if not proposal.get("evidence_ptrs") and parent is not None:
            return {"ok": False, "reason": "GATE5_NO_EVIDENCE"}
        # gate 6 — binding-budget admission (Σ|bindings| ≤ N_max)
        if self._sum_live_bindings() + len(bindings) > config.N_MAX_BINDINGS:
            return {"ok": False, "reason": "GATE6_BINDING_BUDGET"}
        # admit
        goal_id = self.store.mint_id(self.run_id, "G", config.ID_WIDTH)
        reopen = predicates.classify_reopen(test)
        budget = proposal.get("budget_actions", config.MAX_ACTIONS)
        # a milestone-SHAPED test (names a rule to be receipted/TESTED) is an
        # experiment whatever its provenance — its budget scales with the
        # promotion bar, not the run (gen4: a Surveyor-proposed milestone
        # inherited the 400-action default and burned 336 beats)
        if self._milestone_rule_of(test) is not None:
            budget = min(budget, max(8, 6 * config.K_SUPPORT))
        self.store.conn.execute(
            "INSERT INTO goal (run_id, goal_id, version, parent_goal, statement, "
            "achievement_test_json, discriminator_json, reopen_class, budget_actions, "
            "budget_search_calls, provenance, admitted_turn, created_turn) "
            "VALUES (?,?,1,?,?,?,?,?,?,?,?,?,?)",
            (self.run_id, goal_id, parent, proposal.get("statement", ""), json.dumps(test),
             json.dumps(proposal["discriminator"]), reopen, budget,
             proposal.get("budget_search_calls", config.SURVEYOR_CALLS_PER_EPOCH),
             proposal.get("provenance", "SURVEYOR"), turn_id, turn_id))
        for ref in bindings:
            self.store.conn.execute(
                "INSERT INTO goal_binding (run_id, goal_id, goal_version, ref_id) VALUES (?,?,1,?)",
                (self.run_id, goal_id, ref))
        self._append_status(turn_id, "GOAL", goal_id, None, "PROPOSED", "admitted")
        return {"ok": True, "goal_id": goal_id, "reopen_class": reopen}

    def _duplicate_live_test(self, test: dict) -> bool:
        tj = json.dumps(test, sort_keys=True)
        for gid in self.live_goals():
            row = self.store.conn.execute(
                "SELECT achievement_test_json FROM goal WHERE run_id=? AND goal_id=? "
                "ORDER BY version DESC LIMIT 1", (self.run_id, gid)).fetchone()
            if row and json.dumps(json.loads(row["achievement_test_json"]), sort_keys=True) == tj:
                return True
        return False

    def _anti_oscillation_ok(self, test: dict, evidence_ptrs: list) -> bool:
        """Re-proposal of a goal REJECTED as NEVER_VALIDATED needs evidence
        post-dating the rejection (§3.3 gate 4 / §5.3 reuse)."""
        tj = json.dumps(test, sort_keys=True)
        rej = self.store.conn.execute(
            "SELECT g.goal_id, MAX(st.turn_id) rt FROM goal g JOIN status_transition st "
            "  ON st.run_id=g.run_id AND st.entity_kind='GOAL' AND st.entity_id=g.goal_id "
            "WHERE g.run_id=? AND st.to_status='REJECTED' AND st.reason='NEVER_VALIDATED' "
            "GROUP BY g.goal_id", (self.run_id,)).fetchall()
        for r in rej:
            row = self.store.conn.execute(
                "SELECT achievement_test_json FROM goal WHERE run_id=? AND goal_id=? "
                "ORDER BY version DESC LIMIT 1", (self.run_id, r["goal_id"])).fetchone()
            if row and json.dumps(json.loads(row["achievement_test_json"]), sort_keys=True) == tj:
                # must cite evidence with turn_id > rejection turn_id
                fresh = any(self._evidence_turn(e) > r["rt"] for e in evidence_ptrs)
                if not fresh:
                    return False
        return True

    def _evidence_turn(self, ptr: Any) -> int:
        try:
            return int(ptr)
        except (ValueError, TypeError):
            return 0

    # ---- Executive-computed rank (§5.3) ----
    def compute_rank(self, parent: Optional[str]) -> dict:
        """Deterministic sibling order: verified-edge-into-a-live-parent FIRST
        (§5.3 rank key #1 — children order before the parents they serve), then
        status precedence (REOPENED/PROPOSED ahead of ACCEPTED), then remaining
        budget desc, then id. Returns {order:[gid...], equal_siblings:{gid:[peers]}}.
        Rank is Executive state, never LLM-written — §4.3's tree walk is literal."""
        c = self.store.conn
        rows = c.execute(
            "SELECT goal_id, budget_actions FROM goal WHERE run_id=? AND "
            "(parent_goal IS ? OR parent_goal=?) AND version=(SELECT MAX(version) FROM goal g2 "
            "WHERE g2.run_id=goal.run_id AND g2.goal_id=goal.goal_id)",
            (self.run_id, parent, parent)).fetchall()
        prec = {"REOPENED": 0, "PROPOSED": 1, "EXPLORED": 2, "VALIDATED": 3, "ACCEPTED": 5,
                "REJECTED": 6}

        def fills_live_parent(gid: str) -> bool:
            for r in c.execute("SELECT parent_goal FROM goal_edge WHERE run_id=? AND "
                               "child_goal=? AND verified=1", (self.run_id, gid)):
                pst = self.current_status("GOAL", r["parent_goal"]) or "PROPOSED"
                if pst not in ("ACCEPTED", "REJECTED", "NEVER_VALIDATED"):
                    return True
            return False

        def key(g):
            st = self.current_status("GOAL", g["goal_id"]) or "PROPOSED"
            return (0 if fills_live_parent(g["goal_id"]) else 1,
                    prec.get(st, 4), -(g["budget_actions"] or 0), g["goal_id"])
        ordered = sorted(rows, key=key)
        order = [g["goal_id"] for g in ordered]
        equal: dict = {}
        for i, g in enumerate(ordered):
            peers = [h["goal_id"] for h in ordered
                     if h["goal_id"] != g["goal_id"] and key(h)[:3] == key(g)[:3]]
            if peers:
                equal[g["goal_id"]] = peers
        return {"order": order, "equal_siblings": equal}

    # ---- achievement-test evaluation + status machine (§3.4, B6) ----
    def _record_eval_factory(self, ctx: dict):
        """record_eval for LEARN_*/COUNT/EXISTS — the universal quantifiers.
        LEARN_ACTIONS quantifies over the CURRENT level's live context classes
        and over the actions the environment actually OFFERS (Q11's per-game
        action-interface reality: an action never made available cannot be
        learned; ls20-class games expose subsets of the fixed vocabulary)."""
        level = (ctx.get("cur") or {}).get("levels_completed", 0) or 0
        available = (ctx.get("cur") or {}).get("available")

        def ev(node: dict) -> bool:
            op = node.get("op")
            if op == "LEARN_ACTIONS":
                return self._learn_actions_satisfied(level, available)
            if op == "LEARN_RULES":
                return self._learn_rules_satisfied()
            if op == "LEARN_ENV":
                return self._learn_env_satisfied()
            if op in ("COUNT", "EXISTS"):
                n = self._count_entity(node)
                if op == "EXISTS":
                    return n > 0
                v = node.get("value", 1)
                cmpop = node.get("cmp", "GE")
                return n >= v if cmpop == "GE" else (n > v if cmpop == "GT" else n == v)
            if op == "RULE_STATUS":
                return (self.current_status("RULE", node.get("rule", "")) or "HYPOTHESIS") \
                    == node.get("is")
            if op == "RUNG":
                cur = self.current_status("REFERENT_RUNG", node.get("ref", "")) or "ANCHORED"
                return RUNG_ORDER.get(cur, 1) >= RUNG_ORDER.get(node.get("at_least"), 1)
            return False
        return ev

    def _live_context_classes(self, level_index: int) -> list:
        """LIVE = the current regime: the latest-minted class for this level.
        Superseded regimes are unrevisitable, so quantifying over them would
        wedge LEARN-ACTIONS permanently false (§3.2 narrowing, documented)."""
        row = self.store.conn.execute(
            "SELECT context_class_id FROM context_class WHERE run_id=? AND level_index=? "
            "ORDER BY minted_turn DESC, context_class_id DESC LIMIT 1",
            (self.run_id, level_index)).fetchone()
        return [row["context_class_id"]] if row else []

    def _learn_actions_satisfied(self, level_index: int = 0,
                                 available: Optional[list] = None) -> bool:
        """Every OFFERED action has ≥1 consequence in EVERY live context class
        (effect or verified no-op). `available` = the environment's current
        action interface; None falls back to the full fixed vocabulary. A
        freshly minted context class flips this false → reopens (§3.4)."""
        c = self.store.conn
        actions = list(available) if available else \
            [s["action"] for s in self.adapter.action_vocab()]
        if not actions:
            return False
        classes = self._live_context_classes(level_index)
        if not classes:
            return False
        for a in actions:
            for cc in classes:
                hit = c.execute(
                    "SELECT 1 FROM consequence_record WHERE run_id=? AND action=? AND context_class_id=? LIMIT 1",
                    (self.run_id, a, cc)).fetchone()
                if not hit:
                    return False
        return True

    def _learn_rules_satisfied(self) -> bool:
        # every referent that changed participates in ≥1 TESTED rule (simplified)
        tested = self.store.conn.execute(
            "SELECT COUNT(*) n FROM rule r WHERE r.run_id=? AND EXISTS "
            "(SELECT 1 FROM status_transition s WHERE s.run_id=r.run_id AND s.entity_kind='RULE' "
            " AND s.entity_id=r.rule_id AND s.to_status='TESTED' AND s.seq=(SELECT MAX(seq) "
            "  FROM status_transition s2 WHERE s2.run_id=s.run_id AND s2.entity_id=s.entity_id))",
            (self.run_id,)).fetchone()["n"]
        changed = self.store.conn.execute(
            "SELECT COUNT(DISTINCT target_ref) n FROM consequence_record WHERE run_id=? "
            "AND target_ref IS NOT NULL", (self.run_id,)).fetchone()["n"]
        return tested > 0 and tested >= changed

    def _learn_env_satisfied(self) -> bool:
        total = self.store.conn.execute(
            "SELECT COUNT(DISTINCT ref_id) n FROM referent WHERE run_id=?", (self.run_id,)).fetchone()["n"]
        engaged = self.store.conn.execute(
            "SELECT COUNT(DISTINCT target_ref) n FROM consequence_record WHERE run_id=? "
            "AND target_ref IS NOT NULL", (self.run_id,)).fetchone()["n"]
        return total > 0 and engaged >= total

    def _count_entity(self, node: dict) -> int:
        """COUNT/EXISTS over stamped rows with the CLOSED where vocabulary (A1)."""
        entity = node.get("entity")
        where = node.get("where") or {}
        c = self.store.conn
        if entity == "consequence":
            colmap = {"action": "action", "target": "target_ref", "match": "match",
                      "predictor": "predictor_id", "score_event": "score_event",
                      "level_event": "level_event", "context_class": "context_class_id"}
            conds, vals = ["run_id=?"], [self.run_id]
            for k, v in where.items():
                col = colmap.get(k)
                if col is None:
                    return 0
                conds.append(f"{col}=?")
                vals.append(1 if v is True else (0 if v is False else v))
            return c.execute(f"SELECT COUNT(*) n FROM consequence_record WHERE "
                             f"{' AND '.join(conds)}", vals).fetchone()["n"]
        if entity == "rule":
            want = where.get("status")
            n = 0
            for r in c.execute("SELECT DISTINCT rule_id FROM rule WHERE run_id=?", (self.run_id,)):
                st = self.current_status("RULE", r["rule_id"]) or "HYPOTHESIS"
                if want is None or st == want:
                    n += 1
            return n
        if entity == "referent":
            want = where.get("rung")
            n = 0
            for r in c.execute("SELECT DISTINCT ref_id FROM referent WHERE run_id=?", (self.run_id,)):
                rung = self.current_status("REFERENT_RUNG", r["ref_id"]) or "ANCHORED"
                if want is None or rung == want:
                    n += 1
            return n
        return 0

    def eval_goal(self, goal_id: str, ctx: dict) -> bool:
        row = self.store.conn.execute(
            "SELECT achievement_test_json FROM goal WHERE run_id=? AND goal_id=? "
            "ORDER BY version DESC LIMIT 1", (self.run_id, goal_id)).fetchone()
        if not row:
            return False
        test = json.loads(row["achievement_test_json"])
        return predicates.eval_now(test, ctx, self._record_eval_factory(ctx))

    def evaluate_all_goals(self, turn_id: int, ctx: dict) -> list:
        """B6: for every goal, evaluate its test. MONOTONE_TERMINAL latches once
        fired; RECORD_QUANTIFIED reopens when it later evaluates false. Returns
        the transitions taken."""
        c = self.store.conn
        transitions = []
        rows = c.execute(
            "SELECT goal_id, reopen_class FROM goal WHERE run_id=? AND version=(SELECT MAX(version) "
            "FROM goal g2 WHERE g2.run_id=goal.run_id AND g2.goal_id=goal.goal_id)",
            (self.run_id,)).fetchall()
        root = c.execute("SELECT goal_id FROM goal WHERE run_id=? AND parent_goal IS NULL "
                         "ORDER BY goal_id LIMIT 1", (self.run_id,)).fetchone()
        for r in rows:
            gid, reopen = r["goal_id"], r["reopen_class"]
            st = self.current_status("GOAL", gid)
            fired = self.eval_goal(gid, ctx)
            if st not in ("ACCEPTED", "REJECTED") and fired:
                self._append_status(turn_id, "GOAL", gid, st, "ACCEPTED", "test fired")
                transitions.append((gid, st, "ACCEPTED"))
                if root and gid == root["goal_id"]:
                    self.audit_progress_signals(turn_id, ctx)   # §3.2 test-the-test
            elif st == "ACCEPTED" and reopen == "RECORD_QUANTIFIED" and not fired:
                self._append_status(turn_id, "GOAL", gid, "ACCEPTED", "REOPENED", "record-quantified re-check")
                transitions.append((gid, "ACCEPTED", "REOPENED"))
        return transitions

    def mint_context_class(self, action_id: Optional[int], partition_signature: str,
                           turn_id: int, level_index: int) -> str:
        # §5.4: a context-class mint intersecting a Procedure's scope demotes
        # it — cheap to re-verify, forbidden to trust across regimes
        prev = self.store.conn.execute(
            "SELECT context_class_id FROM context_class WHERE run_id=? AND level_index=? "
            "ORDER BY minted_turn DESC, context_class_id DESC LIMIT 1",
            (self.run_id, level_index)).fetchone()
        if prev:
            for p in self.store.conn.execute(
                    "SELECT DISTINCT proc_id FROM procedure WHERE run_id=? AND scope_fingerprint=?",
                    (self.run_id, prev["context_class_id"])).fetchall():
                cur = self.current_status("PROCEDURE", p["proc_id"])
                if cur in ("HYPOTHESIS", "TESTED"):
                    self._append_status(turn_id, "PROCEDURE", p["proc_id"], cur, "DEMOTED",
                                        "context-class mint intersects scope")
        cc_id = self.store.mint_id(self.run_id, "CC", config.ID_WIDTH)
        self.store.conn.execute(
            "INSERT INTO context_class (run_id, context_class_id, action_id, partition_signature, "
            "minted_turn, level_index) VALUES (?,?,?,?,?,?)",
            (self.run_id, cc_id, action_id, partition_signature, turn_id, level_index))
        return cc_id

    # ---- M6: NAVIGATE bootstrap + earned `controllable` (§2.2) ----
    def learn_from_movement(self, action: str, prev_grid: list, curr_grid: list,
                            turn_id: int) -> Optional[tuple]:
        """Record the single-mover delta AND earn the mover's `controllable`
        annotation: movement-command ↔ correlated self-diff receipts, exactly
        like any Rule — HYPOTHESIS on first observation, TESTED at k (§2.2)."""
        hit = pather.learn_action_model(self.store, self.run_id, self.adapter, action,
                                        prev_grid, curr_grid, turn_id,
                                        targeted=self._targeted)
        if hit is None:
            return None
        _, sig = hit
        for r in self.current_referents_with_cells():
            if r["signature"] == sig:
                self._recompute_controllable(r["ref_id"], sig, turn_id)
                break
        return hit

    def _recompute_controllable(self, ref_id: str, sig: str, turn_id: int) -> str:
        n = self.store.conn.execute(
            "SELECT COUNT(*) c FROM action_model WHERE run_id=? AND mover_sig=?",
            (self.run_id, sig)).fetchone()["c"]
        cur = self.current_status("REFERENT_CONTROLLABLE", ref_id)
        new = "TESTED" if n >= config.K_SUPPORT else "HYPOTHESIS"
        if new != cur:
            self._append_status(turn_id, "REFERENT_CONTROLLABLE", ref_id, cur, new,
                                f"movement observations={n}")
        return new

    def controllable_ref(self) -> Optional[str]:
        """The current TESTED (else HYPOTHESIS) controllable referent."""
        best = None
        for row in self.store.conn.execute(
                "SELECT entity_id, to_status FROM status_transition st WHERE run_id=? AND "
                "entity_kind='REFERENT_CONTROLLABLE' AND st.seq=(SELECT MAX(seq) FROM "
                "status_transition s2 WHERE s2.run_id=st.run_id AND s2.entity_id=st.entity_id "
                "AND s2.entity_kind='REFERENT_CONTROLLABLE')", (self.run_id,)):
            if row["to_status"] == "TESTED":
                return row["entity_id"]
            if row["to_status"] == "HYPOTHESIS" and best is None:
                best = row["entity_id"]
        return best

    def mover_centroid(self) -> Optional[tuple]:
        """The controllable referent's centroid (earned, §2.2); bootstrap
        fallback = the smallest current referent."""
        ctrl = self.controllable_ref()
        refs = self.current_referents_with_cells()
        if not refs:
            return None
        chosen = next((r for r in refs if r["ref_id"] == ctrl), None)
        if chosen is None:
            refs.sort(key=lambda r: len(r["cells"]))
            chosen = refs[0]
        cells = chosen["cells"]
        n = len(cells) or 1
        return (round(sum(c[0] for c in cells) / n), round(sum(c[1] for c in cells) / n))

    # ---- D1: scope across deaths (§2.2) + the G0 test-the-test audit (§3.2) ----
    def death_turns(self) -> list:
        return [r["turn_id"] for r in self.store.conn.execute(
            "SELECT DISTINCT turn_id FROM consequence_record WHERE run_id=? AND life_event=1 "
            "ORDER BY turn_id", (self.run_id,))]

    def rule_scope(self, rule_id: str) -> str:
        """Computed scope: effects observed to survive a life-loss earn
        PERSISTENT; effects that vanish after one earn WITHIN_LIFE; UNKNOWN
        until a death crosses them (§2.2)."""
        deaths = self.death_turns()
        if not deaths:
            return "UNKNOWN"
        rows = self.store.conn.execute(
            "SELECT turn_id, match FROM consequence_record WHERE run_id=? AND predictor_id=? "
            "AND match IS NOT NULL ORDER BY turn_id", (self.run_id, rule_id)).fetchall()
        matches = [r["turn_id"] for r in rows if r["match"] == 1]
        mismatches = [r["turn_id"] for r in rows if r["match"] == 0]
        if not matches:
            return "UNKNOWN"
        for d in deaths:
            if any(t < d for t in matches) and any(t > d for t in matches):
                return "PERSISTENT"
        last_death = deaths[-1]
        if all(t < last_death for t in matches) and any(t > last_death for t in mismatches):
            return "WITHIN_LIFE"
        return "UNKNOWN"

    def audit_progress_signals(self, turn_id: int, ctx: dict) -> dict:
        """§3.2 test-the-test: when the root goal's disjunctive test fires,
        record which progress signals actually moved — a quarantined audit row
        the health probe surfaces, so a mis-keyed predicate is a printed fact."""
        cur, prev = ctx.get("cur", {}), ctx.get("prev", {})
        audit = {
            "score": 1 if (cur.get("score") or 0) > (prev.get("score") or 0) else 0,
            "level": 1 if (cur.get("levels_completed") or 0) > (prev.get("levels_completed") or 0) else 0,
            "win": 1 if cur.get("state") == "WIN" else 0,
        }
        seq = self.store.next_seq(self.run_id, "annotate")
        self.store.conn.execute(
            "INSERT INTO annotate (run_id, seq, turn_id, text) VALUES (?,?,?,?)",
            (self.run_id, seq, turn_id, "G0-AUDIT " + json.dumps(audit)))
        return audit

    def compile_navigate(self, target_ref: str, mover_centroid: Optional[tuple] = None) -> Optional[dict]:
        """Compile a NAVIGATE plan toward a target referent using the learned
        action model. Returns {steps:[...], reach} or None (→ Z4 probe). Each
        NAVIGATE carries an arrival handoff: a `then:` INTERACT slot, since
        reaching a referent and interacting with it are separate phases."""
        deltas = pather.action_deltas(self.store, self.run_id)
        if not deltas:
            return None
        mover = mover_centroid or self.mover_centroid()
        if mover is None:
            return None
        tgt = None
        for r in self.current_referents_with_cells():
            if r["ref_id"] == target_ref:
                tgt = r["bbox"]
                break
        if tgt is None:
            return None
        path = pather.route(deltas, mover, tgt)
        if path is None:
            return None
        # NAVIGATE steps predict a nonzero delta (the mover moves) so they are
        # consumable on Executive-confirmed match (§4.3 consume-on-success)
        steps = [{"kind": "NAVIGATE", "action": a, "target_ref": target_ref,
                  "predicted": {"cells_changed": "nonzero"}} for a in path]
        steps.append({"kind": "INTERACT", "action": None, "target_ref": target_ref,
                      "then": True, "predicted": {"cells_changed": "nonzero"}})   # arrival handoff
        return {"steps": steps, "reach": "route", "target_ref": target_ref}

    def write_commitment(self, goal_id: str, steps: list, turn_id: int,
                         premise_rules: Optional[list] = None,
                         procedure_id: Optional[str] = None) -> str:
        """Compile-time stamping per §4.3 step 3: each step carries its
        compilation turn_id, its predicted_delta, and its premise closure —
        the machine-recorded set {cited rules ∪ goal bindings ∪ target refs}
        the §5.3 Revision-Evidence gate consumes. Step 0 goes ACTIVE."""
        commit_id = self.store.mint_id(self.run_id, "C", config.ID_WIDTH)
        c = self.store.conn
        c.execute("INSERT INTO commitment (run_id, commit_id, version, goal_id, compiled_turn, "
                  "procedure_id, created_turn) VALUES (?,?,1,?,?,?,?)",
                  (self.run_id, commit_id, goal_id, turn_id, procedure_id, turn_id))
        bindings = [r["ref_id"] for r in c.execute(
            "SELECT DISTINCT ref_id FROM goal_binding WHERE run_id=? AND goal_id=?",
            (self.run_id, goal_id))]
        for i, st in enumerate(steps):
            step_id = f"{commit_id}-S{i}"
            c.execute(
                "INSERT INTO commitment_step (run_id, commit_id, commit_version, step_id, step_ord, "
                "kind, target_ref, action, param_schema_json, predicted_delta_json, then_slot_step, "
                "precond_json, compilation_turn_id, lease_max_beats) VALUES (?,?,1,?,?,?,?,?,?,?,?,?,?,?)",
                (self.run_id, commit_id, step_id, i, st["kind"], st.get("target_ref"),
                 st.get("action"), "{}",
                 json.dumps(st["predicted"]) if st.get("predicted") is not None else None,
                 None, json.dumps({"rules_tested": premise_rules or []}), turn_id,
                 config.LEASE_MAX_BEATS))
            members = {("RULE", rid) for rid in (premise_rules or [])}
            members |= {("GOAL_BINDING", b) for b in bindings}
            if st.get("target_ref"):
                members.add(("TARGET_REF", st["target_ref"]))
            for kind, mid in sorted(members):
                c.execute(
                    "INSERT OR IGNORE INTO step_premise (run_id, commit_id, commit_version, step_id, "
                    "member_kind, member_id) VALUES (?,?,1,?,?,?)",
                    (self.run_id, commit_id, step_id, kind, mid))
        if steps:
            self.mark_step(f"{commit_id}-S0", "ACTIVE", turn_id, "compiled")
        return commit_id

    # ---- M9: cross-run carryover ----
    def import_prior_rules(self, prior_db_path: str, turn_id: int) -> int:
        """Cross-run carryover (§2.4.6): a prior run's TESTED rules re-enter this
        run as fresh v1 HYPOTHESIS with prior_support noted — hypotheses to
        re-test cheaply, never facts to trust (the converting fix went 0/16 on
        the next level). ARG transfers its way of binding, never its bindings."""
        import sqlite3
        try:
            pc = sqlite3.connect(f"file:{prior_db_path}?mode=ro", uri=True)
            pc.row_factory = sqlite3.Row
        except sqlite3.Error:
            return 0
        prior_run = pc.execute("SELECT run_id FROM run ORDER BY started_at DESC LIMIT 1").fetchone()
        if not prior_run:
            return 0
        prun = prior_run["run_id"]
        rules = pc.execute(
            "SELECT rule_id, template, ctx_pred_json, effect_pattern_json, scope FROM rule r "
            "WHERE r.run_id=? AND EXISTS (SELECT 1 FROM status_transition s WHERE s.run_id=r.run_id "
            "AND s.entity_kind='RULE' AND s.entity_id=r.rule_id AND s.to_status='TESTED' AND "
            "s.seq=(SELECT MAX(seq) FROM status_transition s2 WHERE s2.run_id=s.run_id AND "
            "s2.entity_id=s.entity_id))", (prun,)).fetchall()
        n = 0
        for r in rules:
            support = pc.execute(
                "SELECT COUNT(*) c FROM consequence_record WHERE run_id=? AND predictor_id=? AND match=1",
                (prun, r["rule_id"])).fetchone()["c"]
            new_id = self.store.mint_id(self.run_id, "RU", config.ID_WIDTH)
            self.store.conn.execute(
                "INSERT INTO rule (run_id, rule_id, version, template, ctx_pred_json, "
                "effect_pattern_json, scope, ttl_turn, test_plan, created_turn) VALUES (?,?,1,?,?,?,?,?,?,?)",
                (self.run_id, new_id, r["template"], r["ctx_pred_json"], r["effect_pattern_json"],
                 r["scope"], None, "carryover-retest", turn_id))
            self._append_status(turn_id, "RULE", new_id, None, "HYPOTHESIS",
                                f"carryover from {prun[:8]} (prior_support={support})")
            seq = self.store.next_seq(self.run_id, "seed_import")
            self.store.conn.execute(
                "INSERT INTO seed_import (run_id, seq, prior_run_id, imported_rule_id, new_rule_id, "
                "prior_support, imported_turn) VALUES (?,?,?,?,?,?,?)",
                (self.run_id, seq, prun, r["rule_id"], new_id, support, turn_id))
            n += 1
        pc.close()
        self.store.commit()
        return n

    def inflate_store(self, factor: int, turn_id: int) -> int:
        """A11 stress: synthesize ~factor× referents to prove render size is
        O(working set), never O(store). Test-only."""
        base = self.store.conn.execute(
            "SELECT COUNT(*) c FROM referent WHERE run_id=?", (self.run_id,)).fetchone()["c"]
        target = base * factor
        made = 0
        while self.store.conn.execute("SELECT COUNT(*) c FROM referent WHERE run_id=?",
                                      (self.run_id,)).fetchone()["c"] < target:
            x = 10 + (made % 50)
            self.mint_referent(Component(color=(made % 9) + 1, cells=frozenset([(x, 20)]),
                                         bbox=(x, 20, x, 20), centroid=(x, 20), size=1,
                                         shape=frozenset([(0, 0)])), turn_id)
            made += 1
            if made > 2000:
                break
        self.store.commit()
        return made

    # ===== D3: relation lifecycle, Procedures §5.4, FISSION EXECUTE, compaction =====

    def recompute_sameas_status(self, rel_id: str, turn_id: int) -> str:
        """same_as is mechanically testable (§2.6.2): co-presence of src and
        dst in one beat REFUTES identity (mismatch); k alternating appearances
        with zero co-presence support it. TESTED → a MERGE_CANONICAL lineage
        row (both ids preserved, the older canonical)."""
        row = self.store.conn.execute(
            "SELECT verb, src_ref, dst_ref FROM relation WHERE run_id=? AND rel_id=? "
            "ORDER BY version DESC LIMIT 1", (self.run_id, rel_id)).fetchone()
        if not row or row["verb"] != "same_as":
            return self.current_status("RELATION", rel_id) or "HYPOTHESIS"
        src_turns = {r["turn_id"] for r in self.store.conn.execute(
            "SELECT DISTINCT turn_id FROM binding_record WHERE run_id=? AND bound_to=?",
            (self.run_id, row["src_ref"]))}
        dst_turns = {r["turn_id"] for r in self.store.conn.execute(
            "SELECT DISTINCT turn_id FROM binding_record WHERE run_id=? AND bound_to=?",
            (self.run_id, row["dst_ref"]))}
        co = len(src_turns & dst_turns)
        cur = self.current_status("RELATION", rel_id) or "HYPOTHESIS"
        if co >= config.K_DEMOTE:
            new = "DEMOTED"
        elif co == 0 and len(src_turns) >= config.K_SUPPORT and len(dst_turns) >= config.K_SUPPORT:
            new = "TESTED"
        else:
            new = cur
        if new != cur:
            self._append_status(turn_id, "RELATION", rel_id, cur, new,
                                f"co_presence={co} src_n={len(src_turns)} dst_n={len(dst_turns)}")
            if new == "TESTED":
                canonical, child = sorted([row["src_ref"], row["dst_ref"]])
                seq = self.store.next_seq(self.run_id, "referent_lineage")
                self.store.conn.execute(
                    "INSERT INTO referent_lineage (run_id, seq, turn_id, op, parent_ref, child_ref) "
                    "VALUES (?,?,?,?,?,?)",
                    (self.run_id, seq, turn_id, "MERGE_CANONICAL", canonical, child))
        return new

    def sweep_relations(self, turn_id: int) -> None:
        """Relation lifecycle sweep: same_as recomputed from co-presence;
        any relation with a DORMANT endpoint demotes (its subject matter is
        gone for this level)."""
        dormant = self._dormant_refs()
        for r in self.store.conn.execute(
                "SELECT rel_id, verb, src_ref, dst_ref FROM relation WHERE run_id=? AND "
                "version=(SELECT MAX(version) FROM relation r2 WHERE r2.run_id=relation.run_id "
                "AND r2.rel_id=relation.rel_id)", (self.run_id,)).fetchall():
            cur = self.current_status("RELATION", r["rel_id"]) or "HYPOTHESIS"
            if cur == "DEMOTED":
                continue
            if r["src_ref"] in dormant or r["dst_ref"] in dormant:
                self._append_status(turn_id, "RELATION", r["rel_id"], cur, "DEMOTED",
                                    "endpoint dormant")
                continue
            if r["verb"] == "same_as":
                self.recompute_sameas_status(r["rel_id"], turn_id)

    # ---- Procedures (§5.4): distill on full consume, replay before means ----
    def distill_procedure(self, commit_id: str, commit_version: int, goal_id: str,
                          turn_id: int, level_index: int) -> Optional[str]:
        """A Commitment whose steps ALL confirmed distills into a
        ProcedureTemplate: ordered (action_kind, role slot, expected delta
        shape) — prose-plus-geometry, deliberately not a program — with a
        context-class scope fingerprint."""
        steps = self.store.conn.execute(
            "SELECT step_id, kind, action, predicted_delta_json FROM commitment_step WHERE "
            "run_id=? AND commit_id=? AND commit_version=? ORDER BY step_ord",
            (self.run_id, commit_id, commit_version)).fetchall()
        if not steps or any(self.current_status("COMMITMENT_STEP", s["step_id"]) != "CONSUMED"
                            for s in steps):
            return None
        proc_id = self.store.mint_id(self.run_id, "P", config.ID_WIDTH)
        fingerprint = self.current_context_class(level_index, turn_id)
        self.store.conn.execute(
            "INSERT INTO procedure (run_id, proc_id, version, scope_fingerprint, "
            "distilled_from_commit, created_turn) VALUES (?,?,1,?,?,?)",
            (self.run_id, proc_id, fingerprint, commit_id, turn_id))
        for i, s in enumerate(steps):
            self.store.conn.execute(
                "INSERT INTO procedure_slot (run_id, proc_id, proc_version, slot_ord, "
                "action_kind, referent_role_slot, expected_delta_shape_json) VALUES (?,?,1,?,?,?,?)",
                (self.run_id, proc_id, i, f"{s['kind']}:{s['action'] or '?'}", "target",
                 s["predicted_delta_json"] or "{}"))
        self._append_status(turn_id, "PROCEDURE", proc_id, None, "HYPOTHESIS", "distilled")
        return proc_id

    def compile_from_procedure(self, leaf_goal: str, turn_id: int, level_index: int) -> Optional[str]:
        """§5.4 reuse: applicable Procedures compile BEFORE fresh means
        analysis — fingerprint must equal the CURRENT context class; the role
        slot rebinds to the leaf's bound referent (build-1 deterministic
        binding; the Surveyor may propose alternatives through the gates)."""
        fingerprint = self.current_context_class(level_index, turn_id)
        target = self.store.conn.execute(
            "SELECT ref_id FROM goal_binding WHERE run_id=? AND goal_id=? ORDER BY ref_id LIMIT 1",
            (self.run_id, leaf_goal)).fetchone()
        if not target:
            return None
        target = target["ref_id"]
        if target in self._dormant_refs():
            return None
        for p in self.store.conn.execute(
                "SELECT proc_id, version FROM procedure WHERE run_id=? AND scope_fingerprint=? "
                "ORDER BY proc_id", (self.run_id, fingerprint)).fetchall():
            if self.current_status("PROCEDURE", p["proc_id"]) == "DEMOTED":
                continue
            slots = self.store.conn.execute(
                "SELECT action_kind, expected_delta_shape_json FROM procedure_slot WHERE run_id=? "
                "AND proc_id=? AND proc_version=? ORDER BY slot_ord",
                (self.run_id, p["proc_id"], p["version"])).fetchall()
            if not slots:
                continue
            steps = []
            for s in slots:
                kind, _, action = s["action_kind"].partition(":")
                steps.append({"kind": kind, "action": None if action == "?" else action,
                              "target_ref": target,
                              "predicted": json.loads(s["expected_delta_shape_json"] or "{}") or None})
            commit_id = self.write_commitment(leaf_goal, steps, turn_id,
                                              procedure_id=p["proc_id"])
            self.stamp_relevance(turn_id, leaf_goal, "REFERENT", target)
            return commit_id
        return None

    def procedure_of_commit(self, commit_id: str) -> Optional[str]:
        row = self.store.conn.execute(
            "SELECT procedure_id FROM commitment WHERE run_id=? AND commit_id=? "
            "ORDER BY version DESC LIMIT 1", (self.run_id, commit_id)).fetchone()
        return row["procedure_id"] if row else None

    # ---- FISSION EXECUTE (§2.6.4) ----
    def fission_execute(self, ref_id: str, turn_id: int) -> dict:
        """Re-cluster the referent's BindingRecords by anchor signature; mint a
        fresh child per cluster (provenance FISSION, anchored at the cluster's
        LAST snapshot); retire the parent (DORMANT, split_into lineage); demote
        rules citing it; widen goal bindings to the children; block dependent
        steps; the caller fires T1. Receipts stay keyed to the retired parent
        — replayable data joinable via lineage + BindingRecords (§2.6.1);
        children re-earn support fresh (never inherited)."""
        if ref_id in self._dormant_refs():
            return {"executed": False, "children": []}
        groups: dict = {}
        for b in self.store.conn.execute(
                "SELECT turn_id, anchor_signature, anchor_cells_json FROM binding_record "
                "WHERE run_id=? AND bound_to=? ORDER BY turn_id", (self.run_id, ref_id)):
            groups.setdefault(b["anchor_signature"], []).append(b)
        if len(groups) < 2:
            return {"executed": False, "children": []}
        prow = self.store.conn.execute(
            "SELECT r.kind, g.colors_json FROM referent r JOIN locator_gridregion g ON "
            "g.run_id=r.run_id AND g.locator_id=r.anchor_locator_id WHERE r.run_id=? AND "
            "r.ref_id=? ORDER BY r.version DESC LIMIT 1", (self.run_id, ref_id)).fetchone()
        color = (json.loads(prow["colors_json"]) or [0])[0] if prow else 0
        children = []
        for sig in sorted(groups):
            last = groups[sig][-1]
            cells = frozenset(tuple(c) for c in json.loads(last["anchor_cells_json"]) or [(0, 0)])
            xs = [c[0] for c in cells]; ys = [c[1] for c in cells]
            comp = Component(color=color, cells=cells,
                             bbox=(min(xs), min(ys), max(xs), max(ys)),
                             centroid=(round(sum(xs) / len(cells)), round(sum(ys) / len(cells))),
                             size=len(cells),
                             shape=frozenset((x - min(xs), y - min(ys)) for x, y in cells))
            loc_id = self._write_gridregion_locator(comp, turn_id)
            child = self.store.mint_id(self.run_id, "R", config.ID_WIDTH)
            self.store.conn.execute(
                "INSERT INTO referent (run_id, ref_id, version, kind, anchor_locator_id, "
                "signature, first_seen, provenance, created_turn) VALUES (?,?,1,?,?,?,?,?,?)",
                (self.run_id, child, prow["kind"] if prow else "percept-cluster", loc_id,
                 sig, turn_id, "FISSION", turn_id))
            self._append_status(turn_id, "REFERENT_RUNG", child, None, "ANCHORED", "fission child")
            seq = self.store.next_seq(self.run_id, "referent_lineage")
            self.store.conn.execute(
                "INSERT INTO referent_lineage (run_id, seq, turn_id, op, parent_ref, child_ref) "
                "VALUES (?,?,?,?,?,?)", (self.run_id, seq, turn_id, "FISSION_SPLIT", ref_id, child))
            children.append(child)
        self._append_status(turn_id, "REFERENT_LIFE", ref_id, None, "DORMANT", "fission split")
        # demote rules citing the retired parent (the audit chain survives)
        for r in self.store.conn.execute(
                "SELECT rule_id, ctx_pred_json FROM rule WHERE run_id=? AND version=(SELECT "
                "MAX(version) FROM rule r2 WHERE r2.run_id=rule.run_id AND r2.rule_id=rule.rule_id)",
                (self.run_id,)).fetchall():
            try:
                tgt = json.loads(r["ctx_pred_json"]).get("target")
            except (ValueError, TypeError, AttributeError):
                continue
            cur = self.current_status("RULE", r["rule_id"])
            if tgt == ref_id and cur != "DEMOTED":
                self._append_status(turn_id, "RULE", r["rule_id"], cur, "DEMOTED",
                                    "fission of target")
        # widen goal bindings to all children
        for gb in self.store.conn.execute(
                "SELECT DISTINCT goal_id FROM goal_binding WHERE run_id=? AND ref_id=?",
                (self.run_id, ref_id)).fetchall():
            for child in children:
                self.bind_goal_ref(gb["goal_id"], child)
        # dependent steps auto-block via the existing mechanism
        for sp in self.store.conn.execute(
                "SELECT DISTINCT step_id FROM step_premise WHERE run_id=? AND "
                "member_kind='TARGET_REF' AND member_id=?", (self.run_id, ref_id)).fetchall():
            if self.current_status("COMMITMENT_STEP", sp["step_id"]) == "ACTIVE":
                self.mark_step(sp["step_id"], "BLOCKED", turn_id, "fission of target")
        return {"executed": True, "children": children}

    # ---- evidence compaction (§2.4.5): count + sampled exemplar pointers ----
    def consequence_signature(self, ref_id: str) -> str:
        rows = self.store.conn.execute(
            "SELECT turn_id, observed_delta_json, score_event, level_event FROM consequence_record "
            "WHERE run_id=? AND target_ref=? ORDER BY turn_id", (self.run_id, ref_id)).fetchall()
        if not rows:
            return "-"
        nz = z = ev = 0
        for r in rows:
            try:
                c = json.loads(r["observed_delta_json"] or "{}").get("cells_changed", 0)
            except ValueError:
                c = 0
            nz, z = (nz + 1, z) if c else (nz, z + 1)
            ev += 1 if (r["score_event"] or r["level_event"]) else 0
        turns = [r["turn_id"] for r in rows]
        ex = sorted(set([turns[0], turns[len(turns) // 2], turns[-1]]))
        sig = f"{len(rows)}rcpt({nz}chg,{z}noop"
        if ev:
            sig += f",{ev}ev"
        return sig + f") ex t{',t'.join(str(t) for t in ex)}"

    # ---- M7: fission-check, divergence context-class, Surveyor ingest ----
    def fission_check(self, ref_id: str) -> dict:
        """Point-biserial r between a referent's match/mismatch outcomes and a
        binding feature (here: signature variant across its BindingRecords).
        Fire when mismatches > K_fiss AND |r| ≥ FISS_R. Build-1: the check is
        STAMPED (FSN); the destructive re-split op is gated off."""
        c = self.store.conn
        recs = c.execute(
            "SELECT turn_id, match FROM consequence_record WHERE run_id=? AND target_ref=? "
            "AND match IS NOT NULL", (self.run_id, ref_id)).fetchall()
        mism = sum(1 for r in recs if r["match"] == 0)
        if mism <= config.K_FISS or len(recs) < 3:
            return {"fired": False, "r": 0.0, "mismatches": mism}
        # binding feature per turn: the anchor signature at that turn
        sig_by_turn = {b["turn_id"]: b["anchor_signature"] for b in c.execute(
            "SELECT turn_id, anchor_signature FROM binding_record WHERE run_id=? AND bound_to=?",
            (self.run_id, ref_id))}
        # majority signature = group 0, others = group 1; x = match(0/1), y = group
        from collections import Counter
        sigs = [sig_by_turn.get(r["turn_id"], "?") for r in recs]
        if not sigs:
            return {"fired": False, "r": 0.0, "mismatches": mism}
        majority = Counter(sigs).most_common(1)[0][0]
        xs = [1 if r["match"] == 1 else 0 for r in recs]
        ys = [0 if s == majority else 1 for s in sigs]
        r = _point_biserial(xs, ys)
        fired = abs(r) >= config.FISS_R
        return {"fired": fired, "r": round(r, 4), "mismatches": mism}

    def validate_surveyor_proposals(self, proposals: list, turn_id: int,
                                    step_premises: Optional[dict] = None,
                                    ctx: Optional[dict] = None) -> dict:
        """Route each PROPOSED op through its gate: PROPOSE_GOAL → 6 gates;
        PROPOSE_RULE/RELATION → add (HYPOTHESIS, test_plan required); ABORT_STEP
        / RANK_TIEBREAK → Revision-Evidence gate. The Surveyor can never write a
        fact, promote, mark achieved, touch an anchor, or flip agenda without
        qualifying new evidence. Gate-rejected aborts meter SRR."""
        admitted, rejected, srr = [], [], 0
        for p in proposals:
            if not isinstance(p, dict):
                rejected.append({"op": p, "reason": "MALFORMED"})
                continue
            op = p.get("op")
            if op == "PROPOSE_GOAL":
                res = self.admit_goal(p, turn_id, parent=p.get("parent"), ctx=ctx)
                entry = {"op": op}
                if res["ok"]:
                    entry["goal_id"] = res["goal_id"]
                    # chain §2.4 tier 2: a CLAIMED fill is mechanically proven
                    # or the edge stays unverified — the LLM cannot assert
                    # chain progress; unprovable fills are admitted goals that
                    # remain chain-irrelevant
                    if p.get("fills_hole") is not None and p.get("parent"):
                        ok_fill, hole = self.verify_fill(
                            p["parent"], p.get("achievement_test") or {},
                            {"cur": {}, "prev": {}})
                        self.add_goal_edge(p["parent"], res["goal_id"],
                                           hole if ok_fill else
                                           {"claim": str(p["fills_hole"])[:80]},
                                           verified=ok_fill, turn_id=turn_id)
                        entry["edge_verified"] = ok_fill
                else:
                    entry["reason"] = res["reason"]
                (admitted if res["ok"] else rejected).append(entry)
            elif op == "PROPOSE_RULE":
                if not p.get("test_plan"):
                    rejected.append({"op": op, "reason": "SURVEYOR_RULE_NEEDS_TEST_PLAN"})
                    continue
                ok, why = self.validate_rule_shape(p.get("ctx"), p.get("effect"))
                if not ok:
                    rejected.append({"op": op, "reason": why})
                else:
                    rid = self.add_rule(turn_id, p.get("template", ""), p["ctx"],
                                        p["effect"], test_plan=p["test_plan"])
                    admitted.append({"op": op, "rule_id": rid})
            elif op == "PROPOSE_RELATION":
                roster = self._roster_ids()
                if p.get("src") not in roster or p.get("dst") not in roster:
                    rejected.append({"op": op, "reason": "DANGLING_REF"})
                else:
                    rel = self.persist_relation(turn_id, p.get("verb", ""), p["src"], p["dst"],
                                                p.get("test_plan") or p.get("claim"))
                    if rel:
                        admitted.append({"op": op, "rel_id": rel})
                    else:
                        rejected.append({"op": op, "reason": "RELATION_VERB_NOT_CLOSED"})
            elif op == "PROPOSE_EXPERIMENT":
                actions = {s["action"] for s in self.adapter.action_vocab()}
                tgt = p.get("target")
                disc = p.get("discriminates", [])
                if p.get("action") in actions and (tgt is None or tgt in self._roster_ids()) \
                        and self._effect_shape_ok(p.get("predicted")) and isinstance(disc, list):
                    eid = self.add_experiment(turn_id, "", p["action"], tgt, p["predicted"], disc)
                    admitted.append({"op": op, "exp_id": eid})
                else:
                    rejected.append({"op": op, "reason": "EXPERIMENT_NOT_CLOSED"})
            elif op == "ABORT_STEP":
                gate = self.gate_abort_step(p.get("step_id"), p.get("evidence_ptr"), turn_id)
                if gate["ok"]:
                    admitted.append({"op": op, "step_id": p.get("step_id")})
                else:
                    rejected.append({"op": op, "reason": gate["reason"]})
                    srr += 1   # gate-rejected revision → SRR
            elif op == "RANK_TIEBREAK":
                # tie-breaks pass the identical gate: resolved contradiction-
                # class evidence, fresh, subject intersecting the goal
                ev = self.resolve_evidence(p.get("evidence_ptr"))
                if ev is not None and ev["subject"] and (
                        ev["subject"] == p.get("goal_id")
                        or ev["subject"] in {b["ref_id"] for b in self.store.conn.execute(
                            "SELECT ref_id FROM goal_binding WHERE run_id=? AND goal_id=?",
                            (self.run_id, p.get("goal_id", "")))}):
                    admitted.append({"op": op})
                else:
                    rejected.append({"op": op, "reason": "NOT_CONTRADICTION_CLASS"
                                     if ev is None else "IRRELEVANT_EVIDENCE"})
                    srr += 1
            else:
                rejected.append({"op": op, "reason": "UNKNOWN_OP"})
        return {"admitted": admitted, "rejected": rejected, "srr": srr}

    # ---- Revision-Evidence gate (§5.3) ----
    def revision_evidence_gate(self, step_premise: set, step_compile_turn: int,
                               evidence_kind: str, evidence_turn: int, evidence_subject: str) -> dict:
        """AbortStep admissible iff (a) contradiction-class evidence, (b) fresh
        (evidence.turn_id > step.compilation_turn_id), (c) relevant (subject ∩
        premise closure). Stale/unrelated mismatches never qualify."""
        contradiction_class = {"CONSEQUENCE_MISMATCH", "DEMOTION", "FISSION",
                               "REOPENED", "LEASE_EXPIRY"}
        if evidence_kind not in contradiction_class:
            return {"ok": False, "reason": "NOT_CONTRADICTION_CLASS"}
        if evidence_turn <= step_compile_turn:
            return {"ok": False, "reason": "STALE_EVIDENCE"}
        if evidence_subject not in step_premise:
            return {"ok": False, "reason": "IRRELEVANT_EVIDENCE"}
        return {"ok": True, "reason": None}


    def find_candidates(self) -> list:
        """Current referents as bind candidates: {ref_id, signature, bbox, centroid}
        from each referent's current-version anchor. Anchor-overlap/signature
        prefiltering happens in reidentify via the composite score."""
        c = self.store.conn
        rows = c.execute(
            "SELECT r.ref_id, r.signature, g.bbox_x0, g.bbox_y0, g.bbox_x1, g.bbox_y1, g.cells_json "
            "FROM referent r JOIN locator_gridregion g "
            "  ON g.run_id=r.run_id AND g.locator_id=r.anchor_locator_id "
            "WHERE r.run_id=? AND r.version=(SELECT MAX(version) FROM referent r2 "
            "  WHERE r2.run_id=r.run_id AND r2.ref_id=r.ref_id)", (self.run_id,)).fetchall()
        dormant = self._dormant_refs()
        out = []
        for row in rows:
            if row["ref_id"] in dormant:
                continue
            cells = json.loads(row["cells_json"])
            n = len(cells) or 1
            cx = round(sum(p[0] for p in cells) / n)
            cy = round(sum(p[1] for p in cells) / n)
            out.append({"ref_id": row["ref_id"], "signature": row["signature"],
                        "bbox": (row["bbox_x0"], row["bbox_y0"], row["bbox_x1"], row["bbox_y1"]),
                        "centroid": (cx, cy),
                        "cellset": {tuple(p) for p in cells}})
        return out


def eval_cmp(n: int, node: dict) -> bool:
    op = node.get("op")
    rhs = node.get("value", 0)
    if op == "GE":
        return n >= rhs
    if op == "GT":
        return n > rhs
    if op == "EQ":
        return n == rhs
    return n > 0


def _point_biserial(x: list, y: list) -> float:
    """Correlation between a binary outcome x (match) and a binary group y."""
    n = len(x)
    if n < 2:
        return 0.0
    g1 = [x[i] for i in range(n) if y[i] == 1]
    g0 = [x[i] for i in range(n) if y[i] == 0]
    if not g1 or not g0:
        return 0.0
    m1 = sum(g1) / len(g1)
    m0 = sum(g0) / len(g0)
    mean = sum(x) / n
    var = sum((xi - mean) ** 2 for xi in x) / n
    sd = var ** 0.5
    if sd == 0:
        return 0.0
    p1 = len(g1) / n
    p0 = len(g0) / n
    return (m1 - m0) / sd * (p1 * p0) ** 0.5


# ================= M7: epochs, triggers, fission, Surveyor ingest =================

class EpochController:
    """Trigger set + rate limit (§4.2). One epoch per C beats except T1
    contradiction (rate-limit-exempt, overrides everything)."""

    def __init__(self) -> None:
        self.last_epoch_turn = -10 ** 9
        self.last_evidence_turn = 0
        self.epochs_this_level = 0

    def note_evidence(self, turn: int) -> None:
        self.last_evidence_turn = turn

    def level_reset(self) -> None:
        self.epochs_this_level = 0

    def check(self, turn: int, contradiction: bool, goal_transition: bool,
              comp_fail: bool, level_changed: bool, triggers_on: bool = True,
              lease_expired: bool = False, level_index: int = 0) -> tuple:
        """(fire, trigger). T1 fires immediately and overrides; T2-T5 + lease
        respect the rate limit AND the hard per-level epoch cap (§4.2 —
        cap = EPOCH_CAP_BASE × (level+1), scaling with level index). With
        triggers_on=False (A9), T1/T4/lease are disabled — epochs only on
        T2/T3/T5."""
        if contradiction and triggers_on:
            return True, "T1"
        if turn - self.last_epoch_turn < config.C_EPOCH_RATE:
            return False, None
        if self.epochs_this_level >= config.EPOCH_CAP_BASE * (level_index + 1):
            return False, None
        if level_changed:
            return True, "T5"
        if goal_transition:
            return True, "T2"
        if comp_fail:
            return True, "T3"
        if triggers_on and lease_expired:
            return True, "LEASE"
        if triggers_on and (turn - self.last_evidence_turn >= config.S_STALL):
            return True, "T4"
        return False, None

    def fired(self, turn: int) -> None:
        self.last_epoch_turn = turn
        self.epochs_this_level += 1
