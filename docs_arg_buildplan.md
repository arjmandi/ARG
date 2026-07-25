# ARG BUILD PLAN

**Aligned Referent Grounding — implementation-ready build spec**
Target repo: `/Users/mohsenarjmandi/workspace/sensi` · New code root: `agents/arg/` · Store: fresh `arg_state.db` (one file per run)
Source of truth: `docs_arg_design.md` §2–§8, the extracted STORE/EXECUTIVE/ORGANS/RENDERER/LOOP/PROBES/CONFIG contracts, and the readiness/minimal-core/observability reviews. Every review resolution and every unserved-invariant fix is folded into Sections 3–11 and cited in Section 11.

Repo reuse surface verified for this plan: `agents/agent.py` (`Agent(ABC)` L23; `MAX_ACTIONS=80` L26; `main` L78; `do_action_request` L137; `take_action` L164; `get_scorecard` L178; `cleanup` L190; `is_won` L218 WIN‑inverted; `choose_action` L225; `append_frame` L130); `agents/frame_analysis.py` (`shape_hash` L81; `state_hash_of` L100; `normalize` L127; `segment` L132; `cell_diff` L245; `_diff_regions` L273; `_bbox_iou` L341; `match` L354 — greedy 3‑pass, no margin; `analyze` L457; `plan_routes` L826; `MAX_COMPONENTS_RENDERED=64` L29); `agents/structs.py` (`GameState` L10 {NOT_FINISHED, WIN, GAME_OVER}; `FrameData` L225, `levels_completed: Optional[int]` L232, `available_actions` L237; `GameAction` L140, `RESET=(0,…)`, `ACTION6=(6,ComplexAction)`; `ComplexAction.set_data` L175); `agents/sensi_llm.py` (`LenientChatAdapter` L47, `_lenient_value` L91; `configure_llm` L120; `do_action_request` + `api_log` DDL L292/L399; `_fact_position_xref` L696; `FrameDiffSignature` L2295, `Player1` L2452, `Experimenter` L2699); `agents/__init__.py` builds `AVAILABLE_AGENTS` from `Agent.__subclasses__()` at import and adds `SensiLLM` explicitly. Probes live at repo root (`probe_audit.py`, `probe_rhae.py`); tests live in `tests/` with `golden_renders.json` precedent.

---

## 1. Scope decision — the minimal faithful core

Build 1 is the **FULL cell as one running config with real J/A toggles**: the complete B1–B8 doing loop over a fresh `arg_state.db`, the adapter seam, the append‑only store spine, the deterministic Executive, all three LLM organs, the six‑zone renderer with R1–R9 + ZCR, the seeded G0/LEARN‑\* records, and consequence‑gated grounding — with `ARG_JOIN` and `ARG_AGENDA` as genuinely flippable switches (they carry the P1 structure and P2 double‑dissociation claims, so shadow‑agenda instrumentation runs whenever `ARG_AGENDA=0`). Consequence‑gating, the salience‑flat roster, active‑chain retention, the trigger set, and Surveyor epochs all ship at their FULL‑cell defaults, each behind an env gate that defaults to 1 so the corresponding ablation is later a one‑line flip, not a re‑architecture. **Deferred** (built as clean seams, not omitted): destructive FISSION execution (the check statistic is stamped, the re‑split op is gated off — a conservative τ plus sub‑τ→NEW+`same_as` covers under‑merge so build 1 never destructively merges); Procedure distillation/replay (tables ship empty, `procedure_id` stays NULL); `PROPOSE_EXPERIMENT`/X‑GATE (dropped from the Surveyor vocab, table unused); `locator_textspan`/long‑context P3 (adapter never mints one); independent ablation arms A3–A11 at `=0` (stubbed behind default‑on gates); `ARG_SPLIT` multi‑model, A10 position/A11 stress knobs, bare/B‑CACHE/raw‑history baselines (separate configs); and the full §8 metric/HRT/health/RHAE read‑only probe suite (added post‑hoc over CORE tables — nothing in the runtime depends on it).

---

## 2. File manifest

**ARG must NOT modify any Sensi organ.** It subclasses `Agent`, registers by adding one import line to `agents/__init__.py` (registration is by `Agent.__subclasses__()` at import; without the import ARG is unselectable via `--agent`), and reimplements the cited `frame_analysis` geometry inside its own adapter — never importing Sensi organs. `frame_analysis.py` is cited in spirit only.

### New package `agents/arg/`
| File | Responsibility (one line) |
|---|---|
| `agents/arg/__init__.py` | Package init; exports `ARG`; imported by `agents/__init__.py` so `ARG(Agent)` registers in `AVAILABLE_AGENTS`. |
| `agents/arg/agent_arg.py` | `ARG(Agent)`: fully overrides `main()` as the B1–B8 beat pump; `is_won`, `choose_action` (thin B1 delegate), `cleanup`, and the `do_action_request` api_log choke‑point override; `MAX_ACTIONS` class attr. |
| `agents/arg/config.py` | The one place every `ARG_*`/`SENSI_*` env var, gate, numeric constant (τ, τ_auto, K, k, θ, K_fiss, TTL, lease, B, W, N_max, L, C_max, k_canary, S, C, epoch cap), and baseline selector is read and pinned with a default. |
| `agents/arg/adapter.py` | The **only** env‑specific seam: `canonicalize/locate/diff/signal_channels/action_vocab`; reimplements `segment/cell_diff/_diff_regions/shape_hash/normalize`; defines `component_hash` and `signature`. Everything above it is Locator‑agnostic. |
| `agents/arg/store.py` | `arg_state.db` DDL (all tables + indices + append‑only triggers), connection/WAL management, per‑run per‑type id minting, version helpers (current = MAX(version)), `seed_import` carryover writer. |
| `agents/arg/predicates.py` | Closed‑predicate JSON‑AST grammar: parse/compile/`eval_now`; signal‑vocabulary admissibility gate; `reopen_class` classifier over the AST. |
| `agents/arg/executive.py` | Every deterministic disposal function (Section 4); the store is never in an LLM's hands. Owns `validate_ingest`, `revision_evidence_gate`, `compute_rank`, `compile_path`/`compile_rule_test`, fission‑check, achievement/goal machinery, and `write_reject_meter`. |
| `agents/arg/renderer.py` | Z1–Z6 serialization, R1–R9 enforcement, the single shared join table (bidirectional Z5↔Z6 coordinate string), R2 no‑naked‑mentions lint, ZCR salting, per‑zone `render_tokens` accounting, `C_max` changeset chunking, small‑context fallback. |
| `agents/arg/organs.py` | The three `dspy.Signature` role contracts (`ObserverDelta`, `SurveyorProposals`, `ActuatorRealize`) + `configure_llm` instantiation (JSON‑string ops, `List[str]` canary_echo) + the call wrappers (retry budget). Ingest validators live in `executive.validate_ingest`. |
| `agents/arg/pather.py` | Bootstrap NAVIGATE: learns+stores an action‑delta/quantum/passable model from `controllable` referents' ConsequenceRecords, then routes (reimplements `plan_routes` logic). Until learned, exposes "no route" so B1 falls back to the Z4 cheapest probe. |
| `agents/arg/seeds.py` | Writes the seeded records once at store init: G0 (VALIDATED root) + LEARN‑ACTIONS/RULES/ENV templates, `provenance=SEEDED`, no game nouns; assigns `reopen_class` at admission. |
| `agents/arg/probe_db.py` | The write‑separate observability store: a single Executive‑owned WAL connection (distinct from the model store) + DDL/writers for `api_log`, `scorecards`, `llm_calls`, `run_config`, `render_capture`, `zcr_salt`, `zcr_echo`, `run_validity`, `startup_probe`. |

### Probes (repo root, mirroring `probe_audit.py`/`probe_rhae.py`) — read‑only, never feed the agent
| File | Responsibility |
|---|---|
| `probe_arg_store.py` | Per‑turn store‑state dump: "state as of T" via MAX(version) with turn_id≤T, rung/status via `status_transition` MAX(seq) turn_id≤T, support/interactions via COUNT turn_id≤T. |
| `probe_arg_log.py` | `turn_record` timeline inspector; overlays WRITE_REJECT/SUBSTITUTION_CAUGHT/REVISION; consistency checks (api_log↔Log action, frame‑hash loop closure, drift/shadow stamp presence, orphan api_log rows). |
| `probe_arg_metrics.py` | The §8 metric table + shadow‑drift double‑dissociation readout, sliced by run_config cell/backbone and beat‑bins (1‑50/51‑150/150+). |
| `probe_arg_legibility.py` | Q11 legibility harness + run‑VALIDITY gate; persists verdict to `run_validity`. |
| `probe_arg_health.py` | Q13 meta‑metric floor monitor; named diagnosis rows on breach. |
| `probe_arg_hrt.py` | Hop Reliability Table per LLM‑necessary hop. |
| *(reuse)* `probe_rhae.py` | Official RHAE over `arg_state`'s `api_log` (columns aligned to Sensi so it runs unmodified). |

### Tests (`tests/`)
`test_arg_store.py` (triggers RAISE, version/MAX, id width, current‑rule) · `test_arg_identity.py` (component_hash/signature golden round‑trip, margin composite, τ/τ_auto routing) · `test_arg_predicates.py` (AST eval, `reopen_class`, signal admissibility) · `test_arg_renderer.py` (golden round‑trip, R2 lint, R7 randomization byte‑identity, cross‑zone coordinate equality, R9 ≤ B, `C_max` chunking) · `test_arg_executive.py` (rung ladder, `predictor_id` support, match tolerance, `stamp_target` SUBSTITUTION, six admission gates, rank determinism) · `test_arg_loop.py` (beat pump, `is_won`, arrival‑handoff, consume‑on‑success, unexplained predicate, offline replay) · `test_arg_seeds.py` (G0 + LEARN‑\* + `reopen_class`) · `tests/golden_arg_renders.json` (fixtures).

---

## 3. Store schema — `arg_state.db` DDL (resolutions applied)

**Pinned store‑wide decisions** (readiness review, adopted): one `arg_state.db` **per run** (cross‑run carryover is an explicit `seed_import` path, below). `version` starts at **1**, gapless monotonic per `(run_id,id)`, **current = MAX(version)**, no `is_current` flag (a mutable flag would violate append‑only). Ids are **per‑run, per‑type, Executive‑minted monotonic counters, zero‑padded width 4** (`R0001`); overflow widens digits, never wraps (the R### render join is byte‑sensitive). `turn_id` is a **single per‑run monotonic counter, +1 per emitted command including RESET**; level is tracked only by `level_counter`, never reset. All lifecycle status is **computed** from `status_transition` (current = `to_status` of MAX(seq)); support/mismatch/interactions/last_verified are COUNT/MAX on read; `Goal.rank` is compute‑on‑render. Knowledge rows carry **no** status columns (the design's field lists are documentation drift).

### Pinned constants (default + why)
| Const | Default | Why / units |
|---|---|---|
| `τ` (merge margin) | **0.15** on 0..1 | below τ → mint NEW + `same_as` HYPOTHESIS; §8 sweep var. |
| `τ_auto` (auto‑BIND) | **0.40** | margin ≥ τ_auto → Executive auto‑binds at 0 LLM calls; only the residue enters `changeset`. |
| margin score `s` | `0.5·[sig==] + 0.3·bbox_IoU + 0.2·(1−min(centroidL1/8,1))`; `margin=s(top1)−s(top2)` | `match()` gives no margin/runner‑up → composite built fresh from `_bbox_iou`/`shape_hash`/cell‑overlap. |
| `k` (→TESTED support) | **2** | HYPOTHESIS→TESTED when support≥k & mismatch<θ. |
| `K` (rule demote) | **3** | K mismatches demote (never delete). |
| `θ` (mismatch ratio) | **0.34** | demotion ceiling. |
| `K_fiss` | **3** | distinct from K; fission‑check mismatch floor. |
| fission stat | point‑biserial `r`(mismatch, binding‑feature); fire when mismatches>K_fiss **and** \|r\|≥0.5 | (build 1: check stamped, re‑split op gated off). |
| `TTL` | **50** turn_id units | negative‑evidence decay, DEMOTED re‑probe, rejected‑goal window (all three). |
| `lease_max_beats` | **20** beats/step | lease‑expiry = T‑trigger + qualifying evidence. |
| `B` (render ceiling) | **6000** tokens/call | inside Sonnet's positional‑bias flat region; **per Anthropic `count_tokens` tokenizer**; confirmed by §2.4.7 sweep. |
| `W` (working set) | **40** referents | active‑chain bindings (never‑evicted) ∪ top‑(40−\|active\|) by eviction rank; shared Z2 rows + Z5 annotations. |
| `N_max` (Σ\|bindings\|) | **24** | irreducible zones + 24 Z6 rows ≤ B by arithmetic (gate‑6). |
| `C_max` (Observer changeset entries/call) | pinned so `C_max·per‑entry‑cost + Z1+Z2+Z5+log_tail(L) ≤ B` (**≈20 at B=6000**) | overflow handled by deterministic pagination or auto‑BIND‑NEW (Section 6). |
| `L` (Observer log‑tail) | **8** turns | attribution window for the unexplained path. |
| `k_canary` | **8** (+ every Surveyor epoch) | ZCR cadence; per‑zone echo floor **≥0.90** at warm state (warmup 2 epochs). |
| `S` / `C` | **12** / **10** beats | T4 stall / epoch rate‑limit (carried unchanged). |
| epoch cap | `3·(level_index+1)` search_calls/level | ≤3 calls/epoch still binds each epoch. |

### DDL (with resolutions)

```sql
-- ===== RUN REGISTRY (scopes every (run,id,version) key) =====
CREATE TABLE run (
  run_id TEXT PRIMARY KEY, game_id TEXT NOT NULL, backbone TEXT NOT NULL,
  seed INTEGER NOT NULL, config_json TEXT NOT NULL, render_ceiling_B INTEGER NOT NULL,
  started_at TEXT NOT NULL, ended_at TEXT,
  status TEXT NOT NULL DEFAULT 'RUNNING'  -- RUNNING|COMPLETED|ABORTED|INVALID_FOR_ATTRIBUTION
);

-- ===== POLYMORPHIC LOCATOR (append-only, immutable) =====
CREATE TABLE locator (run_id TEXT NOT NULL REFERENCES run(run_id), locator_id TEXT NOT NULL,
  kind TEXT NOT NULL CHECK (kind IN ('GridRegion','ActionSlot','TextSpan')),
  created_turn INTEGER NOT NULL, PRIMARY KEY (run_id, locator_id));
CREATE TABLE locator_gridregion (run_id TEXT NOT NULL, locator_id TEXT NOT NULL,
  cells_json TEXT NOT NULL, colors_json TEXT NOT NULL,
  bbox_x0 INTEGER NOT NULL, bbox_y0 INTEGER NOT NULL, bbox_x1 INTEGER NOT NULL, bbox_y1 INTEGER NOT NULL,
  PRIMARY KEY (run_id, locator_id), FOREIGN KEY (run_id, locator_id) REFERENCES locator(run_id, locator_id));
CREATE TABLE locator_actionslot (run_id TEXT NOT NULL, locator_id TEXT NOT NULL,
  action_id INTEGER NOT NULL CHECK (action_id BETWEEN 1 AND 7), param_schema_json TEXT NOT NULL,
  PRIMARY KEY (run_id, locator_id), FOREIGN KEY (run_id, locator_id) REFERENCES locator(run_id, locator_id));
-- locator_textspan ships (kind CHECK includes TextSpan) but the ARC adapter never mints one (P3 deferred).
CREATE TABLE locator_textspan (run_id TEXT NOT NULL, locator_id TEXT NOT NULL, doc_id TEXT NOT NULL,
  start_off INTEGER NOT NULL, end_off INTEGER NOT NULL, PRIMARY KEY (run_id, locator_id),
  FOREIGN KEY (run_id, locator_id) REFERENCES locator(run_id, locator_id));

-- ===== VERSIONED KNOWLEDGE (immutable content rows; current = MAX(version)) =====
-- NOTE: referent.label column DROPPED (moved to append-only alias table below).
CREATE TABLE referent (run_id TEXT NOT NULL REFERENCES run(run_id), ref_id TEXT NOT NULL,
  version INTEGER NOT NULL, kind TEXT NOT NULL CHECK (kind IN ('percept-cluster','region','action','signal')),
  anchor_locator_id TEXT NOT NULL, signature TEXT NOT NULL,   -- signature = shape_hash(color, shape), sha1[:12]
  first_seen INTEGER NOT NULL,
  provenance TEXT NOT NULL DEFAULT 'OBSERVER_BIND' CHECK (provenance IN ('OBSERVER_BIND','FISSION','MERGE')),
  created_turn INTEGER NOT NULL, PRIMARY KEY (run_id, ref_id, version),
  FOREIGN KEY (run_id, anchor_locator_id) REFERENCES locator(run_id, locator_id));

CREATE TABLE referent_alias (   -- INTERPRET label: append-only, cosmetic, current = MAX(seq); R7-inert
  run_id TEXT NOT NULL, ref_id TEXT NOT NULL, seq INTEGER NOT NULL, turn_id INTEGER NOT NULL,
  label TEXT NOT NULL, PRIMARY KEY (run_id, ref_id, seq));

CREATE TABLE relation (run_id TEXT NOT NULL, rel_id TEXT NOT NULL, version INTEGER NOT NULL,
  verb TEXT NOT NULL CHECK (verb IN ('requires','enables','blocks','toggles','part_of','adjacent','same_as')),
  src_ref TEXT NOT NULL, dst_ref TEXT NOT NULL, claim TEXT,
  scope TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK (scope IN ('WITHIN_LIFE','PERSISTENT','UNKNOWN')),
  created_turn INTEGER NOT NULL, PRIMARY KEY (run_id, rel_id, version));

CREATE TABLE rule (run_id TEXT NOT NULL, rule_id TEXT NOT NULL, version INTEGER NOT NULL,
  template TEXT NOT NULL, ctx_pred_json TEXT NOT NULL, effect_pattern_json TEXT NOT NULL,
  scope TEXT NOT NULL DEFAULT 'UNKNOWN' CHECK (scope IN ('WITHIN_LIFE','PERSISTENT','UNKNOWN')),
  ttl_turn INTEGER, test_plan TEXT,     -- test_plan NULL for Observer-authored, non-null required for Surveyor
  created_turn INTEGER NOT NULL, PRIMARY KEY (run_id, rule_id, version));

CREATE TABLE goal (run_id TEXT NOT NULL, goal_id TEXT NOT NULL, version INTEGER NOT NULL,
  parent_goal TEXT, statement TEXT NOT NULL, achievement_test_json TEXT NOT NULL,   -- IMMUTABLE after admission
  discriminator_json TEXT NOT NULL,
  reopen_class TEXT NOT NULL CHECK (reopen_class IN ('MONOTONE_TERMINAL','RECORD_QUANTIFIED')),  -- FIX: set at admission
  rejection_reason TEXT, budget_actions INTEGER NOT NULL, budget_search_calls INTEGER NOT NULL,
  provenance TEXT NOT NULL, admitted_turn INTEGER, created_turn INTEGER NOT NULL,
  PRIMARY KEY (run_id, goal_id, version));
CREATE TABLE goal_binding (run_id TEXT NOT NULL, goal_id TEXT NOT NULL, goal_version INTEGER NOT NULL,
  ref_id TEXT NOT NULL, PRIMARY KEY (run_id, goal_id, goal_version, ref_id));

CREATE TABLE commitment (run_id TEXT NOT NULL, commit_id TEXT NOT NULL, version INTEGER NOT NULL,
  goal_id TEXT NOT NULL, compiled_turn INTEGER NOT NULL, procedure_id TEXT,   -- procedure_id NULL in build 1
  created_turn INTEGER NOT NULL, PRIMARY KEY (run_id, commit_id, version));
CREATE TABLE commitment_step (run_id TEXT NOT NULL, commit_id TEXT NOT NULL, commit_version INTEGER NOT NULL,
  step_id TEXT NOT NULL, step_ord INTEGER NOT NULL, kind TEXT NOT NULL CHECK (kind IN ('NAVIGATE','INTERACT','PROBE')),
  target_ref TEXT, action TEXT, param_schema_json TEXT NOT NULL, predicted_delta_json TEXT,
  then_slot_step TEXT, precond_json TEXT NOT NULL, compilation_turn_id INTEGER NOT NULL,
  lease_max_beats INTEGER NOT NULL, PRIMARY KEY (run_id, commit_id, commit_version, step_id));
CREATE TABLE step_premise (run_id TEXT NOT NULL, commit_id TEXT NOT NULL, commit_version INTEGER NOT NULL,
  step_id TEXT NOT NULL, member_kind TEXT NOT NULL CHECK (member_kind IN ('RULE','GOAL_BINDING','TARGET_REF')),
  member_id TEXT NOT NULL, PRIMARY KEY (run_id, commit_id, commit_version, step_id, member_kind, member_id));

-- Procedure/procedure_slot/experiment ship EMPTY in build 1 (distillation + X-GATE deferred).
CREATE TABLE procedure (run_id TEXT NOT NULL, proc_id TEXT NOT NULL, version INTEGER NOT NULL,
  scope_fingerprint TEXT NOT NULL, distilled_from_commit TEXT, created_turn INTEGER NOT NULL,
  PRIMARY KEY (run_id, proc_id, version));
CREATE TABLE procedure_slot (run_id TEXT NOT NULL, proc_id TEXT NOT NULL, proc_version INTEGER NOT NULL,
  slot_ord INTEGER NOT NULL, action_kind TEXT NOT NULL, referent_role_slot TEXT NOT NULL,
  expected_delta_shape_json TEXT NOT NULL, PRIMARY KEY (run_id, proc_id, proc_version, slot_ord));
CREATE TABLE experiment (run_id TEXT NOT NULL, exp_id TEXT NOT NULL, version INTEGER NOT NULL,
  proposed_turn INTEGER NOT NULL, epoch_id TEXT NOT NULL, target_ref TEXT, action TEXT,
  predicted_delta_json TEXT NOT NULL, discriminates_json TEXT NOT NULL, PRIMARY KEY (run_id, exp_id, version));

-- ===== APPEND-ONLY EVIDENCE + LOG =====
CREATE TABLE referent_lineage (run_id TEXT NOT NULL, seq INTEGER NOT NULL, turn_id INTEGER NOT NULL,
  op TEXT NOT NULL CHECK (op IN ('FISSION_SPLIT','MERGE_CANONICAL')), parent_ref TEXT NOT NULL,
  child_ref TEXT NOT NULL, PRIMARY KEY (run_id, seq));
CREATE TABLE binding_record (run_id TEXT NOT NULL, turn_id INTEGER NOT NULL, component_hash TEXT NOT NULL,
  anchor_cells_json TEXT NOT NULL, anchor_bbox_json TEXT NOT NULL, anchor_signature TEXT NOT NULL,
  bound_to TEXT NOT NULL, is_new INTEGER NOT NULL DEFAULT 0, runner_up TEXT, margin REAL NOT NULL,
  PRIMARY KEY (run_id, turn_id, component_hash));
-- FIX (consequence-grounding): predictor_id + predictor_kind added so support counts only pre-registered predictions.
CREATE TABLE consequence_record (run_id TEXT NOT NULL, turn_id INTEGER NOT NULL, seq INTEGER NOT NULL,
  action TEXT NOT NULL, target_ref TEXT, context_class_id TEXT NOT NULL,
  predicted_delta_json TEXT, observed_delta_json TEXT NOT NULL, match INTEGER,
  predictor_id TEXT, predictor_kind TEXT CHECK (predictor_kind IN ('STEP','RULE')),
  score_event INTEGER NOT NULL DEFAULT 0, level_event INTEGER NOT NULL DEFAULT 0,
  life_event INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (run_id, turn_id, seq),
  FOREIGN KEY (run_id, context_class_id) REFERENCES context_class(run_id, context_class_id));
CREATE TABLE context_class (run_id TEXT NOT NULL, context_class_id TEXT NOT NULL, action_id INTEGER,
  partition_signature TEXT NOT NULL, minted_turn INTEGER NOT NULL, level_index INTEGER NOT NULL,
  PRIMARY KEY (run_id, context_class_id));
CREATE TABLE relevance_edge (run_id TEXT NOT NULL, seq INTEGER NOT NULL, turn_id INTEGER NOT NULL,
  goal_id TEXT NOT NULL, target_kind TEXT NOT NULL CHECK (target_kind IN ('RULE','REFERENT')),
  target_id TEXT NOT NULL, PRIMARY KEY (run_id, seq));
CREATE TABLE status_transition (run_id TEXT NOT NULL, seq INTEGER NOT NULL, turn_id INTEGER NOT NULL,
  entity_kind TEXT NOT NULL CHECK (entity_kind IN ('REFERENT_RUNG','REFERENT_CONTROLLABLE','RELATION','RULE',
    'GOAL','PROCEDURE','COMMITMENT_STEP','EXPERIMENT')),
  entity_id TEXT NOT NULL, from_status TEXT, to_status TEXT NOT NULL, reason TEXT,
  PRIMARY KEY (run_id, seq));
CREATE TABLE turn_record (run_id TEXT NOT NULL, turn_id INTEGER NOT NULL, action TEXT NOT NULL,
  params_json TEXT, target_ref TEXT, pre_frame_hash TEXT NOT NULL, post_frame_hash TEXT NOT NULL,
  raw_diff_json TEXT NOT NULL, predicted_delta_json TEXT, observed_delta_json TEXT, match INTEGER,
  score INTEGER NOT NULL, level_counter INTEGER NOT NULL, state_flags TEXT NOT NULL, lives INTEGER,
  commitment_step_id TEXT,
  source_stamp TEXT NOT NULL CHECK (source_stamp IN ('COMMITMENT_STEP','PROBE','ACTUATOR_LLM','FALLBACK','RESET')),
  render_tokens INTEGER NOT NULL,        -- B8 render TOTAL only; per-call R9 uses llm_calls (probe store)
  shadow_step_id TEXT, drift_ref TEXT CHECK (drift_ref IN ('LIVE','SHADOW')),
  PRIMARY KEY (run_id, turn_id));
  -- FIX (write-separation): canary_echo_json removed from turn_record → lives in zcr_echo (probe store).
CREATE TABLE write_reject (run_id TEXT NOT NULL, seq INTEGER NOT NULL, turn_id INTEGER NOT NULL,
  organ TEXT NOT NULL CHECK (organ IN ('OBSERVER','SURVEYOR','ACTUATOR')), op_type TEXT NOT NULL,
  violation_class TEXT NOT NULL, retry_count INTEGER NOT NULL, PRIMARY KEY (run_id, seq));
CREATE TABLE substitution_caught (run_id TEXT NOT NULL, seq INTEGER NOT NULL, turn_id INTEGER NOT NULL,
  step_target TEXT NOT NULL, landed_target TEXT, PRIMARY KEY (run_id, seq));
CREATE TABLE revision (run_id TEXT NOT NULL, seq INTEGER NOT NULL, turn_id INTEGER NOT NULL,
  step_id TEXT NOT NULL, evidence_ptr TEXT NOT NULL, PRIMARY KEY (run_id, seq));
CREATE TABLE annotate (run_id TEXT NOT NULL, seq INTEGER NOT NULL, turn_id INTEGER NOT NULL,
  text TEXT NOT NULL, PRIMARY KEY (run_id, seq));   -- quarantined; never re-rendered, no budget cost

-- ===== NAVIGATE BOOTSTRAP (readiness BLOCKER: plan_routes needs a learned model) =====
CREATE TABLE action_model (run_id TEXT NOT NULL, seq INTEGER NOT NULL, turn_id INTEGER NOT NULL,
  action TEXT NOT NULL, dx INTEGER NOT NULL, dy INTEGER NOT NULL, quantum INTEGER NOT NULL,
  support INTEGER NOT NULL, PRIMARY KEY (run_id, seq));   -- learned from controllable referents' consequences

-- ===== CROSS-RUN CARRYOVER (readiness BLOCKER: §2.4.6 TESTED→HYPOTHESIS has no path) =====
CREATE TABLE seed_import (run_id TEXT NOT NULL, seq INTEGER NOT NULL, prior_run_id TEXT NOT NULL,
  imported_rule_id TEXT NOT NULL, new_rule_id TEXT NOT NULL, prior_support INTEGER NOT NULL,
  imported_turn INTEGER NOT NULL, PRIMARY KEY (run_id, seq));

-- ===== INDICES =====
CREATE INDEX idx_consequence_turn      ON consequence_record(run_id, turn_id);
CREATE INDEX idx_consequence_target    ON consequence_record(run_id, target_ref, context_class_id);
CREATE INDEX idx_consequence_predictor ON consequence_record(run_id, predictor_id, match);  -- FIX support recompute
CREATE INDEX idx_binding_turn          ON binding_record(run_id, turn_id);
CREATE INDEX idx_binding_bound         ON binding_record(run_id, bound_to);
CREATE INDEX idx_status_current        ON status_transition(run_id, entity_kind, entity_id, seq DESC);
CREATE INDEX idx_goal_binding_ref      ON goal_binding(run_id, ref_id);
CREATE INDEX idx_step_premise_member   ON step_premise(run_id, member_kind, member_id);
CREATE INDEX idx_relevance_goal        ON relevance_edge(run_id, goal_id);

-- ===== APPEND-ONLY ENFORCEMENT (structural, not disciplinary) =====
-- BEFORE UPDATE / BEFORE DELETE ... RAISE(ABORT) on ALL evidence/log tables:
--   binding_record, consequence_record, turn_record, write_reject, substitution_caught,
--   revision, relevance_edge, referent_lineage, context_class, status_transition,
--   referent_alias, annotate, action_model, seed_import.
-- AND (achievement_test immutability FIX) on versioned knowledge tables:
--   referent, relation, rule, goal, commitment, procedure, experiment
--   — EXCEPTED: run(ended_at, status) close-out only.
```

---

## 4. Executive — deterministic function list (`executive.py`)

Every function is 0‑LLM; the store is never in an LLM's hands (§2.1 LLM‑proposes / Executive‑disposes).

| Function → signature | Invariant enforced |
|---|---|
| `differ(pre, post) → ChangeSet{cells,regions}` | Raw integer‑grid diff only, salience‑blind; `post_frame_hash` == Log byte‑for‑byte (loop closure). (cf `cell_diff`) |
| `anchor_extract(grid) → [GridRegion{cells,colors,bbox,signature,component_hash}]` | One salience‑blind code path; anchor & kind machine‑written only. `signature=shape_hash(color, shape)`; `component_hash=sha1(str(color)+"\|"+";".join(sorted "x,y"))[:12]` (position‑inclusive). (cf `segment`/`shape_hash`) |
| `reidentify_bind(candidates, roster) → BIND(hash→R###\|NEW), runner_up, margin` | Composite score `s`; merge iff margin≥τ else NEW+`same_as` HYPOTHESIS. **Built fresh** (`match()` has no margin). |
| `write_binding(turn_id, snapshot, bound_to, runner_up, margin) → binding_record` | Append‑only every B3, turn_id‑joinable; replayable, never a destructive union. |
| `match_predicted_observed(pred, obs, live_step, in_scope_TESTED_rules) → (match, [consequence_record])` | Prediction pre‑committed pre‑emission; Executive‑computed; null effect is evidence. **Stamps `predictor_id`/`predictor_kind`** = the id whose pre‑registered `predicted_delta` produced each receipt. Match tolerance: exact on {event_kind, target signature, sign of score/level/life}; positional deltas by translation‑invariant shape. |
| `stamp_target(emitted_params) → target_ref` (containment lookup) | Never copied from step; step≠landing ⇒ `substitution_caught` + **zero** consequence_record vs step target. |
| `recompute_rung(R###) → ANCHORED\|ENGAGED\|CHARACTERIZED` | ENGAGED iff ≥1 consequence_record; CHARACTERIZED iff ≥1 TESTED rule; monotone by receipts, appearance never grounds. |
| `recompute_status(rule\|relation) → HYPOTHESIS\|TESTED\|DEMOTED` | **`support(RU)=COUNT(consequence_record WHERE predictor_id=RU AND match=1 AND turn_id>RU.created_turn)`** (no ctx‑only retrospective fit); TESTED on support≥k & mismatch<θ; K mismatches demote (never delete), auto‑block dependents, fire T1; negatives carry TTL. |
| `compile_rule_test(HYPOTHESIS rule) → probe/commitment step` | Emits a step whose `predicted_delta = rule.effect_pattern` and whose premise closure cites the rule — the **only** route to accrue support (so CHARACTERIZED is reachable in CORE without X‑GATE). |
| `mint_context_class(action, observed_delta)` | Executive‑minted from ChangeSet partition, never LLM‑named; a fresh class whose delta mismatches every prior receipt flips LEARN‑ACTIONS false ⇒ REOPEN. |
| `fission_check(R###)` / `fission(R###)` *(check CORE; op gated off)* | Check = point‑biserial \|r\|≥0.5 & mismatches>K_fiss (stamps FSN); op (deferred) re‑clusters, re‑attributes by turn_id, demotes citing rules, `split_into` edges. |
| `eval_achievement_test(goal, Log, records) → bool` | Consequence‑based, evaluable‑now, IMMUTABLE after admission; LLM "done" is not an event. |
| `eval_goal_status(goal) → PROPOSED..REOPENED` | Below‑VALIDATED auto‑REJECT NEVER_VALIDATED on budget exhaustion regardless of effect rows; **MONOTONE_TERMINAL latches once true (excluded from re‑check); RECORD_QUANTIFIED re‑evaluated each beat, ACCEPTED→REOPENED on any false read** (+ WITHIN_LIFE reopen‑on‑death). |
| `admit_goal(Goal PROPOSED) → ACCEPT\|REJECT` (gates 1–6) | Bindings ANCHORED+; test compiles & returns false‑not‑error; discriminator present; anti‑oscillation (evidence.turn_id>rejection); Σ\|bindings\|≤N_max. **Computes and stores `reopen_class` here.** |
| `compute_rank(goals) → total order` | Deterministic f(dependency edges, status precedence REOPENED‑ahead, remaining budget, id tiebreak); LLM never writes rank; emits `equal_siblings` for RANK_TIEBREAK admissibility. |
| `compile_path(goal) → [commitment_step]` | Each step stamped compilation turn_id + premise closure {rules∪bindings∪targets}; DEMOTED/REOPENED precond auto‑blocks; no rules ⇒ cheapest Z4 probe (+ `compile_rule_test` for any in‑scope HYPOTHESIS rule), never idle; NAVIGATE only if `action_model` learned else falls back to probe. |
| `revision_evidence_gate(AbortStep\|tiebreak, evidence_ptr) → ACCEPT\|REJECT` | (a) evidence in {match=false CR, demotion, FISSION, REOPENED, lease‑expiry}; (b) turn_id>step compile turn; (c) subject intersects premise closure; lease‑expiry subject=step_id auto‑satisfies (c), turn_id=expiry beat satisfies (b); accepted ⇒ `revision` row; only Surveyor. |
| `validate_ingest(typed op) → ACCEPT\|REJECT` | Reject any op referencing entity/coord absent from ChangeSet/roster; V1 completeness = verdict for every proposed component_hash; R5 dangling & R8 uncontained rejected pre‑emission; ≤2 reprompts. |
| `write_reject_meter(organ, op_type, violation_class, retry_count, turn_id)` | Malformed = hard‑logged failure, never silent degrade; exhaustion drops proposal set, beat proceeds, ChangeSet stays UNEXPLAINED (T4 input); WER floor breach disqualifies attribution. |
| `render_view(zones, working_set) → View + render_tokens` | Fixed positional layout; all joins pre‑computed (R1); per‑call render_tokens≤B else run‑invalid (R9); eviction rank f(active‑chain, recency, rung); R7 annotation‑blind; silent truncation = Q11 fail. (Section 6) |
| `zcr_canary()` / `compute_echo(canary_echo)` | Zone‑prefixed nonces salted, never persisted/joinable/plan‑targetable, excluded from metrics; uniform fail ⇒ adapter defect (invalid); zone‑differential ⇒ R6 fallback. |
| `learn_action_model()` *(pather bootstrap)* | Point‑estimate action→(dx,dy,quantum) from `controllable` referents' consequence deltas; NAVIGATE inadmissible until support present. |
| `distill_procedure(...)` *(deferred, stub)* | Role slots not concrete ids; 1 replay ⇒ TESTED in scope — not exercised in build 1. |

---

## 5. Organs — three dspy role contracts (`organs.py`)

Instantiate via `configure_llm` (Anthropic: `temperature=None` + `thinking{type:adaptive}` + `output_config{effort}`). Ops are emitted as **JSON‑string** output fields and `canary_echo` as `List[str]` (never `List[dict]`) to dodge the dspy‑2.5.32 `JSONAdapter` image‑drop (`LenientChatAdapter._lenient_value` salvages). `canary_echo` nonces are **zone‑prefixed** (`Z2:xxxx`) so a nonce echoed against the wrong zone is a detectable ZCR fault. No LLM output mutates the store — all writes are typed proposals; all status is Executive‑computed.

### Contract 1 — `ObserverDelta` (B5, only on an UNEXPLAINED ChangeSet)
**In:** `changeset: str` (coverage list, only the residue: components with margin<τ_auto or unexplained delta — bounded by `C_max`), `head_view: str` (Z1), `roster_view: str` (Z2), `render_view: dspy.Image` (Z5), `log_tail: str` (≤L=8, keyed by turn_id). **Out:** `ops: str` (JSON array of `BIND`/`NOTE_EVENT`/`PROPOSE_RELATION`/`PROPOSE_RULE(scope=UNKNOWN)`/`INTERPRET`/`ANNOTATE`), `canary_echo: List[str]`.
**Ingest validator (`validate_ingest`):** V1 completeness (verdict for every `changeset` component_hash — silence = violation); V2 candidate‑closure (BIND must be NEW or an R### listed in *that* hash's candidates — off‑candidate rejected); V3 sub‑τ transform (margin<τ → code mints NEW+`same_as`, verdict honored as intent); V4 reference integrity (R5; `NOTE_EVENT.turn_id` resolves in log_tail); V5 grammar (`event_kind` ∈ {appeared,vanished,moved,recolored,resized} only — **never** score/level/life; scope not settable); V6 quarantine (R7: label/text never branched/joined/compiled; `INTERPRET`→append‑only `referent_alias`, `ANNOTATE`→append‑only `annotate`, no budget cost); V7 weightless match (Observer opinion recorded but `match` is Executive‑only); V8 schema (`canary_echo` absent → reject). `PROPOSE_RULE` from Observer stores `test_plan=NULL`, enters HYPOTHESIS; `same_as` from an organ enters as an ordinary HYPOTHESIS relation and **never** triggers a union (merge is code‑only). Retry budget ≤2 (2nd decomposes to one‑op‑type‑per‑call); exhaustion → drop set + WRITE_REJECT + ChangeSet stays UNEXPLAINED. **`canary_echo`** mandatory.

### Contract 2 — `SurveyorProposals` (Epoch, event‑triggered)
**In:** `trigger: str`, `head_view`(Z1), `goal_chain_view` (Z6 cards **incl. `equal_siblings:[G###]`**), `frontier_proposed_view`, `stale_slices_view`, `roster_view`(Z2), `rules_view`(Z3), `untouched_frontier_view`(Z4), `counterexample_buckets`. **Out:** `proposals: str` (`PROPOSE_GOAL`/`PROPOSE_RELATION`/`PROPOSE_RULE`(with test_plan)/`ABORT_STEP`/`RANK_TIEBREAK`; **`PROPOSE_EXPERIMENT` dropped from the vocab in build 1**), `canary_echo: List[str]`.
**Ingest validator:** G‑gates 1–6 for `PROPOSE_GOAL` (referential closure; mechanical test compiles & now‑false; discriminator; non‑duplication+anti‑oscillation; provenance+budget; Σ\|bindings\|≤N_max). R‑gate for Relation/Rule (test_plan required for Surveyor; refs resolve; enters HYPOTHESIS). Revision‑Evidence gate for `ABORT_STEP`/`RANK_TIEBREAK` (clauses a/b/c; RANK_TIEBREAK truncated to the `equal_siblings` set). The Surveyor can never write a fact, promote a rule, mark a goal ACCEPTED, touch an anchor, set rank, or flip agenda state (those ops are absent). Rejections meter WER; gate‑rejected aborts/tiebreaks meter SRR ("revision thrash"). **`canary_echo`** mandatory.

### Contract 3 — `ActuatorRealize` (B1 exception path, ≤1 call when a step underdetermines the command)
**In:** `answer_view: str` (Z1+Z2+Z5+Z6, Z6 states the step imperatively with every dependency re‑cited by id), `target_roster_row: str` (the only roster content on retry), `target_render_crop: dspy.Image` (`«R:id»`‑annotated), `param_schema: str`. **Out:** `action: str` (**Executive‑fixed** by `param_schema` — validated equal, not an LLM choice), `x: int`, `y: int` (ACTION6 only), `canary_echo: List[str]`.
**Ingest validator (R8, pre‑emission):** `(x,y)∈` cited R###'s `anchor.cells`; enum/params match `param_schema`; a coordinate copied from an adjacent roster row is a CAUGHT violation. On failure: one target‑only re‑prompt (distractors≈0); second failure → deterministic anchor‑centroid FALLBACK (stamped, never a silent guess). No goal‑selection/step‑skip field exists. Post‑emission: `stamp_target` by containment (never copied from step) → `substitution_caught` on disagreement; `source_stamp∈{ACTUATOR_LLM,FALLBACK}` by code path; `predicted_delta` committed to Log **before** emission; consume‑on‑success only. **`canary_echo`** mandatory.

**Canary echo (all three):** at cadence `k_canary=8` per organ (plus every Surveyor epoch) the Executive salts one nonce row per zone tier; every organ echoes the observed zone‑prefixed nonces; Executive computes per‑zone echo rate (floor ≥0.90, warmup 2 epochs). Startup image‑receipt round‑trip canary + signal‑vocab probe + per‑game ACTION6‑interface audit must pass (`startup_probe`) before the run counts.

---

## 6. Renderer — Z1–Z6 zones, R1–R9, the bidirectional join (`renderer.py`)

Deterministic Executive code producing the BudgetedView — the only shared state between organs. Fixed top→bottom layout, invariant across turns/games (R6). Per‑zone caps sum under B with headroom.

- **Z1 HEAD** (primacy, IRREDUCIBLE, ≤200 tok/3 lines): line 1 `turn=t level=l score=s lives=v`; line 2 goal chain `G0000 > G0004 > G0007` (rank order); line 3 the active Commitment step **verbatim, byte‑identical to its Z6 copy**.
- **Z2 ROSTER** (corroboration, ≤W=40 rows @ ≤40 tok, stable ascending‑id order): `id | kind | anchor | rung | interactions | last_consequence | serves(goals)`; kind/label R7‑inert; archive folded to one foot line.
- **Z3 RULES/RELATIONS** (≤24 rows: 16 TESTED then 8 `[HYP]`): all R### R2‑substituted; DEMOTED excluded from render, kept in archive; overflow by eviction rank and LOGGED (silent truncation = Q11 fail).
- **Z4 UNTOUCHED FRONTIER** (≤20 pairs): roster × {ACTION1‑5,7; ACTION6 sampled over signature‑equivalence classes} MINUS existing consequence_records; sorted by min interactions then eviction rank.
- **Z5 RENDER** (grid + ≤W annotations): inline **`«R:id rung @r{row}c{col}»`** at each working‑set region's cells (JOIN SIDE A). Small‑context fallback → coordinate‑only joins.
- **Z6 GOAL CARD** (recency, IRREDUCIBLE, ≤N_max=24 binding rows + 4 fixed lines): (1) goal statement (R2‑subst) + achievement_test + status; (2) each bound referent `id | anchor coordinates | render cross-reference | rung | one-line consequence` (JOIN SIDE B); (3) the step imperatively, byte‑identical to Z1, + predicted effect; (4) unresolved mismatches. Active‑chain bindings never‑evicted; other live goals fold to `id|anchor|rung`.

**Rules:** R1 all joins pre‑computed (`serves(goals)`, Z5 annotations, Z6 rows, alias substitution materialized). R2 no naked mentions — post‑render lint rewrites every referent‑denoting token to carry its R###; a naked mention is a hard defect. R3 the join is bidirectional/redundant. R4 position by decision‑criticality, fixed. R5 outputs cite ids or die. R6 fixed template + tiered small‑context fallback (Z1+Z6 irreducible; Z2 by rank; Z3 TESTED‑only; Z5 coordinate‑only); live trigger = ZCR zone‑differential (fallback after 2 consecutive canary epochs below floor). R7 no branching on kind/label (branch only on id/geometry/signature/rung/receipts/bindings) — Q11 randomization test: byte‑identical modulo label text. R8 parameters contained or die (target‑only crop retry, then centroid FALLBACK). **R9 hard per‑call ceiling B=6000** via Anthropic `count_tokens`; per‑call ≤B enforced from `llm_calls` (not the single `turn_record.render_tokens` total, since a beat can carry 2 LLM calls); breach ⇒ run invalid.

**Bidirectional join, spelled out (invariant‑gap fix #1):** one **shared join table** materializes, per working‑set referent, a single pre‑formatted **coordinate string** field. That exact byte string is emitted into **both** Z5's `«R:id rung @r{row}c{col}»` annotation (side A) **and** Z6's "anchor coordinates" column (side B); Z6's "render cross-reference" field **is defined as that same shared‑join coordinate string**. So the id *and* the coordinate — the variable the fact‑xref proof turned on (`_fact_position_xref`, sensi_llm.py:696) — are textually redundant at zero attention distance. `probe_arg_legibility` adds a **per‑beat cross‑zone equality assertion** (distinct from the golden‑file stability test): for every referent rendered in both Z5 and Z6, its id and coordinate strings must byte‑match; any mismatch marks the run INVALID and persists to `run_validity`. This converts R3's "cannot disagree" from an argued property into a checked mechanism.

**Observer `changeset` under B (invariant‑gap fix #4):** the Observer input is under R9 but the changed‑component set is O(frame) on boundary/RESET beats. Pin **`C_max`** = the per‑Observer‑call entry cap such that `C_max·per‑entry‑cost + Z1 + Z2 + Z5 + log_tail(L) ≤ B` (≈20 at B=6000). Overflow is resolved **without** violating V1 completeness by: (a) deterministic pagination — chunk the adjudicated set by mechanical rank (descending size / ascending margin) into ≤`C_max` calls within the same beat, V1 completeness redefined over the union of chunk verdicts (each call ≤B); and (b) mass‑first‑appearance auto‑BIND‑NEW — a component with no prior candidate is minted NEW at 0 LLM calls with deferred characterization, reserving the LLM changeset for the ambiguous residue (margin<τ_auto with ≥1 candidate). Either restores changeset size to O(working set + bounded‑new/beat) so B is never breached on boundary beats.

---

## 7. Doing loop — B1–B8, epochs, `ARG.main()`, seeds (`agent_arg.py`, `seeds.py`)

**`ARG.main()` turn pump** (fully overrides `Agent.main`, base while‑loop unused): (a) `self.timer=time.time()`; (b) one‑time store init — open fresh `arg_state.db`, write SEEDED records, run `seed_import` carryover, `learn_action_model` seed, `startup_probe` (image‑receipt + signal‑vocab + ACTION6 interface); (c) emit beat‑0 `GameAction.RESET` via `take_action` (inherited `frames[0]` is a placeholder `FrameData(score=0)`); then `while not is_won(...) and action_counter < MAX_ACTIONS:` run one beat B1–B8; `action_counter += 1`. `cleanup()` closes `arg_state.db` then `super().cleanup()`. `action_counter` counts only emitted commands (incl. RESET). **`is_won` overrides the WIN‑inverted base: `return frames[-1].state == GameState.WIN`** (whole‑game); `levels_completed++` with NOT_FINISHED must **not** trip it; on GAME_OVER, B1 of the next beat emits RESET (T5). `levels_completed` coalesced None→0. `choose_action` is a thin delegate returning B1's command so the class instantiates. `MAX_ACTIONS` raised off the class attr to the §8 horizon. `do_action_request` is overridden as the single `api_log` choke point (all issuers route through it).

**Beats:**
- **B1 — Actuator select+emit** (0 LLM modal; ≤1 for param realization): live step → execute deterministically at API speed; NAVIGATE carries the **arrival handoff** (`then:` slot — arrival is a consume‑event chaining into the interaction, no re‑decision). No live step → query walk: eval active goal test (ACHIEVED → walk to nearest unachieved by rank, REOPENED ahead of dependents); means‑analysis over TESTED rules → `compile_path`; unmet precond → candidate sub‑goal to Surveyor; no applicable rules → cheapest Z4 probe (never idle). LLM path only when a step underdetermines the command. Emits one GameAction; stamps `source_stamp`; commits `predicted_delta` to Log **before** emission.
- **B2 — emit + TurnRecord** (0 LLM): `take_action(cmd)` + `append_frame`; append `turn_record` keyed by turn_id; `target_ref` stamped by containment (never copied from step). `take_action→None` consumes the beat with no payload; `api_log` still self‑stamps the caught HTTP failure.
- **B3 — perception + identity** (0 LLM): `differ` + `anchor_extract` (salience‑blind, before any LLM); `reidentify_bind` (composite margin) → `write_binding`; merge iff margin≥τ else NEW+`same_as`; update fission stat.
- **B4 — prediction match + consume‑on‑success** (0 LLM): compare pre‑committed `predicted_delta` vs observed for the live step and in‑scope TESTED rules; **stamp `predictor_id`**; MATCH → support++, cursor advances (consume‑on‑success — never on self‑report/arrival); MISMATCH → counterexample++, T1 armed, fission stat updated; null effect is a consequence_record; step/landing disagreement → `substitution_caught`, no receipt vs step target.
- **B5 — Observer IFF unexplained** (0 LLM modal; ≤1+≤2 retries): **explained ⇔ every changed component (a) covered by a live‑step or in‑scope TESTED‑Rule `effect_pattern` within tolerance AND (b) margin≥τ_auto**; otherwise unexplained. **First‑appearance (no prior candidate or margin<τ_auto) forces B5** even with no mismatch. Chunked by `C_max`.
- **B6 — validate + apply + achievement tests** (0 LLM): `validate_ingest`; apply accepted deltas; `recompute_rung`/`recompute_status`; evaluate **all** achievement tests — MONOTONE_TERMINAL latch vs RECORD_QUANTIFIED REOPEN (a freshly minted context class flips LEARN‑ACTIONS false); all goal transitions incl. NEVER_VALIDATED terminal at budget exhaustion.
- **B7 — epoch triggers + fission** (0 LLM to check): check T1–T5 under rate limit (one epoch per C=10 beats except T1); if fission stat fired, **execute fission first, then dispatch the T1 epoch** so the Surveyor reads the post‑fission store (build 1: fission‑execute gated off; check stamps FSN); dispatch ≤1 epoch if a trigger is live and rate permits.
- **B8 — incremental render** (0 LLM): re‑render dirty zones under B (R9); stamp `render_tokens`; salt ZCR canaries at cadence; in agenda‑off cells recompile the shadow step and stamp `shadow_step_id`/`drift_ref` — never rendered.

**Epoch (Surveyor, ≤3 calls, triggered):** T1 contradiction (rate‑limit‑exempt, overrides all), T2 goal transition (incl. ACCEPTED→REOPENED), T3 compilation failure, T4 stall (S=12 beats no new evidence; unexplained‑ChangeSet flags count), T5 boundary (level/game — demote Rules/Procedures→HYPOTHESIS, reset instances, re‑seed). Reads the BudgetedView only; all writes PROPOSED‑on‑entry and gated; aborts/tiebreaks only through the Revision‑Evidence gate; induction hill‑climbs on best‑so‑far. Cap `3·(level_index+1)`/level.

**Seeded records** (`provenance=SEEDED`, no game nouns, written once at init): **G0** `{parent:null, statement:"win the game", bindings:[] (gate‑1 waived for root), achievement_test=OR(levels_completed>prev, state==WIN, score>prev), discriminator=any monotone progress event, status:VALIDATED, reopen_class=MONOTONE_TERMINAL, budget:{actions:MAX_ACTIONS, search_calls:per‑level cap}}` + the test‑the‑test repair (when one progress signal fires, verify the others and repair the predicate — kills the WIN‑vs‑levels_completed circular gate). **LEARN‑ACTIONS/RULES/ENV** expansion templates (game‑agnostic, `reopen_class=RECORD_QUANTIFIED`, Surveyor‑expanded per game only through the six gates; ablatable curriculum, human‑injectable through the same gate).

---

## 8. Probes & observability

All probe tables are **write‑separate** from the model store: a single Executive‑owned WAL connection distinct from `arg_state`'s model tables; write failures increment a `probe_arg_health` counter, never a silent log line. Every probe joins **run_id then turn_id**. Shadow/drift/canary instrumentation lives in the probe store (not on `turn_record`, which the Observer reads as `log_tail`).

| Surface / probe | Hooks | Answers |
|---|---|---|
| `api_log` + `ARG.do_action_request()` override | every HTTP round‑trip regardless of issuer; keyed `(run_id,turn_id,step_id)`; `step_id` increments only on real emissions (retries live in `llm_calls.retry_count`); self‑stamps `run_id`+`source_stamp`+`frame_received`; `response_json` = full raw body incl. frame grids | exactly what ARG sent/received and whether the server accepted it; raw‑frame source for offline replay; orphan rows = caught HTTP failures. |
| `scorecards` + `get_scorecard()` | captured on **every `levels_completed` transition + cleanup**, monotonic `seq`; **`turn_id` column** stamped from the live per‑run counter | server‑recorded score/levels vs ARG's own logs, cross‑checkable at the exact transition turn. |
| `llm_calls` | one row per LLM call: organ, turn_id, backbone, prompt/completion/reasoning tokens, effort, `render_tokens` per zone, `call_idx`, retry_count, ZCR result — **authoritative per‑call source** for R9/parity/slope | where/how much LLM compute per organ per backbone; is cost decoupled from score and flat in store size. |
| `run_config` | one row per run: factorial cell {J,A}, kill‑switch env, baseline mode, backbone, seed, pinned budgets, **`comparison_group` id (game×seed×backbone) + arm label**; the write‑separate `(run_id,card_id,game_id,guid)` registry mirroring `store.run` | which configuration produced this play; the join key for ρ_calls/ρ_tokens parity. |
| `render_capture` | `(run_id,turn_id,call_idx,organ,zone_tier,view_bytes,render_tokens,shadow_flag,rank_snapshot)`; the exact rendered‑view bytes per beat | shadow byte‑identity, per‑zone R9, per‑zone ZCR, and the rank ARG actually used at T. |
| `zcr_salt` / `zcr_echo` | append‑only `(run_id,turn_id,organ,call_idx,zone_tier,nonce[,echoed])` | per‑zone‑per‑organ echo rate; the fixed uniform‑vs‑zone‑differential diagnosis ordering. |
| `startup_probe` | `(run_id,image_receipt_ok,signal_vocab_json,action_interface_json)` | did the vision/signal/ACTION6 gates pass — feeds `run_validity`, explains dead Actuator realizations. |
| `run_validity` | written by `probe_arg_legibility`: `(run_id,verdict,r9_breaches,silent_degrade_count,wer_floor_ok,zcr_uniform_fail)` | which runs are INVALID for attribution; metrics/hrt/health default‑filter `verdict=VALID` and print the excluded set. |
| `probe_arg_store.py` | reconstructs state as of T (MAX(version) turn_id≤T; rung/status via `status_transition` MAX(seq) turn_id≤T; support/interactions via COUNT turn_id≤T — never a HEAD snapshot) | what ARG believed/intended/committed at turn T. |
| `probe_arg_log.py` | `turn_record` ledger + WRITE_REJECT/SUBSTITUTION_CAUGHT/REVISION overlay; checks api_log↔Log action, `hash(response_json.frame)==turn_record.post_frame_hash`, drift_ref non‑null every beat, shadow_step_id non‑null in agenda‑off cells | beat‑by‑beat what/why/predicted/observed/matched, and whether control‑plane, Log, and API agree. |
| `probe_arg_metrics.py` | §8 table over Log/binding/consequence/llm_calls sliced by cell/backbone/beat‑bin (1‑50/51‑150/150+): RGR, DTL, FBR, FCR, APR, FSN, ICR, ECR, WER/DPR, SCL, SRR, ZCR, render/token compliance, completions/score; + shadow‑drift readout (GDS‑bind, GDS‑abandon, DRIFT_total, GA via `drift_ref`) | is the architecture doing what the thesis measures; the P2 double‑dissociation as numbers. `DPR = write_reject(retry_count==budget)` joined 1:1 to its `llm_calls` row. |
| `probe_arg_legibility.py` | pre‑run + per‑beat: golden round‑trip on every producer→consumer schema; nonce/image canary; per‑game interface audit; R7 randomization; R9 per‑beat; shadow byte‑identity; **cross‑zone coordinate equality** | is the plumbing sound / does this run count — persists the verdict. |
| `probe_arg_health.py` | reads §8 metrics vs pre‑registered floors; named diagnosis rows (write‑path degradation, consumption rot, render‑budget breach, revision thrash) | is ARG failing, in which named way, which runs to disqualify. |
| `probe_arg_hrt.py` | Actuator‑param hop, Observer‑BIND hop (FISSION/100 binds), Surveyor hop (admission rejection, SRR) | how reliable is each place the LLM is strictly necessary. |
| `probe_rhae.py` (reuse) | official RHAE over `arg_state.api_log`; columns aligned to Sensi (`action`, `levels_completed`, `game_id`, `card_id`) so it runs unmodified; RESET excluded via `source_stamp='RESET'` filtering; baseline‑missing levels marked | quadratic human‑relative efficiency per completed level. |

---

## 9. Config & kill‑switch map (`config.py`)

Convention: **`=0` kills, `=1`/unset = on**; FULL = every `ARG_*` at default with `ARG_SPLIT=0`. The **adapter is the one env‑specific seam**; store/Executive/organs/renderer/loop stay Locator‑agnostic.

| Env var | Gate (what `=0` does) | Default | Class |
|---|---|---|---|
| `ARG_JOIN` | strips Z5 inline annotations + Z6 bindings + R2 substitution (goal/commitment text still rendered) | 1 | LOAD‑BEARING (P1/P2) |
| `ARG_AGENDA` | kills Commitment persistence (LLM re‑decides each beat); roster+join intact; **shadow‑agenda instrumentation ON** | 1 | LOAD‑BEARING (P1/P2) |
| `ARG_SEARCH` | disables Surveyor epochs (store answers queries alone) | 1 | ablation A3 |
| `ARG_CONSEQ` | disables consequence gating (appearance/assertion promotes rungs) | 1 | ablation A4 |
| `ARG_RETAIN` | drops active‑chain retention → recency‑only eviction | 1 | ablation A5 |
| `ARG_SEEDS` | removes seeded templates (Surveyor expands G0 from scratch) | 1 | ablation A6 |
| `ARG_FLAT` | drops the salience‑flat exhaustive Z2 roster | 1 | ablation A7 |
| `ARG_TRIGGERS` | disables T1‑immediacy + T4‑stall + lease‑expiry (epochs only on T2/T5) | 1 | ablation A9 |
| `ARG_SPLIT` | `=1` runs the 3 contracts on distinct backbones (3‑model cost) | 0 | informational A8, NOT in FULL |
| `ARG_GOALS` | `=0` turns goal machinery off (composes with `ARG_CONSEQ=0` to gate **B‑CACHE**) | 1 | baseline seam |
| `ARG_BASELINE` | selects `{bare,bcache,raw}` baseline config | (unset) | baseline, single‑variable‑exempt |
| `ARG_GOALCARD_POS` | `{adjacent,mid,restated}` (A10; runs `ARG_AGENDA=0` + shadow ON) | adjacent | measurement, NOT in FULL |
| `ARG_STRESS_MULT` | inflates store ~N× at fixed budget (A11 render‑is‑O(working‑set) test) | 1 | stress, NOT in FULL |
| `SENSI_MAX_ACTIONS`/class attr | raises `MAX_ACTIONS` off base 80 to §8 horizon | §8 horizon | budget |

**Threshold/renderer constants** (Section 3 table) are pre‑registered tunables read here: τ=0.15, τ_auto=0.40, k=2, K=3, θ=0.34, K_fiss=3, TTL=50, lease=20, B=6000, W=40, N_max=24, L=8, C_max≈20, k_canary=8, ZCR floor 0.90, S=12, C=10, epoch cap `3·(level_index+1)`.

**Adapter interface (the seam):** `canonicalize(FrameData.frame: list-of-int-grids) → CanonicalState` (**pins which layer(s) to flatten/select — Sensi `normalize()` does %16 per layer — before segmentation**, since layer handling silently changes every anchor/ChangeSet/signature); `locate(state) → [Locator]` (connected‑component GridRegion + signature, salience‑blind); `diff(prev,curr) → ChangeSet`; `signal_channels()` (static verified vocabulary {score 0‑254, levels_completed, state/life} + observed transitions — a test referencing a non‑member is gate‑2 inadmissible); `action_vocab() → [ActionSlot]` (ACTION1‑5,7 simple + ACTION6(x,y) via `set_data` + RESET, opaque symbols).

---

## 10. Milestones

Each subsystem reads its `ARG_*` gate as it lands (ON behavior now, `=0` stubbed behind a default‑1 flag). Ordered so the system **plays a game by M2**, then hardens.

### M1 — Store spine + config + adapter + identity *(offline foundation)*
Delivers `store.py` (full DDL, indices, append‑only triggers on evidence **and** versioned tables), `config.py` (all constants), `adapter.py` (`canonicalize` with pinned layer handling, `locate`, `diff`, `signal_channels`, `action_vocab`; `component_hash` + `signature`), `reidentify_bind` composite margin, id minting, version helpers, `seed_import` writer. **Files:** `store.py`, `config.py`, `adapter.py`, `executive.py` (identity fns), `tests/test_arg_store.py`, `tests/test_arg_identity.py`. **Verify (offline):** golden round‑trip on `signature`/`component_hash`; `BEFORE UPDATE/DELETE` on every evidence + versioned table RAISEs (goal `achievement_test` UPDATE aborts; `run` close‑out succeeds); `current=MAX(version)` gapless; id zero‑pad width 4; margin composite ranks a known top1/top2 with correct runner_up; τ/τ_auto routing (sub‑τ → NEW+`same_as`).

### M2 — Minimal playing loop *(0 LLM, probe‑only — plays a game)*
Delivers `agent_arg.py` (beat pump, `is_won`, `choose_action` delegate, `cleanup`, `do_action_request` choke point, RESET‑on‑GAME_OVER), `seeds.py` (G0 + LEARN‑\*), B2/B3/B4 (differ, binding, consequence_records, turn_record, containment `stamp_target`), degenerate B1 = cheapest Z4 probe, `probe_db.py` (`api_log`, `run_config`, `scorecards`, `startup_probe`), the `agents/__init__.py` import line. **Files:** `agent_arg.py`, `seeds.py`, `probe_db.py`, `executive.py` (differ/binding/match/stamp_target), `agents/arg/__init__.py`, `agents/__init__.py`, `tests/test_arg_seeds.py`, `tests/test_arg_loop.py`. **Verify (live smoke):** `python main.py --agent arg` against a game — emits RESET then probe actions, writes `api_log` + `turn_record` per beat, terminates on WIN or MAX_ACTIONS (never on level completion), `probe_arg_log.py` prints a coherent timeline with `api_log`↔Log action agreement and frame‑hash loop closure.

### M3 — Renderer + shared join + ZCR + render_capture
Delivers `renderer.py` (Z1–Z6, R1–R9, the single shared join table with the byte‑identical coordinate string in Z5+Z6, R2 lint, `C_max` chunking, small‑context fallback), ZCR salting + `zcr_salt`/`zcr_echo`, `render_capture`; reads `ARG_JOIN`/`ARG_FLAT`/`ARG_RETAIN`. **Files:** `renderer.py`, `probe_db.py`, `probe_arg_legibility.py` (partial), `tests/test_arg_renderer.py`, `tests/golden_arg_renders.json`. **Verify (offline):** golden round‑trip on all zones; R7 randomization → byte‑identical modulo label; **cross‑zone coordinate equality** holds and a deliberately corrupted Z6 coordinate is caught → INVALID; per‑call render_tokens ≤ B; `C_max` overflow paginates (union completeness) or auto‑BINDs‑NEW without breaching B.

### M4 — Organs + closed‑predicate grammar + ingest validators *(LLM in the loop)*
Delivers `organs.py` (three `dspy.Signature`s via `configure_llm`, JSON‑string ops, zone‑prefixed `List[str]` canary), `predicates.py` (AST grammar + `eval_now` + signal admissibility + `reopen_class` classifier), `validate_ingest` (all V/G/R/R8 reject classes), the B5 unexplained trigger + `C_max` residue, Actuator R8 realization + FALLBACK. **Files:** `organs.py`, `predicates.py`, `executive.py` (`validate_ingest`), `tests/test_arg_predicates.py`, `tests/test_arg_executive.py`. **Verify:** offline — every reject class fires (off‑candidate BIND, dangling ref, non‑member `event_kind`, uncontained ACTION6, missing canary); AST `eval_now`; `reopen_class` labels G0 MONOTONE_TERMINAL and LEARN‑\* RECORD_QUANTIFIED. Live smoke — startup image‑receipt canary passes; on an unexplained beat the Observer BINDs and the Actuator realizes an in‑anchor ACTION6.

### M5 — Grounding + goals + agenda + rank + rule‑test *(the thesis engine)*
Delivers `recompute_rung`/`recompute_status` with **`predictor_id` support** and the consequence‑grounding fix, `compile_rule_test`, `eval_achievement_test`/`eval_goal_status` with the MONOTONE latch / RECORD_QUANTIFIED reopen, `admit_goal` (6 gates, sets `reopen_class`), `compute_rank` (+ `equal_siblings`), `compile_path`, arrival‑handoff, consume‑on‑success, `revision_evidence_gate`; reads `ARG_AGENDA`/`ARG_CONSEQ`/`ARG_SEARCH`. **Files:** `executive.py`, `predicates.py`, `agent_arg.py` (B1 query walk, B4 consume, B6 tests, handoff). **Verify:** offline — a rule reaches TESTED **only** via receipts with `predictor_id=RU` & turn_id>created_turn (retrospective ctx‑only receipts do **not** count); CHARACTERIZED unreachable without a pre‑registered prediction; G0 is **not** spuriously REOPENED on non‑progress beats while a LEARN‑\* goal REOPENs when a context class is minted; six gates reject/accept correctly; `compute_rank` deterministic. Live smoke — a referent climbs ANCHORED→ENGAGED→CHARACTERIZED off a pre‑committed prediction; a written intention becomes a Commitment obeyed from the next beat (declared→executed conversion > 0).

### M6 — Pather bootstrap + NAVIGATE
Delivers `pather.py` (`action_model` learning + routing) and NAVIGATE step compilation + `then:` handoff. **Files:** `pather.py`, `executive.py` (`learn_action_model`, `compile_path` NAVIGATE branch), `store.py` (`action_model`). **Verify:** offline — routing returns "no route" until `action_model` has support, then produces a plan; `compile_path` falls back to a Z4 probe when unlearned. Live smoke — after enough controllable‑referent consequences, a NAVIGATE step compiles and arrival mechanically chains into its interaction (post‑arrival testing occurs).

### M7 — Epochs + triggers + fission‑check + Surveyor writes
Delivers T1–T5 with rate limit + epoch cap, `fission_check` (statistic stamped, execute gated off), `mint_context_class` → REOPEN, SRR metering; reads `ARG_TRIGGERS`. **Files:** `agent_arg.py` (B7), `executive.py` (triggers, fission_check, mint_context_class), `organs.py` (Surveyor wiring). **Verify:** offline — each trigger fires under its condition; rate limit binds except T1; FISSION executes before the T1 epoch dispatch (Surveyor reads post‑fission store). Live smoke — a T4 stall dispatches one Surveyor epoch that admits a gated goal expansion through the six gates; FSN is stamped.

### M8 — Observability suite + validity/health gates + metrics
Delivers `probe_arg_store.py`, `probe_arg_log.py`, `probe_arg_metrics.py` (+ shadow‑drift), `probe_arg_legibility.py` (full, persists `run_validity`), `probe_arg_health.py`, `probe_arg_hrt.py`; `llm_calls` per‑call authority; RHAE column alignment. **Files:** all `probe_arg_*.py`, `probe_db.py` (`llm_calls`, `run_validity`), `probe_rhae.py` (verify unmodified). **Verify:** run every probe over an M7 live run — store dump reconstructs state as of T from append‑only rows; legibility prints and **persists** a VALID/INVALID verdict; metrics table computes with `verdict=VALID` filtering; `probe_rhae.py --db arg_state.db` runs unmodified and reports per‑completed‑level RHAE.

### M9 — Factorial hardening + baselines + carryover
Delivers real `ARG_JOIN`/`ARG_AGENDA` flips with shadow‑agenda instrumentation (`shadow_step_id`/`drift_ref` stamped, never rendered), the `=0` stubs behind every ablation gate, `ARG_GOALS`/`ARG_BASELINE`, `seed_import` cross‑run carryover (prior TESTED → fresh v1 HYPOTHESIS with `prior_support`), A11 stress knob. **Files:** `config.py`, `agent_arg.py` (shadow compile), `renderer.py` (J gating), `store.py` (`seed_import`), `probe_arg_metrics.py` (drift readout). **Verify:** `ARG_JOIN=0` and `ARG_AGENDA=0` each flip and produce distinct renders/behavior; **shadow byte‑identity** (rendered views identical with shadow on/off); A=0 cell stamps `shadow_step_id` every agenda‑off beat; the P2 double‑dissociation readout shows GDS‑bind vs GDS‑abandon separating; a T5 boundary writes `seed_import` HYPOTHESIS rows; A11 confirms max render_tokens is flat under ~10× store inflation.

---

## 11. Design review summary

**Blockers (resolved before the dependent milestone ships):**
- **Identity/margin has no reuse source** — `frame_analysis.match()` is greedy 3‑pass with no margin/runner‑up. *Resolution:* build a fresh scored bipartite assignment; reuse only `_bbox_iou`/`shape_hash`/cell‑overlap as cost terms; composite `s = 0.5·[sig==] + 0.3·bbox_IoU + 0.2·(1−min(centroidL1/8,1))`, `margin=s₁−s₂`, **τ=0.15**, **τ_auto=0.40** (M1).
- **`component_hash`/`signature` undefined** — `component_hash=sha1(str(color)+"|"+cells)[:12]` (position‑inclusive); `signature=shape_hash(color, shape)` (translation‑invariant; "multiset" struck — 4‑connected same‑color components are monochrome). Frozen with a golden test (M1).
- **No closed‑predicate grammar** — define the `{op,args}` JSON AST {AND,OR,NOT,GE,EQ,EXISTS,COUNT} over the verified vocabulary; `adapter.signal_channels()` is the admissibility table; match tolerance = exact on {event_kind, target signature, sign of score/level/life}, positional by shape (M4).
- **`turn_id` semantics** — single per‑run monotonic, +1 per emitted command incl. RESET; level via `level_counter` only (M1/M2).
- **Cross‑run carryover has no path** — one `arg_state.db` per run + a `seed_import` provenance row copying prior TESTED rules as fresh v1 HYPOTHESIS with `prior_support` (M9).
- **Fission statistic undefined** — point‑biserial `r`; fire when mismatches>K_fiss=3 and \|r\|≥0.5; execute gated off in build 1 (M7).
- **`plan_routes` bootstrap gap** — it returns `[]` without a learned `action_deltas`/`quantum`/`passable`; add `action_model` + `learn_action_model`; NAVIGATE inadmissible until learned, else Z4 probe (M6).
- **Observer `changeset` vs R9 (invariant gap)** — pin `C_max` by the N_max arithmetic; overflow by deterministic pagination (union completeness) or mass‑first‑appearance auto‑BIND‑NEW, so B is never breached on boundary beats (M3).
- **Consequence‑grounding not enforced (invariant gap)** — add `consequence_record.predictor_id`/`predictor_kind`; redefine `support(RU)` to count only its own pre‑registered receipts with turn_id>created_turn; add `compile_rule_test` — without these no referent can legitimately reach CHARACTERIZED in CORE (M5).
- **Achievement‑test reopen selector missing (invariant gap)** — add `goal.reopen_class`, computed once at admission over the AST; MONOTONE_TERMINAL latches, RECORD_QUANTIFIED reopens per beat — otherwise B6 would spuriously REOPEN the delta‑keyed G0 every non‑progress beat (M4/M5).
- **Observability run‑keying/write‑separation** — `run_config` is the write‑separate `(run_id,card_id,game_id,guid)` registry; add `run_id` to `api_log`/`scorecards`/`llm_calls`; add `render_capture`, `zcr_salt`/`zcr_echo`, `run_validity`, `startup_probe`; single WAL probe connection; **`scorecards` gains a `turn_id` column** (invariant gap) so the last observability leg is turn‑keyed (M2/M3/M8).

**Adopted resolutions to spec ambiguities (builder decisions):** status columns moved to `status_transition` (design field lists are documentation drift); `version` starts at 1, current=MAX(version), no `is_current`; ids per‑run per‑type zero‑pad width 4; append‑only enforced by DDL triggers on evidence **and** versioned tables (run close‑out excepted); Observer BIND off‑candidate rejected (V2); `NOTE_EVENT.event_kind` ∈ observable‑channel set only (never score/level/life); Observer `PROPOSE_RULE` stores `test_plan=NULL`, Surveyor requires non‑null (both HYPOTHESIS); `same_as` from an organ is an ordinary HYPOTHESIS relation and never triggers a union (merge is code‑only); `INTERPRET` label → append‑only `referent_alias` (current=MAX(seq), `referent.label` dropped); `ANNOTATE` → append‑only `annotate`, never re‑rendered, no budget cost; Actuator `action` Executive‑fixed by `param_schema`; lease‑expiry evidence auto‑satisfies gate clauses (b)/(c); B5 "explained" pinned (covered by live‑step/TESTED effect within tolerance AND margin≥τ_auto), first‑appearance forces B5; B7 fission‑before‑epoch; two‑LLM‑call beats permitted (worst case 2/beat); `is_won` overrides the WIN‑inverted base and never trips on level completion; RESET counts toward the loop cap but is excluded from the RHAE denominator; `render_tokens` counted with the Anthropic tokenizer, per‑zone breakdown on `llm_calls`, canary nonces zone‑prefixed; `equal_siblings` surfaced for RANK_TIEBREAK; `PROPOSE_EXPERIMENT`/X‑GATE, Procedure distillation, destructive FISSION, and long‑context P3 deferred behind clean seams; env convention `=0` kills, default‑on, FULL = all `ARG_*` default with `ARG_SPLIT=0`; A10=`ARG_GOALCARD_POS`, A11=`ARG_STRESS_MULT`, B‑CACHE=`ARG_GOALS=0`+`ARG_CONSEQ=0`, baselines via `ARG_BASELINE`.