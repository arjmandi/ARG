# ARG — Expected Behavior, Expected Outcomes, and How We Measure Them

*Operational companion to docs_arg_design.md (the claims) and docs_arg_design_coverage.md (what exists — at HEAD: the full agent-code surface, 22/22 suites, fifteen named narrowings). This document states, before the campaign: what a healthy ARG run LOOKS like beat-by-beat, what each mechanism produces as observable evidence, the pre-registered OUTCOMES with their falsified-if clauses, and — for every expectation — the instrument that measures it and the validity gate that lets us trust the number. Nothing here is a result; smoke figures appear only as instrument-calibration reference points. **The pre-campaign measurement checklist is complete** (§4.6): every arm below is runnable today.*

---

## 1. Expected system behavior — the healthy-run profile

A correct ARG run passes through six observable regimes; each row names the mechanically-stamped evidence that proves it (none self-reported).

| Phase | Expected behavior | Proof in the stores |
|---|---|---|
| **Cold start (beat 0)** | RESET; every component minted ANCHORED through one salience-blind path; seeds written (G0 VALIDATED, LEARN-* PROPOSED); config snapshot + honest tri-state startup stamped | `referent` rows; `binding_record.is_new=1` at turn 0; `run.config_json`; `startup_probe` (image_receipt NULL = no vision path) |
| **Coverage / learning** | Probes walk the least-tried frontier (Z4: regime-pruned globals + chain-scoped ACTION6 pairs; pending experiments preferred); every beat writes a coverage receipt — null effects included; referents climb to ENGAGED; movers earn `controllable`; the Observer fires only on unexplained changed beats (paginated changeset, ≤L keyed tail) and proposes closed-vocabulary rules; rejected ops get ONE corrective re-prompt, residue drops as DPR; the Surveyor fires on T3/T4 within the rate limit and per-level cap, proposing goals/rules/relations/experiments over the real action frontier | `decision_mix`; `consequence_record`; rung transitions; REFERENT_CONTROLLABLE transitions; `llm_calls` sparse with `ops_accepted`; `write_reject` retry_count 0/1; `experiment` rows |
| **Rule formation** | In-scope predictions pre-registered BEFORE emission; matches accumulate; TESTED at k=2 with ratio < θ (sticky until K mismatches); the referent reaches CHARACTERIZED; the Observer quiets on explained beats | predictor receipts; RULE→TESTED; REFERENT_RUNG→CHARACTERIZED; observer calls/changed-beat → 0 |
| **Committed play** | The walk compiles from an applicable PROCEDURE first, else means analysis (skipping WITHIN_LIFE rules until re-armed); steps execute with premise closure + predictions; consume-on-success; goal walks PROPOSED→EXPLORED→VALIDATED→ACCEPTED; wrong landings are SUBSTITUTION_CAUGHT (receipt suppressed); a fully-consumed commitment DISTILLS a procedure; a confirming replay makes it TESTED-in-scope | `commitment(.procedure_id)` + `step_premise`; agenda source stamps; CONSUMED transitions; GOAL ladder; `substitution_caught`; PROCEDURE transitions |
| **Repair** | A TESTED rule's failed prediction arms T1; feature-correlated mismatches fire FISSION-CHECK and EXECUTE the split (children minted with lineage, parent retired, citing rules demoted, bindings widened, dependent steps blocked); same_as relations refuted by co-presence or promoted by alternation; the Surveyor may abort steps ONLY via store-resolved contradiction evidence (REVISION rows); TTL re-probes demoted beliefs; budget exhaustion below VALIDATED → NEVER_VALIDATED (anti-oscillation then binds) | T1 epochs; REFERENT_FISSION + FISSION_SPLIT lineage; RELATION transitions + MERGE_CANONICAL; `revision` rows; TTL transitions; REJECTED/NEVER_VALIDATED |
| **Boundary** | On a level event: scorecard captured; TESTED rules AND procedures demote with prior support noted; instances go DORMANT; active steps abort; epoch cap resets; LEARN-* reopen via fresh regime classes | `scorecards`; boundary transitions; REFERENT_LIFE→DORMANT; ACCEPTED→REOPENED |

**Two silences are correct behavior** (both observed on the real server): the Observer is silent on zero-change beats, and the agenda is idle under ignorance (probes + T3 epochs at the rate limit).

## 2. Mechanism → expected observable → instrument

"Healthy" values are pre-registered expectations; ⊙ rows carry a smoke-run reference reading (ft09, real server, Sonnet-5-medium).

| Mechanism | Expected observable | Instrument | Healthy / floor | Breach prints |
|---|---|---|---|---|
| Pre-registration (B4) | predictor receipts once rules exist; `turn_record.match` populated | metrics predictor counts; log probe | rising with rules | — |
| Grounding ladder | monotone climbs; CHARACTERIZED only via TESTED-rule matches | `RGR` (goal-bound CHARACTERIZED share), `grounding_rate_all`, `rung_distribution` ⊙ 0.46 inert-phase | RGR floor **0.05** | "low-grounding" |
| Observer economy | calls ∝ unexplained changed beats; ONE corrective re-prompt max | observer `llm_calls`, retry_count rows | ↓ within level | token-growth diagnosis |
| Agenda (A) | committed stamps once a TESTED rule serves a live leaf; ICR high; SCL ≤ lease | `decision_mix`, `ICR`, `SCL` | ICR ≥ **0.5** responsive games; SCL ≤ **20** | "revision thrash" (SRR) / A9 ossification bracket |
| Procedures §5.4 | second ask compiles FROM the procedure; replay → TESTED-in-scope | `commitment.procedure_id` share; PROCEDURE transitions | reuse > 0 after first distill | — |
| Join (J) | bound refs byte-identical in Z5+Z6 with consequence signatures | `cross_zone_violations` → legibility | **0 violations** | run INVALID |
| Drift decomposition | GDS defined in EVERY cell vs live/shadow reference | `gds_bind`, `gds_abandon`, `drift_total`, `drift_ref_beats` | FULL: both ≈ 0 | the P2 readout itself |
| Identity + fission | exclusive prefiltered binds; movers re-anchor as versions; correlated mismatch → SPLIT | margins; referent versions; `FSN`; FISSION_SPLIT lineage | FSN ≈ 0 absent morphers | HRT Observer-BIND bound |
| Relations | same_as verdicts from co-presence/alternation | RELATION transitions; MERGE_CANONICAL | no TESTED same_as ever co-present | — |
| Scope across deaths | PERSISTENT/WITHIN_LIFE earned; WITHIN_LIFE excluded from plans until re-armed | Z3 scope tags; `rule_scope`; life_event receipts | — | — |
| Write-path integrity | typed rejects metered per organ; drops after retry | `WER`, `wer_per_organ`, `DPR`, reject classes ⊙ gates rejecting real Sonnet ops | WER ≤ **0.25**/organ (≥5 ops) — **wired: breach → INVALID** | "write-path degradation" |
| ZCR consumption | per-zone echoes ≥ floor post-warmup; differential rot flips LIVE compact fallback | `zcr_salt/echo`; legibility rates ⊙ 9/9=1.0 | ≥ **0.90**/zone after warmup **2** | uniform→INVALID; differential→"consumption rot" + R6 compact |
| Render discipline | ≤ B per beat AND per call; flat in store size; archive line, never silent truncation | `max_render_tokens`, `R9_ok`, A11 ⊙ 2382/6000 | ≤ **6000**; slope ≈ 0 | "render-budget breach" → INVALID |
| Revision gate | aborts only on store-RESOLVED fresh premise-relevant contradictions | `SRR`; `revision` rows | SRR ≤ **1.0**/epoch | "revision thrash" |
| Goal hygiene | NEVER_VALIDATED on exhausted budgets; anti-oscillation; monotone latches; G0-AUDIT rows | `APR`; goal_status; annotate G0-AUDIT | APR ≤ **0.05** (decoy arm) | — |
| Epoch discipline | rate limit + per-level cap (base × (level+1)), T1 exempt | surveyor `llm_calls` per level | ≤ cap | — |
| Cost envelope | per-organ calls/tokens; modal beat 0 calls ⊙ 3 calls/20k tokens/30 beats | `llm_calls`, `tokens_vs_beat_slope`, length bins | slope ≈ 0 post-warmup | "token growth" |
| **Chain recognizer (G1)** | `chain_status` consulted every walk; empty store = total DEFICIT with empty-evidence holes (pinned test) | `deficit_stamps`, `deficit_goals`; stamps carry typed holes + evidence | stamps appear in the ignorance phase, holes shrink as rules form | cold-start reporting anything but total DEFICIT = bug |
| **Auto-fill tier (G2, A2)** | derivable holes (HYPOTHESIS rule carrying the needed effect) draft `test RU####` milestones with VERIFIED edges, no LLM | `milestone_goals` (provenance DEFICIT), `edges_verified` | first milestones within ~beats of the first score/level-linked rule | — |
| **Milestone execution (G2)** | experiment-commitments toward HYPOTHESIS rules: NAVIGATE\*+INTERACT with the rule's prediction pre-registered → first non-probe stamps on ls20-class games | `COMMITMENT_STEP` share, `ICR` ≠ None, GDS denominators > 0, per-rule receipts | commitments > 0 wherever score/level-linked hypotheses exist | falsified-if: recognizer live + derivable fills + 0 commitments over ≥3×400 |
| **Honest re-open (G2)** | milestone rule DEMOTED/MISSING ⇒ record-hole DEFICIT; step premise auto-blocks; parent hole re-opens | status_transitions (BLOCKED "premise demoted"), fresh stamps | dead ends never silently absorb the walk | — |
| **Deficit-directed Surveyor (G3)** | epoch view carries the DEFICIT block; proposals cite `fills_hole`; Executive PROVES fills — unprovable = unverified edge | `edge_verified` per proposal; duplicate-proposal rejections | duplicates → ~0 (a stated question, not an open sky) | — |
| **Generative curriculum (G3, A6 inverted)** | `ARG_SEEDS=0`: the LEARN-shaped curriculum is GENERATED from the first deficit brief | goal provenance mix; time-to-first-VALIDATED | learn-shaped goals on ≥2/3 seeds | falsified-if: missing on ≥2/3 → seeds were load-bearing (A6's honest outcome) |
| **Small-model hypothesis (P4×chain)** | deficit-direction turns proposal into slot-filling → flat quality curve across backbones | PROPOSE_GOAL gate-rejection profile, holes-filled rate, `milestone_conversion` per `ARG_MODEL` | mid-tier ≈ small-tier on fill quality | binding constraint prints as a named number |

## 3. Expected outcomes — pre-registered predictions and their measurement recipes

Protocol for every arm: ≥3 unseen games × ≥3 seeds, mean ± stdev; **a run counts only if `run_validity=VALID`**; efficiency numbers only for completed levels.

**P0 — efficacy floor.** Mid-tier + FULL completes levels on ≥3 unseen games. *Measure:* `completions` in FULL. *Falsified-if:* ~0 wins — structural defeater.

**P1 — load-bearing structure.** J0 completes zero/significantly fewer than FULL. *Measure:* completions + parity row (ρ from `llm_calls`). *Falsified-if:* J0 matches, or compute-matched J0 closes the gap.

**P2 — double dissociation (headline).** Kill J → RGR+DTL+GDS-bind move jointly, GDS-abandon flat; kill A → GDS-abandon+ICR move, RGR/DTL flat. *Measure:* the 2×2 cells; A-off cells use the real shadow reference. *Falsified-if:* GDS-bind fails to track J/position, effects cross over, or compute-matched variants close deltas.

**X1/X2 — cross-transfer.** A0 shows GA > J0A0; J0 shows RGR/DTL > J0A0. *Falsified-if:* null → §1 downgrade clause (reframe + LINK-KG/HIPIF named baselines).

**P2b — prior-art delta.** *Now runnable:* B-CACHE (`ARG_BASELINE=bcache`) reproduces canonicalization but leaves completions/GA/ICR at bare levels (argbare). *Falsified-if:* B-CACHE matches FULL on completions.

**P3 — transfer.** Blocked on the TextSpan engine (track work). **P4 — tier claim.** Backbone swap via `ARG_MODEL`; `wer_per_organ` printed per backbone separates emission failure from transfer failure.

**A-arm expectations:** A3 → fewer chains/sub-goals; A4 → FBR/false-TESTED/FCR spike; A5 → DTL/RGR degrade; A6 → slower first-VALIDATED; A7 → interactions=0 coverage collapses; A9 → SCL→lease bound (vs A0 thrash); A10 → GDS-bind tracks position, shadow GDS-abandon persists at max salience; A11 → flat render (test-proven); decoy → APR ≤ ceiling; FISSION kill (`ARG_FISSION=0`) → FSN stamps without splits (detector-only ablation).

**PC — chain sufficiency (batch 4, pre-registered).** FULL-gen (`ARG_SEEDS=0`) ×3 seeds ×400 on ls20 + one small-backbone lane (`ARG_MODEL=haiku-class`). *Measure:* `deficit_stamps`, `milestone_goals/accepted/conversion`, `edges_verified`, COMMITMENT_STEP share, ICR, GDS denominators, goal provenance mix. *Falsified-ifs:* (i) recognizer live + derivable fills + 0 commitments over ≥3×400 → the mechanism (not the game) is charged; (ii) generated curriculum missing learn-shaped goals on ≥2/3 seeds → seeds were load-bearing (A6's honest outcome); (iii) cold-start recognizer reporting anything but total DEFICIT on an empty store → bug.

## 4. How we make sure the measurements can be trusted

1. **Run validity (Q11)** per run, persisted: R9 = 0 breaches (per beat AND per LLM call); silent-degrade = 0; startup tri-state honest; shadow byte-identity over live captures; ZCR uniform failure = 0; **WER floor per organ**. INVALID ⇒ excluded from attribution.
2. **Instrument invisibility:** shadow compile render-invisible (byte-identity test); canaries quarantined; the ZCR live trigger only degrades the RENDER TIER (R6), never state.
3. **Consumption measured:** post-warmup per-zone ZCR; uniform vs differential separates transport defects from rot BEFORE belief-level diagnosis.
4. **Attribution stamped:** source stamps from the executing code path; HRT's mismatch-by-stamp column + actuator-vs-step delta is the param-hop falsified-if; FALLBACK-dominant wins attribute to the backbone, not ARG.
5. **Q13 floors** print named diagnoses every run (WER, RGR, SRR, token slope, ZCR-differential).
6. **Pre-campaign checklist — COMPLETE** (D1–D4): WER floor wired; image receipt honest; archive/overflow lines; bare/raw/B-CACHE comparators; HRT column; length bins; gate-6 test; golden renders pinned; ZCR-differential live trigger; ZCR warmup. Tests themselves are hermetic (no real backbone reachable from a suite).

## 5. Run protocol (commands)

```bash
# FULL cell
ARG_STORE_PATH=$RUN/state.db ARG_PROBE_PATH=$RUN/probe.db \
ARG_MODEL=anthropic/claude-sonnet-5 ARG_REASONING_EFFORT=medium \
uv run main.py --agent=arg --game=<game> --tags=FULL,seed<k>

# FULL-gen (batch-4 default): FULL + ARG_SEEDS=0 — the curriculum is GENERATED
#   from the first deficit brief; seeded LEARN-* becomes the A6 ablation arm
# factorial: J0 → ARG_JOIN=0 | A0 → ARG_AGENDA=0 | J0A0 → both
# ablations: A3 ARG_SEARCH=0 | A4 ARG_CONSEQ=0 | A5 ARG_RETAIN=0 | A6 ARG_SEEDS=0
#            A7 ARG_FLAT=0 | A9 ARG_TRIGGERS=0 | A10 ARG_GOALCARD_POS=mid|restated
#            A11 ARG_STRESS_MULT=10 | fission-detector-only ARG_FISSION=0
# baselines (same probe accounting → parity rows for free):
uv run main.py --agent=argbare --game=<game> --tags=BARE,seed<k>
uv run main.py --agent=argraw  --game=<game> --tags=RAW,seed<k>
ARG_BASELINE=bcache uv run main.py --agent=arg --game=<game> --tags=BCACHE,seed<k>

# per run, in order:
uv run python probe_arg_legibility.py --db $RUN/state.db --probe $RUN/probe.db   # gate first
uv run python probe_arg_metrics.py    --db $RUN/state.db --probe $RUN/probe.db   # §8 row + bins
uv run python probe_arg_health.py     --db $RUN/state.db --probe $RUN/probe.db   # diagnoses + ZCR
uv run python probe_arg_hrt.py        --db $RUN/state.db --probe $RUN/probe.db   # hop reliability
uv run python probe_arg_log.py        --db $RUN/state.db --probe $RUN/probe.db   # beat timeline
```

Tunables (pre-registered, env-sweepable): τ/τ_auto, k/K/θ, K_fiss/r, TTL, lease, B, W, N_max, C_max, L, k_canary, ZCR floor+warmup, S, C, epoch cap, WER floor. Game selection: committed play needs mechanics that respond within the probe budget — ls20-class first; ft09-class inert openings exercise coverage/economy only.

## 6. Reference instrument readings (smokes, not results)

Smoke-2 (ft09, 30 actions, real server): 31 round-trips; 65 referents; rungs {ANCHORED 35, ENGAGED 30}; grounding_rate_all 0.46; PROBE-only mix (inert phase, correct); Surveyor 3 calls / 20,091 tokens / 14 ops admitted (9 experiments) + 5 gate-rejected; ZCR 9/9 = 1.0; max render 2,382 ≤ 6,000; scorecard captured; VALID on non-vacuous checks. Calibration points only.

## 7. Residual narrowings that scope interpretation

The fifteen deliberate simplifications are enumerated in docs_arg_design_coverage.md §3 (greedy-exclusive assignment, one-retry budget, GA closure, current-regime classes, query-side fission re-attribution, same_as-only relation receipts, committed-only budget spend, validator-based R5, unpersisted tie-breaks, pending B/ZCR calibration sweeps, auto-bound AMBIGUOUS band, deterministic procedure rebinding, unconsumed `discriminates`, shared per-call budget for comparators, exclusion-based WITHIN_LIFE discipline). None touches forgery-resistance or attribution; any that matters to a specific claim must be restated next to that claim in the paper.
