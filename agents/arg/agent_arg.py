"""ARG(Agent) — the doing-loop turn pump (build plan §7).

Fully overrides Agent.main() as the B1–B8 beat pump over a fresh arg_state.db.
M2 delivers the playing spine: B1 degenerate frontier probe (0 LLM), B2 emit +
TurnRecord, B3 diff + re-identify + bind, B4 consequence record. B5–B8
(Observer/renderer/epochs) land in later milestones behind their gates.
do_action_request is overridden as the single api_log choke point so every
HTTP round-trip is captured regardless of issuer.
"""

from __future__ import annotations

import datetime
import logging
import time
from typing import Any, Optional

import requests
from requests import Response

from ..agent import Agent
from ..structs import FrameData, GameAction, GameState
from . import config, organs, seeds
from .adapter import ARCAdapter
from .executive import Executive, EpochController, frame_hash
from .probe_db import ProbeStore
from .renderer import Renderer
from .store import Store

logger = logging.getLogger()


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


class ARG(Agent):
    """Aligned Referent Grounding agent. One arg_state.db + one arg_probe.db per run."""

    MAX_ACTIONS = config.MAX_ACTIONS

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.turn_id: int = -1               # +1 per emitted command (incl. RESET); first = 0
        self.level_counter: int = 0
        self.prev_grid: Optional[list] = None
        self._run_id = f"arg-{self.game_id}-{int(time.time())}"
        self._store: Optional[Store] = None
        self._probe: Optional[ProbeStore] = None
        self._exec: Optional[Executive] = None
        self._adapter = ARCAdapter()
        self._targeted = self._adapter.targeted_actions()   # tool seam: no name string-matching
        self._last_levels = 0
        self._prev_signals: dict = {}
        self._renderer: Optional[Renderer] = None
        self._epochs = EpochController()
        self._llm_ready = False
        self._pending_comp_fail = False
        self._pending_lease = False
        self._active_step_text: Optional[str] = None
        self._active_pred_text: Optional[str] = None
        self._beat_render_tokens = 0
        self._organ_calls: dict = {}
        from collections import deque
        self._log_tail = deque(maxlen=max(config.L_LOG_TAIL, 1))   # §2.4.7: Observer tail ≤ L turns
        self._zone_echoes: dict = {}       # zone → recent echo bits (ZCR live window)
        self._force_compact = False        # R6 live trigger: zone-differential ZCR failure

    # ---- ABC obligations ----
    def is_won(self, frames: list, latest_frame: FrameData) -> bool:
        """Whole-game win only (overrides the WIN-inverted base). A level
        completion (levels_completed++ with NOT_FINISHED) must NOT trip it."""
        return latest_frame.state == GameState.WIN

    def choose_action(self, frames: list, latest_frame: FrameData) -> GameAction:
        """Thin delegate so the class is concrete; the real select is B1."""
        return self._compose_probe(latest_frame)

    # ---- the api_log choke point: every HTTP round-trip, any issuer ----
    def do_action_request(self, action: GameAction) -> Response:
        resp = super().do_action_request(action)
        try:
            body = resp.json()
        except ValueError:
            body = None
        # `lives` is not in FrameData's model — capture it from the raw body at
        # the choke point so life_event/scope can be earned (§2.2)
        self._pending_lives = (body or {}).get("lives") if isinstance(body, dict) else None
        req = dict(action.action_data.model_dump())
        if action == GameAction.RESET:
            req["card_id"] = self.card_id
        if self.guid:
            req["guid"] = self.guid
        req["game_id"] = self.game_id
        if self._probe is not None:
            self._probe.log_api(self._run_id, max(self.turn_id, 0), 0, action.name,
                                getattr(self, "_pending_stamp", "RESET"), req, body,
                                getattr(resp, "status_code", None), _now())
        return resp

    # ---- turn pump ----
    def main(self) -> None:
        self.timer = time.time()
        self._store = Store(config.STORE_PATH)
        self._probe = ProbeStore(config.PROBE_PATH)
        self._exec = Executive(self._store, self._adapter, self._run_id)
        self._renderer = Renderer(self._store, self._exec, self._run_id, self._adapter)
        self._store.register_run(self._run_id, self.game_id, config.MODEL, 0,
                                 __import__("json").dumps(config.snapshot()),
                                 config.B_RENDER, _now())
        self._probe.register(self._run_id, card_id=self.card_id, game_id=self.game_id,
                             backbone=config.MODEL, seed=0,
                             config_json=__import__("json").dumps(config.snapshot()),
                             arm=(",".join(self.tags) if self.tags else "FULL"),
                             comparison_group=f"{self.game_id}-0-{config.MODEL}", started_at=_now())
        seeds.write_seeds(self._store, self._run_id, turn_id=0)
        # honest tri-state: no vision path is in use, so the image-receipt
        # round-trip is NOT APPLICABLE (NULL), not "passed" (§7 / Q11)
        self._probe.log_startup(self._run_id, image_receipt_ok=None,
                                signal_vocab=self._adapter.signal_channels(),
                                action_interface={"actions": [s["action"] for s in
                                                              self._adapter.action_vocab()]})

        # beat 0: RESET to start the game
        self._emit(GameAction.RESET, source="RESET")
        if config.STRESS_MULT > 1:   # A11 store-stress knob
            self._exec.inflate_store(config.STRESS_MULT, max(self.turn_id, 0))

        while not self.is_won(self.frames, self.frames[-1]) and self.action_counter < self.MAX_ACTIONS:
            latest = self.frames[-1]
            if latest.state in (GameState.GAME_OVER, GameState.NOT_STARTED):
                self._emit(GameAction.RESET, source="RESET")   # T5: recover a lost life
            else:
                self._beat(latest)
            self.action_counter += 1

        self._finish()
        self.cleanup()

    def _compose_probe(self, latest: FrameData) -> GameAction:
        avail = [a.name for a in latest.available_actions] or \
                [s["action"] for s in self._adapter.action_vocab()]
        # experiment preference: a probe with a pre-registered prediction is
        # worth more than a blind one (§4.2 Experiments)
        choice = None
        exp = self._exec.next_experiment(set(avail))
        if exp is not None:
            params: dict = {}
            if exp["action"] in self._targeted:
                cells = self._exec._ref_cells(exp["target"]) if exp["target"] else set()
                cell = min(cells) if cells else (0, 0)
                params = {"x": int(cell[0]), "y": int(cell[1])}
            choice = {"action": exp["action"], "params": params, "target_ref": exp["target"],
                      "source_stamp": "PROBE", "experiment": exp}
        if choice is None:
            choice = self._exec.frontier_probe(avail, max(self.turn_id, 0))
        act = GameAction[choice["action"]]
        if choice["action"] in self._targeted:
            act.set_data(choice["params"])
        self._pending_choice = choice
        return act

    def _beat(self, latest: FrameData) -> None:
        """B1 (§4.3): live Commitment step → execute deterministically [0
        calls; ≤1 Actuator call for param realization]; else query walk
        (means analysis → compile) ; else the cheapest untested probe."""
        avail = {a.name for a in latest.available_actions} or \
                {s["action"] for s in self._adapter.action_vocab()}
        self._last_avail = sorted(avail)
        self._pending_comp_fail = False
        self._pending_lease = False
        self._beat_render_tokens = 0
        if config.BASELINE == "bcache":
            # §8 B-CACHE (LINK-KG-equivalent): canonical ids + R2 substitution
            # + Z1/Z2/Z5 retained; consequence gating and goal machinery OFF;
            # ONE decision call per beat over the substituted view.
            cmd, params, stamp = self._bcache_decide(latest, avail)
            self._pending_stamp = stamp
            self._emit(cmd, source=stamp, params=params)
            return
        step = None
        if config.AGENDA_ON and config.GOALS_ON:
            step, flags = self._exec.next_executable_step(self.turn_id + 1)
            self._pending_lease = flags["lease_expired"]
            if step is not None and step["action"] and step["action"] not in avail:
                self._exec.mark_step(step["step_id"], "BLOCKED", self.turn_id + 1,
                                     "action unavailable")
                step = None
            if step is None and not self._pending_lease:
                step = self._try_compile()
        if step is not None:
            cmd, params, stamp, predicted = self._realize_step(step, latest)
            self._active_step_text = (
                f"step {step['step_ord'] + 1} [{step['kind']}] {step['action'] or 'interact'}"
                f" → {step['target_ref'] or '-'} ({step['step_id']} of {step['goal_id']})")
            self._active_pred_text = str(predicted) if predicted else None
            self._pending_stamp = stamp
            self._emit(cmd, source=stamp, params=params, step=step, step_predicted=predicted)
        else:
            self._active_step_text = None
            self._active_pred_text = None
            cmd = self._compose_probe(latest)
            self._pending_stamp = self._pending_choice["source_stamp"]
            self._emit(cmd, source=self._pending_choice["source_stamp"],
                       params=self._pending_choice.get("params", {}),
                       declared_target=self._pending_choice.get("target_ref"),
                       experiment=self._pending_choice.get("experiment"))

    def _bcache_decide(self, latest: FrameData, avail: set) -> tuple:
        """One LLM decision over the substituted Z1+Z2+Z5 view (the alias/
        canonicalization surface, nothing else); deterministic probe fallback."""
        head = {"turn": self.turn_id + 1, "level": self._last_levels,
                "score": latest.score or 0}
        try:
            self._ensure_llm()
            bv = self._renderer.budgeted_view(head, self.prev_grid or [], sorted(avail),
                                              force_compact=self._force_compact)
            self._beat_render_tokens = max(self._beat_render_tokens, bv["render_tokens"])
            view = "\n\n".join(bv["zones"][z] for z in ("Z1", "Z2", "Z5"))
            out = organs.run_baseline(view + "\n\nAVAILABLE: " + ",".join(sorted(avail)))
            self._log_llm("actuator", {"canary_echo": []}, render_tokens=bv["render_tokens"],
                          ops_accepted=1 if out["action"] in avail else 0,
                          ops_rejected=0 if out["action"] in avail else 1)
            if out["action"] in avail:
                cmd = GameAction[out["action"]]
                params = {}
                if out["action"] in self._targeted:
                    params = {"x": out["x"], "y": out["y"]}
                    cmd.set_data(params)
                return cmd, params, "ACTUATOR_LLM"
        except Exception as e:
            logger.warning(f"bcache decide failed (probe fallback): {e}")
        choice = self._exec.frontier_probe(sorted(avail), max(self.turn_id, 0))
        cmd = GameAction[choice["action"]]
        if choice["action"] in self._targeted:
            cmd.set_data(choice["params"])
        return cmd, choice.get("params", {}), "PROBE"

    def _try_compile(self) -> Optional[dict]:
        """§4.3 + chain §2.5: the chain-aware WALK. Per unachieved goal in
        rank order: compile directly (procedures → TESTED means → milestone);
        else execute the chain FRONTIER — the deepest compilable goal along
        verified edges (children before the parents they serve); else, on a
        recognized DEFICIT, auto-fill the derivable holes (milestone sub-goals,
        provenance DEFICIT — amendment A2) and compile the fill; a residue of
        non-derivable holes is STAMPED — the Surveyor's directed question.
        Nothing compilable anywhere = compilation failure → T3."""
        sig_ctx = {"cur": dict(self._prev_signals or {}), "prev": {}}
        # walk order (Executive-computed, shared with the epoch DEFICIT block):
        # chain leaf, rank-ordered siblings, then ancestors deepest-first — the
        # root's own deficit stays visible while curriculum children live
        candidates = self._exec.walk_candidates()
        if not candidates:
            return None
        tried = False
        turn = self.turn_id + 1
        for gid in candidates:
            if self._exec.current_status("GOAL", gid) in ("ACCEPTED", "REJECTED"):
                continue
            tried = True
            commit_id = self._exec.compile_plan(gid, turn, sig_ctx)
            if commit_id is None:
                fr = self._exec.chain_frontier(gid, sig_ctx)
                if fr is not None and fr != gid:
                    commit_id = self._exec.compile_plan(fr, turn, sig_ctx)
                if commit_id is None:
                    cs = self._exec.chain_status(gid, sig_ctx)
                    if cs["status"] == "DEFICIT":
                        for child in self._exec.auto_fill_holes(gid, cs["holes"], turn):
                            commit_id = self._exec.compile_plan(child, turn, sig_ctx)
                            if commit_id is not None:
                                break
                        if commit_id is None:
                            self._exec.deficit_stamp(gid, cs["holes"], turn)
            if commit_id is not None:
                step, _ = self._exec.next_executable_step(turn)
                return step
        if tried:
            self._pending_comp_fail = True   # T3
        return None

    def _realize_step(self, step: dict, latest: FrameData) -> tuple:
        """(cmd, params, source_stamp, predicted). Deterministic except the
        targeted-tool parameter, which is the Actuator's one confined call (R8)."""
        predicted = None
        if step["predicted_delta_json"]:
            try:
                predicted = __import__("json").loads(step["predicted_delta_json"])
            except ValueError:
                predicted = None
        action = step["action"]
        if action in self._targeted:
            x, y, stamp = self._realize_targeted(step, latest, action)
            cmd = GameAction[action]
            cmd.set_data({"x": x, "y": y})
            return cmd, {"x": x, "y": y}, stamp, predicted
        if action is None:
            # arrival handoff (`then:` slot): post-arrival testing on the
            # target via the (deterministic-first) targeted tool
            acts = [t["name"] for t in self._adapter.tools() if t["side"] == "actuate"]
            tact = sorted(self._targeted)[0] if self._targeted else acts[0]
            cells = self._exec._ref_cells(step["target_ref"]) if step["target_ref"] else set()
            cell = min(cells) if cells else (0, 0)
            cmd = GameAction[tact]
            cmd.set_data({"x": int(cell[0]), "y": int(cell[1])})
            return cmd, {"x": int(cell[0]), "y": int(cell[1])}, "COMMITMENT_STEP", predicted
        cmd = GameAction[action]
        return cmd, {}, "COMMITMENT_STEP", predicted

    def _realize_targeted(self, step: dict, latest: FrameData, action: str) -> tuple:
        """R8 parameter realization for a targeted tool: Actuator proposes
        (x,y); the containment validator disposes; one typed re-prompt
        rendering ONLY the target's roster row; then deterministic FALLBACK
        (contained centroid-or-cell)."""
        target = step["target_ref"]
        schema = next((t["param_schema"] for t in self._adapter.tools()
                       if t["name"] == action), None) or {"x": [0, 63], "y": [0, 63]}
        head = {"turn": self.turn_id + 1, "level": self._last_levels, "score": 0}
        if config.BASELINE == "":
            try:
                self._ensure_llm()
                avail = [a.name for a in latest.available_actions] or sorted(self._targeted)
                bv = self._renderer.budgeted_view(head, self.prev_grid or [], avail,
                                                  active_step=self._describe_step(step),
                                                  predicted_effect=step["predicted_delta_json"],
                                                  force_compact=self._force_compact)
                self._beat_render_tokens = max(self._beat_render_tokens, bv["render_tokens"])
                row = self._roster_row(target)
                out = organs.run_actuator(bv["view"], row, __import__("json").dumps(schema))
                v = self._exec.validate_actuator(action, out["x"], out["y"], target, schema)
                self._log_llm("actuator", out, render_tokens=bv["render_tokens"],
                              ops_accepted=1 if v["ok"] else 0,
                              ops_rejected=0 if v["ok"] else 1)
                if v["ok"]:
                    return out["x"], out["y"], "ACTUATOR_LLM"
                self._exec.meter_write_reject(self.turn_id + 1, "ACTUATOR", action,
                                              v["violation"] or "R8", 0)
                out2 = organs.run_actuator(row, row, __import__("json").dumps(schema))
                v2 = self._exec.validate_actuator(action, out2["x"], out2["y"], target, schema)
                self._log_llm("actuator", out2, retry_count=1,
                              ops_accepted=1 if v2["ok"] else 0,
                              ops_rejected=0 if v2["ok"] else 1)
                if v2["ok"]:
                    return out2["x"], out2["y"], "ACTUATOR_LLM"
                self._exec.meter_write_reject(self.turn_id + 1, "ACTUATOR", action,
                                              v2["violation"] or "R8", 1)
            except Exception as e:
                logger.warning(f"Actuator realization failed (non-fatal): {e}")
        # deterministic fallback: the anchor CENTROID, verbatim per R8 — it may
        # land off-target (a ring's hole); SUBSTITUTION_CAUGHT is the designed
        # net for exactly that, so the fallback stays simple and honest.
        cen = self._exec._centroid(target) if target else None
        if cen is None:
            return 0, 0, "FALLBACK"
        return max(0, min(63, int(cen[0]))), max(0, min(63, int(cen[1]))), "FALLBACK"

    def _describe_step(self, step: dict) -> str:
        return (f"step {step['step_ord'] + 1} [{step['kind']}] {step['action'] or 'interact'}"
                f" → {step['target_ref'] or '-'}")

    def _roster_row(self, ref_id: Optional[str]) -> str:
        if not ref_id:
            return "(no target)"
        for r in self._exec.current_referents_with_cells():
            if r["ref_id"] == ref_id:
                x0, y0, x1, y1 = r["bbox"]
                return f"{ref_id} | anchor r{y0}-{y1}c{x0}-{x1} | cells={sorted(r['cells'])[:12]}"
        return f"{ref_id} | (not in roster)"

    def _emit(self, cmd: GameAction, source: str, params: Optional[dict] = None,
              declared_target: Optional[str] = None, step: Optional[dict] = None,
              step_predicted: Optional[dict] = None,
              experiment: Optional[dict] = None) -> None:
        """Issue one command, advance turn_id, run B2–B6, append the frame."""
        self.turn_id += 1
        self._pending_stamp = source
        pre_grid = self.prev_grid
        params = params or {}
        # Target by containment of the coordinates about to be emitted (§4.3 —
        # never copied from a step), then B4a: pre-register every in-scope
        # prediction BEFORE emission — the live step, all in-scope rules, and
        # the pending experiment. The unforgeable atom (§2.2): the LLM cannot
        # author a match it did not pre-commit to.
        target = self._exec.stamp_target(cmd.name, params)
        predictors = []
        shadow_step = None
        if cmd != GameAction.RESET:
            sig_ctx = {"cur": dict(self._prev_signals or {}), "prev": {}}
            if step is not None and step_predicted:
                predictors.append({"pid": step["step_id"], "kind": "STEP",
                                   "effect": step_predicted, "status": None})
            for p in self._exec.applicable_rules(cmd.name, target, sig_ctx):
                predictors.append({"pid": p["rule_id"], "kind": "RULE",
                                   "effect": p["effect"], "status": p["status"]})
            if experiment is not None:
                predictors.append({"pid": experiment["exp_id"], "kind": "EXPERIMENT",
                                   "effect": experiment["predicted"], "status": None})
            # §8 shadow-agenda: in A-off cells the Executive recompiles the
            # would-be step from the live store EXACTLY as FULL — computed at
            # the decision point, never rendered, never executed.
            if not config.AGENDA_ON and config.GOALS_ON:
                shadow_step = self._exec.plan_shadow_step(sig_ctx)
        frame = self.take_action(cmd)
        if frame is None:
            # caught HTTP failure; api_log self-stamped the orphan row. Consume the beat.
            return
        self.append_frame(frame)
        curr_grid = self._adapter.canonicalize(frame.frame) if frame.frame else []
        # B3: perceive + bind
        observed = {"cells_changed": 0}
        if curr_grid:
            changeset = self._adapter.diff(pre_grid, curr_grid)
            observed = self._exec.perceive_bind(self.turn_id, changeset)
        # B4: one coverage receipt + one receipt per pre-registered predictor
        # with the Executive-computed match; a TESTED rule's failed prediction
        # arms T1; mismatches update the fission statistic (§5.1 B4).
        levels = frame.levels_completed if frame.levels_completed is not None else 0
        level_event = 1 if levels > self._last_levels else 0
        prev_score = (self._prev_signals or {}).get("score") or 0
        score_event = 1 if (frame.score or 0) > prev_score else 0
        lives_now = getattr(self, "_pending_lives", None)
        prev_lives = (self._prev_signals or {}).get("lives")
        life_event = 1 if (lives_now is not None and prev_lives is not None
                           and lives_now < prev_lives) else 0
        cells = observed.get("cells_changed", 0)
        primary = None          # (predictor, match) — stamped into the TurnRecord
        contradiction = False   # T1
        if cmd != GameAction.RESET:
            # SUBSTITUTION_CAUGHT (§4.3): the emitted targeted tool landed on a
            # different referent than the step intended → logged, and NO
            # ConsequenceRecord is written against the step's target
            # (misattributed receipts are structurally impossible).
            substitution = bool(step and cmd.name in self._targeted and step.get("target_ref")
                                and target != step["target_ref"])
            if substitution:
                seq = self._store.next_seq(self._run_id, "substitution_caught")
                self._store.conn.execute(
                    "INSERT INTO substitution_caught (run_id, seq, turn_id, step_target, "
                    "landed_target) VALUES (?,?,?,?,?)",
                    (self._run_id, seq, self.turn_id, step["target_ref"], target))
                predictors = [p for p in predictors if p["kind"] != "STEP"]
            # divergence check FIRST so a regime-defining receipt lands in the
            # class it mints (§2.2); the fresh class reopens LEARN-ACTIONS.
            self._exec.maybe_diverge_context(cmd.name, cells, levels, self.turn_id)
            cc = self._exec.current_context_class(levels, self.turn_id)
            self._exec.write_consequence(
                self.turn_id, cmd.name, target, cc, observed_delta=observed,
                score_event=score_event, level_event=level_event, life_event=life_event)
            step_match = None
            for p in predictors:
                m = self._exec.match_effect(p["effect"], cells, score_event, level_event)
                self._exec.write_consequence(
                    self.turn_id, cmd.name, target, cc, observed_delta=observed,
                    predicted_delta=p["effect"], match=m,
                    predictor_id=p["pid"], predictor_kind=p["kind"],
                    score_event=score_event, level_event=level_event)
                if p["kind"] == "RULE":
                    self._exec.recompute_rule_status(p["pid"], self.turn_id)
                    if not m and p["status"] == "TESTED":
                        contradiction = True
                elif p["kind"] == "STEP":
                    step_match = m
                elif p["kind"] == "EXPERIMENT":
                    self._exec.mark_experiment_done(p["pid"], self.turn_id)
                if not m and target:
                    fc = self._exec.stamp_fission_check(target, self.turn_id)
                    # §2.6.4: the check firing EXECUTES the re-split (children
                    # minted, parent retired, dependents demoted/blocked) and
                    # fires T1 — unless killed via ARG_FISSION=0
                    if fc["fired"] and config.FISSION_ON:
                        fx = self._exec.fission_execute(target, self.turn_id)
                        if fx["executed"]:
                            contradiction = True
                if primary is None:
                    primary = (p, m)
            # consume-on-success (§4.3): the cursor advances only on an
            # Executive-confirmed match; failure = fail-with-observation
            # (the step stays ACTIVE; the lease bounds it).
            if step is not None and not substitution and step_match:
                self._exec.consume_step(step, self.turn_id, level_index=levels)
            # relation lifecycle sweep (same_as co-presence / dormant endpoints)
            self._exec.sweep_relations(self.turn_id)
        # turn_record — the shadow step stamped above keeps GDS-bind/abandon
        # defined in every factorial cell against a REAL compiled reference.
        self._exec.record_turn(
            self.turn_id, cmd.name, params, target,
            frame_hash(pre_grid) if pre_grid else "none", frame_hash(curr_grid) if curr_grid else "none",
            raw_diff={"cells_changed": observed.get("cells_changed", 0)},
            observed_delta=observed, score=frame.score or 0, level_counter=levels,
            state_flags=frame.state.name, lives=lives_now, source_stamp=source,
            commitment_step_id=step["step_id"] if step else None,
            predicted_delta=primary[0]["effect"] if primary else None,
            match=primary[1] if primary else None,
            render_tokens=self._beat_render_tokens,
            shadow_step_id=shadow_step,
            drift_ref="LIVE" if config.AGENDA_ON else "SHADOW")
        # B4 (cont.): learn the action model from movement (M6 NAVIGATE bootstrap)
        if pre_grid and curr_grid and cmd != GameAction.RESET:
            self._exec.learn_from_movement(cmd.name, pre_grid, curr_grid, self.turn_id)
        # B6: grounding recompute + achievement-test evaluation (the engine runs live).
        # ARG_GOALS=0 (B-CACHE seam) disables goal evaluation; ARG_CONSEQ=0 (A4)
        # would let appearance promote — recompute_rung is consequence-gated, so
        # A4 is a renderer/promotion switch handled at M9 config level.
        if curr_grid and cmd != GameAction.RESET:
            rung_refs = observed.get("bound", []) + observed.get("minted", [])
            if target and target not in rung_refs:
                rung_refs.append(target)
            if config.BASELINE != "bcache":   # B-CACHE: rungs freeze at ANCHORED (§8)
                for ref_id in rung_refs:
                    self._exec.recompute_rung(ref_id, self.turn_id)
            goal_transitions = []
            if config.GOALS_ON and config.BASELINE != "bcache":
                ctx = {"cur": {"score": frame.score or 0, "levels_completed": levels,
                               "state": frame.state.name,
                               "available": getattr(self, "_last_avail", None)},
                       "prev": self._prev_signals or {}}
                goal_transitions = self._exec.evaluate_all_goals(self.turn_id, ctx)
                # §3.4 terminal rule + §2.3 TTL decay — both zero-LLM sweeps
                self._exec.check_goal_budgets(self.turn_id)
                self._exec.ttl_sweep(self.turn_id)
            # B5: Observer IFF the ChangeSet is unexplained — no pre-registered
            # prediction covered it, or the prediction mismatched (§4.1). As
            # rules climb to TESTED and their predictions match, beats become
            # explained and the Observer quiets — mechanically, not by decree.
            explained = bool(primary and primary[1])
            unexplained = bool(observed.get("minted") or cells > 0) and not explained
            if config.BASELINE == "" and unexplained:
                self._run_observer(observed, frame)
            # B7: epoch — Surveyor on a fired trigger (rate-limited; T1 exempt).
            # T1 is armed by a real contradiction: a TESTED rule's pre-registered
            # prediction failed this beat (§4.2).
            if config.SEARCH_ON and config.BASELINE == "":
                self._epochs.note_evidence(self.turn_id) if observed.get("cells_changed") else None
                fire, trig = self._epochs.check(
                    self.turn_id, contradiction=contradiction,
                    goal_transition=bool(goal_transitions),
                    comp_fail=self._pending_comp_fail,
                    level_changed=bool(level_event), triggers_on=config.TRIGGERS_ON,
                    lease_expired=self._pending_lease, level_index=levels)
                if fire:
                    self._run_epoch(trig)
                    self._epochs.fired(self.turn_id)
        self._store.commit()
        if level_event:
            self._capture_scorecard()
            # T5 boundary pass (§2.4.6): instances reset; TESTED rules demote
            # to HYPOTHESIS with prior support noted; active steps abort.
            self._exec.level_boundary_pass(self.turn_id)
            self._epochs.level_reset()          # per-level epoch cap (§4.2)
            self._store.commit()
        self._last_levels = levels
        self.level_counter = levels
        if cmd != GameAction.RESET:
            # §4.1 Log tail: turn_id-keyed action + its PRE-COMMITTED prediction
            # + the Executive's match — attribution by keying, ≤ L turns
            pe = primary[0]["effect"] if primary else None
            self._log_tail.append(
                f"t{self.turn_id} {cmd.name}->{target or '-'} predicted={pe if pe else '-'} "
                f"match={primary[1] if primary else '-'} cells_changed={cells}")
        self._prev_signals = {"score": frame.score or 0, "levels_completed": levels,
                              "state": frame.state.name, "lives": lives_now}
        self.prev_grid = curr_grid

    def _ensure_llm(self) -> None:
        if not self._llm_ready:
            organs.configure_llm()
            self._llm_ready = True

    def _log_llm(self, organ: str, out: dict, render_tokens: int = 0,
                 ops_accepted: int = 0, ops_rejected: int = 0, retry_count: int = 0) -> None:
        usage = organs.last_usage()
        self._probe.log_llm_call(self._run_id, self.turn_id, organ, backbone=config.MODEL,
                                 call_idx=0, retry_count=retry_count,
                                 prompt_tokens=usage["prompt_tokens"],
                                 completion_tokens=usage["completion_tokens"],
                                 render_tokens=render_tokens,
                                 ops_accepted=ops_accepted, ops_rejected=ops_rejected,
                                 effort=config.REASONING_EFFORT,
                                 zcr_json=__import__("json").dumps(out.get("canary_echo", [])),
                                 ts=_now())

    def _salt_and_capture(self, organ: str, bv: dict) -> tuple:
        """§2.5 ZCR: capture the rendered zones (Q11 evidence) and, at cadence
        (every K_CANARY-th call per organ; EVERY Surveyor epoch), salt one
        nonce row per zone tier. Returns (zones_to_render, nonces)."""
        self._organ_calls[organ] = self._organ_calls.get(organ, 0) + 1
        idx = self._organ_calls[organ]
        zones = bv["zones"]
        # overflow is LOGGED (§2.4.7): the archived count rides the capture row
        self._renderer.capture(self._probe, self.turn_id, idx, organ, zones,
                               shadow=not config.AGENDA_ON,
                               rank_snapshot=f"ws={len(bv['working_set'])} "
                                             f"archived={bv.get('archived', 0)}")
        nonces: dict = {}
        if organ == "surveyor" or (config.K_CANARY > 0 and idx % config.K_CANARY == 0):
            # salt only the zones this organ's contract consumes (§4.1/§4.2)
            tiers = ("Z2",) if organ == "observer" else ("Z2", "Z3", "Z6")
            salted = self._renderer.salt_canaries(self._probe, self.turn_id, organ, idx,
                                                  zones, tiers=tiers)
            zones, nonces = salted["zones"], salted["nonces"]
        return zones, nonces

    def _record_echo(self, organ: str, nonces: dict, out: dict) -> None:
        """Persist per-zone echo results; a salted view with ZERO echoes is a
        caught adapter/consumption violation (metered as WER, §2.5)."""
        if not nonces:
            return
        echoed_any = False
        got = set(out.get("canary_echo") or [])
        for tier, nonce in nonces.items():
            e = 1 if nonce in got else 0
            echoed_any = echoed_any or bool(e)
            try:
                seq = self._probe._seq("zcr_echo", self._run_id)
                self._probe.conn.execute(
                    "INSERT INTO zcr_echo (run_id, seq, turn_id, organ, call_idx, zone_tier, "
                    "nonce, echoed) VALUES (?,?,?,?,?,?,?,?)",
                    (self._run_id, seq, self.turn_id, organ,
                     self._organ_calls.get(organ, 0), tier, nonce, e))
                self._probe.conn.commit()
            except Exception:
                self._probe.write_failures += 1
        if not echoed_any:
            self._exec.meter_write_reject(self.turn_id, organ.upper(), "CANARY",
                                          "MISSING_CANARY", 0)
        # R6 LIVE trigger (§2.5 diagnosis 2): zone-DIFFERENTIAL echo failure
        # over the recent window = consumption rot → the renderer falls back
        # to the compact tier from now on (uniform failure is Q11 territory).
        from collections import deque
        for tier, nonce in nonces.items():
            self._zone_echoes.setdefault(tier, deque(maxlen=5)).append(
                1 if nonce in got else 0)
        rates = {z: sum(d) / len(d) for z, d in self._zone_echoes.items() if len(d) >= 3}
        below = {z for z, r in rates.items() if r < config.ZCR_FLOOR}
        if below and len(below) < len(rates):
            if not self._force_compact:
                logger.warning(f"ZCR zone-differential failure {rates} → R6 compact fallback")
            self._force_compact = True

    def _run_observer(self, observed: dict, frame: FrameData) -> None:
        """B5: interpret an unexplained ChangeSet. The Executive proposes the
        candidate hashes; the Observer emits typed deltas; validate_ingest
        disposes; accepted ops are applied."""
        try:
            self._ensure_llm()
            grid = self.prev_grid or []
            head = {"turn": self.turn_id, "level": self._last_levels, "score": frame.score or 0}
            bv = self._renderer.budgeted_view(head, grid,
                                              [a.name for a in frame.available_actions] or ["ACTION1"],
                                              active_step=self._active_step_text,
                                              predicted_effect=self._active_pred_text,
                                              force_compact=self._force_compact)
            # §2.5 C_max: the changeset lists THIS BEAT's changed referents
            # (the actual ChangeSet), paginated — the remainder is re-presented
            # naturally while the beat class stays unexplained (union
            # completeness without breaching B).
            changed = (observed.get("bound") or []) + (observed.get("minted") or [])
            info = {r["ref_id"]: r for r in self._exec.current_referents_with_cells()}
            listed = [rid for rid in changed if rid in info][:config.C_MAX_CHANGESET]
            changeset_txt = "CHANGED THIS BEAT:\n" + "\n".join(
                f"  {rid} sig={info[rid]['signature']} bbox={info[rid]['bbox']}" for rid in listed)
            if len(changed) > config.C_MAX_CHANGESET:
                changeset_txt += (f"\n  (+{len(changed) - config.C_MAX_CHANGESET} more changed — "
                                  f"re-presented while unexplained)")
            tail_txt = "\n".join(self._log_tail) or "(no prior turns)"
            zones, nonces = self._salt_and_capture("observer", bv)
            view = zones["Z1"] + "\n" + zones["Z2"] + "\n" + zones["Z5"]
            out = organs.run_observer(changeset_txt, tail_txt, view)
            self._record_echo("observer", nonces, out)
            res = self._exec.validate_observer_ops(out["ops"], set())  # candidate hashes: NEW-only in M-loop
            self._log_llm("observer", out, render_tokens=bv["render_tokens"],
                          ops_accepted=len(res["accepted"]), ops_rejected=len(res["rejections"]))
            accepted = list(res["accepted"])
            if res["rejections"]:
                # §2.1 Write-Path Integrity: ONE typed re-prompt (within the
                # ≤2 budget); still-rejected ops are DROPPED and metered with
                # retry_count=1 — the DPR source. Exhaustion never stalls the
                # beat and never silently degrades.
                for rej in res["rejections"]:
                    self._exec.meter_write_reject(self.turn_id, "OBSERVER",
                                                  (rej.get("op") or {}).get("op", "?"),
                                                  rej["violation"], 0)
                fb = (changeset_txt + "\nYOUR REJECTED OPS (emit corrected replacements ONLY):\n"
                      + __import__("json").dumps(res["rejections"], default=str)[:1500])
                out2 = organs.run_observer(fb, tail_txt, view)
                res2 = self._exec.validate_observer_ops(out2["ops"], set())
                self._log_llm("observer", out2, retry_count=1,
                              ops_accepted=len(res2["accepted"]),
                              ops_rejected=len(res2["rejections"]))
                for rej in res2["rejections"]:
                    self._exec.meter_write_reject(self.turn_id, "OBSERVER",
                                                  (rej.get("op") or {}).get("op", "?"),
                                                  rej["violation"], 1)
                accepted += res2["accepted"]
            # apply accepted INTERPRET/PROPOSE_RULE/PROPOSE_RELATION/NOTE_EVENT
            for op in accepted:
                self._apply_observer_op(op)
            self._store.commit()
        except Exception as e:
            logger.warning(f"Observer beat failed (non-fatal): {e}")

    def _apply_observer_op(self, op: dict) -> None:
        kind = op.get("op")
        if kind == "INTERPRET" and op.get("ref") and op.get("label"):
            seq = self._store.next_seq(self._run_id, "referent_alias")
            self._store.conn.execute(
                "INSERT INTO referent_alias (run_id, ref_id, seq, turn_id, label) VALUES (?,?,?,?,?)",
                (self._run_id, op["ref"], seq, self.turn_id, str(op["label"])[:60]))
        elif kind == "PROPOSE_RULE":
            self._exec.add_rule(self.turn_id, op.get("template", ""), op.get("ctx", {}),
                                op.get("effect", {}))
        elif kind == "PROPOSE_RELATION":
            self._exec.persist_relation(self.turn_id, op.get("verb", ""), op.get("src", ""),
                                        op.get("dst", ""), op.get("evidence"))
        elif kind == "ANNOTATE":
            seq = self._store.next_seq(self._run_id, "annotate")
            self._store.conn.execute(
                "INSERT INTO annotate (run_id, seq, turn_id, text) VALUES (?,?,?,?)",
                (self._run_id, seq, self.turn_id, str(op.get("text", ""))[:500]))

    def _run_epoch(self, trigger: str) -> None:
        """B7: one budgeted Surveyor pass. Reads the BudgetedView, proposes
        gated expansions; validate_surveyor_proposals disposes."""
        try:
            self._ensure_llm()
            grid = self.prev_grid or []
            head = {"turn": self.turn_id, "level": self._last_levels, "score": 0}
            # the Surveyor must see the REAL action frontier — a hardcoded
            # vocabulary made it propose unrunnable experiments (live-smoke fix)
            avail = getattr(self, "_last_avail", None) or \
                [s["action"] for s in self._adapter.action_vocab()]
            bv = self._renderer.budgeted_view(head, grid, avail,
                                              active_step=self._active_step_text,
                                              predicted_effect=self._active_pred_text,
                                              force_compact=self._force_compact)
            zones, nonces = self._salt_and_capture("surveyor", bv)
            salted_view = "\n\n".join(zones[z] for z in ("Z1", "Z2", "Z3", "Z4", "Z5", "Z6"))
            # §4.2 BudgetedView goal-tree slice: the Surveyor SEES the live
            # goals (so it stops re-proposing admitted tests) with terminal
            # goals folded to a count line — HIPIF-style progress folding.
            salted_view += "\n\n" + self._goal_tree_slice()
            # chain §2.4 tier 2: the DEFICIT block — typed live holes; the
            # Surveyor answers a machine-stated question, not an open sky
            sig_ctx = {"cur": dict(self._prev_signals or {}), "prev": {}}
            salted_view += "\n\n" + self._exec.deficit_view_block(sig_ctx)
            buckets = self._exec.counterexample_buckets()
            out = organs.run_surveyor(trigger, salted_view[:config.B_RENDER * 4], buckets)
            self._record_echo("surveyor", nonces, out)
            res = self._exec.validate_surveyor_proposals(out["proposals"], self.turn_id,
                                                         ctx=sig_ctx)
            self._log_llm("surveyor", out, render_tokens=bv["render_tokens"],
                          ops_accepted=len(res["admitted"]), ops_rejected=len(res["rejected"]))
            if res["rejected"]:
                # §2.1: one typed re-prompt; still-rejected proposals DROP (DPR)
                for rej in res["rejected"]:
                    self._exec.meter_write_reject(self.turn_id, "SURVEYOR",
                                                  rej.get("op", "?"), rej.get("reason", "?"), 0)
                fb = (buckets + "\nYOUR REJECTED PROPOSALS (emit corrected replacements ONLY):\n"
                      + __import__("json").dumps(res["rejected"], default=str)[:1500])
                out2 = organs.run_surveyor(trigger, salted_view[:config.B_RENDER * 4], fb)
                res2 = self._exec.validate_surveyor_proposals(out2["proposals"], self.turn_id,
                                                              ctx=sig_ctx)
                self._log_llm("surveyor", out2, retry_count=1,
                              ops_accepted=len(res2["admitted"]),
                              ops_rejected=len(res2["rejected"]))
                for rej in res2["rejected"]:
                    self._exec.meter_write_reject(self.turn_id, "SURVEYOR",
                                                  rej.get("op", "?"), rej.get("reason", "?"), 1)
            self._store.commit()
        except Exception as e:
            logger.warning(f"Surveyor epoch failed (non-fatal): {e}")

    def _goal_tree_slice(self) -> str:
        """Live goals with their tests (do NOT re-propose these); terminal
        goals folded to counts with queryable ids (§4.2)."""
        c = self._store.conn
        live, done = [], {"ACCEPTED": 0, "REJECTED": 0}
        for g in c.execute("SELECT goal_id, statement, achievement_test_json FROM goal "
                           "WHERE run_id=? ORDER BY goal_id", (self._run_id,)):
            st = self._exec.current_status("GOAL", g["goal_id"]) or "PROPOSED"
            if st in done:
                done[st] += 1
            else:
                live.append(f"  {g['goal_id']} [{st}] {g['statement'][:40]} "
                            f"test={g['achievement_test_json'][:100]}")
        lines = ["GOAL TREE (live — these tests EXIST, do not re-propose them):"] + \
                (live or ["  (none)"])
        lines.append(f"  (+{done['ACCEPTED']} ACCEPTED, +{done['REJECTED']} REJECTED — "
                     f"recoverable by id)")
        return "\n".join(lines)

    def _capture_scorecard(self) -> None:
        """Capture the server scorecard. Robust to the ARC client's empty-card
        edge (get_scorecard can raise ValueError on an empty scorecard) — falls
        back to the raw HTTP body so a row is always persisted."""
        try:
            sc = self.get_scorecard()
            body = sc.model_dump() if hasattr(sc, "model_dump") else {}
        except Exception as e:   # noqa: BLE001 - any client-side failure falls back to raw
            try:
                r = self._session.get(
                    f"{self.ROOT_URL}/api/scorecard/{self.card_id}/{self.game_id}",
                    headers=self.headers, timeout=10)
                body = r.json()
            except Exception:
                logger.warning(f"scorecard capture failed: {e}")
                return
        self._probe.log_scorecard(self._run_id, self.turn_id, self.card_id, self.game_id,
                                  body if isinstance(body, dict) else {"raw": str(body)}, _now())

    def _finish(self) -> None:
        self._capture_scorecard()
        if self._store:
            self._store.close_run(self._run_id, _now(),
                                  "COMPLETED" if self.is_won(self.frames, self.frames[-1]) else "ABORTED")
            self._store.close()
        if self._probe:
            self._probe.finish(self._run_id, _now())
            self._probe.close()
