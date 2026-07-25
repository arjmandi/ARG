# ARG Implementation Review — code vs. docs_arg_design.md

*Independent fresh-eyes audit (Fable 5, max effort), 2026-07-17. Method: full read of docs_arg_design.md (§1–§9 + merge decisions + ledger), docs_arg_buildplan.md §10–§11 (the build's own promised scope), every file in `agents/arg/` (2,828 lines), all 13 test suites, all 6 probes, wiring greps for every thesis mechanism and config gate, plus re-interpretation of the ft09 live-smoke data. All 13 suites pass at review time.*

---

## Verdict

**The state/validation substrate faithfully implements the design and is genuinely well-tested. The behavioral half of the design — the part the thesis is about — is not implemented: it exists as tested, store-backed functions that the live loop never calls.** The build plays probe-only with excellent bookkeeping. As built today it cannot run the design's pre-registered experiments (P0–P4, X1/X2, the J×A factorial), because:

- **A (the agenda) is behaviorally inert.** No commitment is ever compiled, executed, or consumed in play. `_beat` (agent_arg.py:132) unconditionally calls `_compose_probe`; `compile_navigate`/`write_commitment` (executive.py:717/743) and the Actuator organ (`organs.run_actuator`) have **zero callers outside tests** — `run_actuator` has zero callers anywhere. Flipping `ARG_AGENDA` changes only a stamp, not behavior: both factorial A-cells run identical probe-only play.
- **The grounding ladder freezes in live play.** The loop writes every ConsequenceRecord with no pre-registered prediction (`agent_arg.py:167-171` — `predicted_delta`/`match`/`predictor_id` never passed). Rule support/mismatch therefore never accumulates live → no rule ever reaches TESTED live → **CHARACTERIZED is unreachable in real play** (the smoke confirms: 16/16 referents ANCHORED, RGR 0.0). T1 (contradiction) is hardcoded `False` (agent_arg.py:214), so contradiction epochs and live fission can never fire, and `_change_explained` (agent_arg.py:227) can never become true — the Observer never "quiets as rules climb."
- **J (the join) is vacuous in live play.** No referent is ever bound to any goal live (the only binder is Surveyor `PROPOSE_GOAL`, and `_active_chain` is hardcoded to `[G0]` — renderer.py:79-89 — whose bindings are empty). Z6 therefore renders zero bound referents, and `cross_zone_violations` passes trivially over an empty set. Worse, **Z5 contains no grid content at all** (renderer.py:181-196 renders an annotation list, never the render; `_region_color` returns 0 for every region) — the organs never see a single pixel, so there is nothing for the join to join. The mechanism that generalizes the 0/200→3/3 fact-xref result is present as code and offline tests, absent as live behavior.

This is not a scope disagreement with the design alone — **the buildplan's own M5 promised the wiring** ("`compile_path`, arrival-handoff, consume-on-success … `agent_arg.py` (B1 query walk, B4 consume, B6 tests, handoff)", live-verify: "a written intention becomes a Commitment obeyed from the next beat (declared→executed conversion > 0)"; "a referent climbs ANCHORED→ENGAGED→CHARACTERIZED off a pre-committed prediction"). The M5 commits delivered the Executive functions and their offline tests, not the loop wiring or the live criteria.

**Correction of the earlier in-session verification (docs_arg_verification.md, "10/10 invariants served"):** that audit was accurate at the level it checked — *structural* invariants (can a forged write reach the store; is the join byte-identical when rendered; is the store append-only). It did not check *behavioral* fidelity (does live play traverse the designed loop), and its live-smoke VALID verdict rested on three vacuous checks: R9 passed because `render_tokens` is stamped 0 every beat (agent_arg.py:176-183 never passes a real count); shadow byte-identity passed because `render_capture` is never written live (`Renderer.capture` has zero callers); join equality passed because zero bindings existed. The 10/10 report should be read as "the substrate cannot be forged," not "the design is implemented."

---

## 1. What is faithfully implemented (verified in code, with mechanism)

| Design element | Mechanism | Status |
|---|---|---|
| §2.1 LLM-proposes/Executive-disposes (write side) | Organs emit typed JSON only; `validate_observer_ops` / `validate_surveyor_proposals` / `validate_actuator` gate ingest; only accepted ops apply (agent_arg.py:278) | **Solid.** Live smoke showed real Surveyor proposals correctly gate-rejected |
| §2.2 schema | store.py DDL covers the full record system incl. versioning keys, reopen_class, source_stamp/shadow_step_id/drift_ref, WRITE_REJECT/SUBSTITUTION/REVISION tables | **Complete as schema** (several tables never written — §3 below) |
| Append-only / no last-writer-wins | 29 protected tables with `BEFORE UPDATE/DELETE RAISE(ABORT)` triggers (store.py:172-181); status computed from `status_transition`; `(run,id,version)` keys; widen-not-wrap minting | **Enforced at SQL layer; tested** (a test's own illegal UPDATE was caught by the trigger during this session) |
| §2.3 tier definitions + §2.6 margin rule | `reidentify` (executive.py:59): composite 0.5/0.3/0.2 score, margin=s₁−s₂, τ/τ_auto routing, sub-τ → NEW + `same_as` HYPOTHESIS relation; MENTIONED quarantine holds (nothing mints from LLM text) | **Faithful offline** (routing caveats in §3.8) |
| Consequence-grounded promotion (as functions) | `rule_support_mismatch` counts only own pre-registered post-creation receipts (executive.py:392-406); `recompute_rung` requires a TESTED-rule matched receipt for CHARACTERIZED (423-449) | **Exactly the design's invariant** — tested; unreachable live (§3.2) |
| §3.3 admission gates 1–5 | `admit_goal` (executive.py:473-522): referential closure, compiles-over-verified-channels (predicates.py `compiles` rejects unverified channels and appearance tests), discriminator, dup+anti-oscillation, evidence | **Faithful; each rejection tested.** Gate 6 arithmetic present but untested |
| §3.4 monotone latch vs reopen | `classify_reopen` + `evaluate_all_goals`: MONOTONE_TERMINAL latches; RECORD_QUANTIFIED reopens on false | **Faithful for the ACCEPTED↔REOPENED pair** (rest of status machine missing — §3.6) |
| Salience-blind enumeration | `adapter.segment` one code path for all components (adapter.py:89-121); Z2 fixed-width row per working-set referent, `interactions=0` printed; eviction rank has no size term (renderer.py:107-110) | **Faithful; tested** (3-cell plate = 40-cell wall) |
| R3 join construction + corruption check | one `_coord_string` (renderer.py:120) emitted in Z5 and Z6; `cross_zone_violations` | **Byte-identical by construction; tested offline** — vacuous live (§3.3) |
| R9 ceiling | R6 zone-shedding + terminal hard clamp (renderer.py:258-273); tested incl. an 80k-char goal | **Real in the renderer**; the per-beat TurnRecord stamp is 0 (§3.7) |
| Generality contract | adapter is the only env-specific file; seeds carry no game nouns (regex-tested); `kind` machine-derived with DB CHECK; whole-game `is_won` | **Faithful** |
| Observability plumbing | `do_action_request` choke point; write-separate probe DB; probes reconstruct state-as-of-T from append-only rows | **Faithful and useful** (metric definitions deviate — §3.7) |
| WIN-vs-levels deadlock removal | disjunctive G0 + `is_won` on `GameState.WIN` only; loop test proves bare level completion doesn't terminate | **Faithful** |
| Cross-run carryover | `import_prior_rules`: TESTED → fresh v1 HYPOTHESIS + `seed_import` audit row | **Faithful as a function; test-only** (no caller in the loop; T5 does not run it — §3.6) |

The offline test discipline over this substrate is genuinely good: 13 suites, ~140 assertions, every ingest reject class fired, append-only proven, identity goldens, reopen asymmetry, A9 trigger gating, A11 render plateau under 10× store inflation, shadow render byte-identity (as a fresh-store comparison), ARG_JOIN/FLAT/RETAIN/SEEDS/GOALS flips.

---

## 2. The purpose test — can this build run the design's experiments?

§1's falsifiable program requires, in every cell: completions (P0), the J×A factorial with **RGR, DTL, GDS-bind, GDS-abandon, DRIFT_total, GA, ICR** (P2/X1/X2), attribution stamps, and parity rows. Status:

| Requirement | Status in this build |
|---|---|
| P0 (mid-tier + full ARG completes levels) | Not testable as "full ARG" — the FULL cell currently plays the same probe-only policy as every other cell; completions would attribute to enumeration, not to J/A |
| J×A factorial | **Not executable.** A on/off: identical behavior (no live agenda). J on/off: changes renders that only the Observer/Surveyor see; no decision path consumes the join (the Actuator, the only designed consumer of Z6, is never invoked) |
| GDS-bind / GDS-abandon / DRIFT_total / GA / ICR / DTL / FBR / FCR / APR / SCL / ECR / DPR / ZCR | **None computed.** probe_arg_metrics implements 4-ish of §8's ~17 metrics; the shadow reference step needed by GDS is a synthetic string `SHADOW-{action}-t{n}` (agent_arg.py:175), not the design's "Executive compiles shadow Commitments from the live store exactly as in FULL" |
| RGR | Computed with a deviating definition (ENGAGED+CHARACTERIZED over *all* referents; design §8: "TESTED+ / all among **goal-bound** referents") — and pinned at ~0 live by §3.2 |
| WER | Computed with a deviating denominator (game-action api rows, not LLM write calls per organ) |
| Attribution (Q12) | source_stamp exists but only {PROBE, RESET} ever occur; COMMITMENT_STEP/ACTUATOR_LLM/FALLBACK unreachable |
| ZCR + Q11 harness | Salting/echo/floor entirely unwired (§3.5); R9 per-beat stamp constant 0; shadow byte-identity live check reads an empty table |

**Conclusion: the build does not yet serve the design's purpose.** It is the correct *foundation* for it — the hard invariants are enforced at the right layer, and most missing pieces have their store schema, their Executive function, and their offline test already waiting.

---

## 3. Gap register (ranked)

### S1 — BLOCKER: the agenda never acts (§4.3, §5.1 B1, §5.3)
`_beat` = probe, always. No query walk (evaluate → rank walk → means analysis → compile → execute), no step execution, no consume-on-success, no lease decrement/expiry, no premise auto-block, no `SUBSTITUTION_CAUGHT`, no arrival handoff in play. `compute_rank`, `compile_navigate`, `write_commitment`, `validate_actuator`, `revision_evidence_gate` are all built and tested — and all test-only. `write_commitment` also writes **no `step_premise` rows and no `predicted_delta`** (executive.py:748-755 hardcodes `precond="{}"`, premise closure absent), so even the tested commitment path lacks the two fields §5.3's gate consumes. GDS-abandon — the abandonment half of the thesis, whose existence proof is the 171-un-committed-turns run — has no live mechanism to repair or measure.

### S2 — BLOCKER: no pre-registered predictions live (§2.2 ConsequenceRecord, §5.1 B4)
`predicted_delta` is "committed to Log BEFORE the action is emitted" in the design; the loop never writes one. Downstream casualties: TESTED unreachable live → CHARACTERIZED unreachable → Z3 shows `[HYP]` forever → `_change_explained` never true → Observer fires on every changed beat forever (unbounded LLM cost, the opposite of "settled transitions cost zero calls") → T1 dead → live fission dead → FBR/HRT ground-truth columns empty. The `compile_rule_test` promised by buildplan M5 does not exist as a function anywhere.

### S3 — BLOCKER: the join never fires live; organs are blind (§2.5)
(a) No live goal-referent bindings: nothing binds referents to G0/LEARN-* (design §3.2's LEARN templates are *about* referents; the seeds carry no bindings and nothing adds any). (b) `_active_chain` hardcoded `[G0]` (docstring says "no live selection until M5"; M5 never upgraded it). (c) **Z5 renders no grid** — an annotation list with `color=0` on every line (a false statement about every region), so the Observer's "view" contains no world content whatsoever; the design's Z5 is "the grid render with inline joins." (d) R2 (`label#R###` substitution) is entirely absent — no substitution code exists. The single mechanism the design calls "the load-bearing surface" is offline-verified and live-inert.

### S4 — MAJOR: shadow-agenda instrumentation is a placeholder (§8)
Design: Executive compiles real (never-rendered) shadow Commitments per beat in agenda-off cells; drift metrics reference them. Code stamps a synthetic string. Every drift metric computed against it would be meaningless; A10 and both P2 halves are not executable. (The Q11 "shadow byte-identity" *offline* test compares two fresh stores' renders — fine — but live capture is unwired, so the per-run harness check reads an empty table.)

### S5 — MAJOR: ZCR is designed, half-built, unwired (§2.5)
`salt_canaries` and `capture` have zero callers; `zcr_echo` is never written by any code; no echo-rate computation exists; `K_CANARY`, `ZCR_FLOOR`, `ZCR_WARMUP_EPOCHS` are read nowhere; the "missing canary" reject class (buildplan M4 verify) is absent from the validators; R6's designed live trigger (zone-differential ZCR failure) is replaced by token-budget-only. `canary_echo` is parsed from organs and stored as JSON in llm_calls — then never compared to anything. Consumption is assumed, not measured — the exact failure §2.5 exists to prevent.

### S6 — MAJOR: the Revision-Evidence gate trusts the LLM (§5.3)
`revision_evidence_gate` (executive.py:914-927) validates `kind`/`turn`/`subject` **as supplied by the Surveyor's own output** — it never resolves `evidence_ptr` to an Executive-stamped record in the store. The design's central clause ("a merely-citable record is not a contradiction") is inverted: an *uncitable* record passes. Currently harmless only because admitted aborts do nothing (no REVISION row is ever written — `INSERT INTO revision` appears nowhere; no step status changes; `step_premises` comes from a caller-supplied dict, never the store). Two broken halves canceling into inertness is not enforcement.

### S7 — MAJOR: the §8 metrics layer is ~4/17, with deviating definitions (§8, Q9, Q13)
Missing: GDS-bind, GDS-abandon, DRIFT_total, GA, ICR, DTL, FBR, FCR, APR, SCL, ECR, DPR, SRR-as-reported (computed in-return, never persisted), FSN, ZCR, token-vs-beat slope. Deviating: RGR (denominator + rung threshold), WER (denominator). Vacuous: R9 compliance (TurnRecord `render_tokens`=0 every beat), LLM token accounting (`_log_llm` hardcodes 0s; dspy history never read). Q13's floors run on three numbers, two of them vacuous.

### S8 — MODERATE: identity lifecycle gaps (§2.6, §4.1, B3)
(a) **Anchors never update on re-bind** — B3's "anchors updated" is unimplemented; a mover's roster/Z5/Z6 coordinates, containment checks, and frontier targets go stale immediately, and its bind margin decays toward duplicate-minting (`NEW+same_as`) as it travels. (b) Assignment is greedy per-component with **no exclusivity** (two components can bind the same referent in one beat) — design specifies Hungarian assignment. (c) The AMBIGUOUS band (τ ≤ margin < τ_auto) is defined and then treated identically to AUTO_BIND (executive.py:249-268); the designed Observer-BIND routing for the residue does not exist — and in the live loop `validate_observer_ops` is called with `candidate_hashes=set()` (agent_arg.py:272), so any Observer BIND is auto-rejected and the completeness invariant is vacuously satisfied. The Observer-BIND hop (HRT row 2) cannot occur.

### S9 — MODERATE: lifecycle/decay machinery absent (§2.4, §3.4)
No level-boundary demotion + instance reset (T5 fires a Surveyor epoch only; the 0/16 lesson is implemented cross-*run* but not cross-*level*; referents accumulate across RESETs and levels forever). No TTL decay anywhere (`TTL` read nowhere; demoted records never become re-probeable; "beliefs decay toward doubt" unimplemented). No lease enforcement (stored per step, never decremented/checked). No budget decrement → the NEVER_VALIDATED terminal rule can never fire → `_anti_oscillation_ok` guards an empty set, APR is undefined, the decoy stress arm has no defense to measure. No EXPLORED/VALIDATED transitions (nothing consumes steps; discriminator variance never observed). No evidence compaction. No Procedures (§5.4 — schema only). No Relation lifecycle (relations are minted as HYPOTHESIS and never promote/demote; Surveyor PROPOSE_RELATION is "admitted" but **never written to the store** — executive.py:892-897).

### S10 — MODERATE: fake or dead config seams (§8 arms)
Read nowhere: `ARG_CONSEQ` (A4 — flipping it changes nothing; the anti-cascade ablation cannot run), `ARG_SPLIT` (A8), `ARG_GOALCARD_POS` (A10), `STRESS_MULT` (A11 runs via method arg — acceptable), `TTL`, `L_LOG_TAIL` (Observer log_tail is `str(observed)[:400]`, not ≤L Log turns keyed by turn_id), `K_CANARY`, `ZCR_FLOOR`, `ZCR_WARMUP_EPOCHS`. `ARG_BASELINE` gates organs off for any non-empty value — but B-CACHE per §8 is a *specific configuration* (ids+alias+R2+Z2/Z5 retained, consequence gating off, goal machinery off, Actuator-LLM on), which is not constructible from the current gates. P2b is therefore not executable either.

### S11 — MODERATE: seeded-goal semantics defects (§3.2)
`default_context_class` mints one class **per action** (CC1…CC7), while `_learn_actions_satisfied` requires every action to have a receipt in **every** class — ACTION1 can never have a receipt in ACTION2's class, so **LEARN-ACTIONS is unsatisfiable by construction** (it can never fire, hence also never legitimately reopen; the engine test forced ACCEPTED manually). It also hardcodes `level_index=0`. LEARN-RULES ("every changed referent class participates in ≥1 TESTED rule") is approximated by `count(TESTED) ≥ count(changed referents)` with no participation join and no window-contradiction-rate term. LEARN-ENV drops "or unreachable by grounded means." G0's "test-the-test audit" is absent. ENGAGED's "referent in scope" is approximated as "target or mentioned in a delta" — far narrower than the design's in-scope semantics (the smoke's 16×ANCHORED confirms the practical effect).

### S12 — MINOR (collected)
Surveyor vocabulary omits `PROPOSE_EXPERIMENT` entirely (experiments/`discriminates:[rule_ids]` — §9.4's defense — cannot be expressed; the table is never written). `SURVEYOR_CALLS_PER_EPOCH`(≤3) and the per-level epoch cap are not enforced (one call per epoch happens to satisfy it). Hill-climb "counterexample buckets" input is the literal string "(none)". `mover_centroid` = smallest referent heuristic (declared bootstrap). Z4 enumerates (referent × simple-action) pairs that can never be marked done (simple actions have no target; only ACTION6 pairs prune). `frontier_probe` ignores "in active goal scope." Observer `log_tail` lacks last-action+prediction keying. `EXPLORED` precedence in `compute_rank` orders REOPENED<PROPOSED<EXPLORED — design's walk is by rank over the dependency/status order (acceptable simplification, unused live anyway). `probe_rhae.py` compatibility (buildplan M8 verify) never actually verified. `golden_arg_renders.json` (buildplan M3) never created. `controllable` annotation (REFERENT_CONTROLLABLE) is never computed despite the action-model learner existing — the schema hook is dead.

---

## 4. "Tests the correct parameters and limitations" — assessment

**Parameters (pinned constant → consumed by code → asserted by a test):**

| Constant | Pinned | Consumed | Tested |
|---|---|---|---|
| τ=0.15, τ_auto=0.40 | ✓ | ✓ reidentify | ✓ routing incl. sub-τ→NEW+same_as |
| k=2, K=3, θ=0.34 | ✓ | ✓ rule status | ✓ TESTED at 2, DEMOTED at 3, retrospective excluded |
| K_fiss=3, FISS_R=0.5 | ✓ | ✓ fission_check | ✓ r=−1.0 fires; quiet under floor |
| B=6000 | ✓ | ✓ budgeted_view | ✓ incl. terminal clamp (80k-char goal → ≤B) |
| W=40 | ✓ | ✓ working_set | ✓ A11 plateau at 10× store |
| S=12, C=10 | ✓ | ✓ EpochController | ✓ T1 exemption, T4 stall, A9 gating |
| MAX_ACTIONS=200 | ✓ | ✓ loop | ✓ via env in loop tests |
| N_max=24 (gate 6) | ✓ | ✓ admit_goal | **✗ no test** |
| C_max=20 | ✓ | ✓ (truncates the candidate list — not the designed ChangeSet chunking) | ✗ |
| lease=20 | ✓ | stored only, never enforced | ✗ |
| TTL=50 | ✓ | **✗ read nowhere** | ✗ |
| L=8 | ✓ | **✗ read nowhere** | ✗ |
| k_canary=8, ZCR floor=0.90, warmup=2 | ✓ | **✗ read nowhere** | ✗ |

**Limitations (§9) — is each admitted failure mode instrumented as promised?**

- §9.1 (identity sensitivity): FSN statistic ✓ built+tested; **never runs live** (needs match≠NULL); BindingRecords ✓.
- §9.2 (closed vocabularies): WER ✓ (deviating denominator); DPR ✗; SRR computed but not persisted/reported; the lease bound that "caps the delay" ✗ unenforced.
- §9.3 (Goodhart): REOPENED ✓; FCR ✗; context-class minting live ✗ (`divergence_context_class` test-only; the loop only mints per-action base classes).
- §9.4 (wrong world model): `discriminates` field / Experiments **inexpressible** in the implemented Surveyor vocabulary.
- §9.5 (weak Surveyor): SCL ✗; A0/A9 bracket — A9 real, A0 degenerate (see S1/S4).

**Test-design observations.** The suites verify what the code does, not always what the design demands: the integration test *mocks the organs to emit exactly the op types the loop can apply*, which makes the unwired op types (BIND with real candidates, ABORT_STEP effects, PROPOSE_RELATION persistence) invisible; no test drives a commitment through the loop (the buildplan's own M5 live criterion); no test asserts a live referent reaches CHARACTERIZED; the loop tests' "legibility VALID" assertions inherit the three vacuous checks. Offline coverage of implemented mechanisms: strong. Coverage of design-mandated behavior: the same holes as the implementation, so the suite cannot catch them.

---

## 5. Re-reading the ft09 live smoke with this lens

`decision_mix {PROBE:12, RESET:1}` — no COMMITMENT_STEP/ACTUATOR_LLM/FALLBACK will ever appear with current wiring. `rung {ANCHORED:16}, RGR 0.0` — the ladder is frozen by S2 + the narrow ENGAGED proxy, not by the game. `llm_calls=1` with 0 tokens — the accounting is hardcoded zeros. `WER 0.188` — genuine gate rejections (good) over a deviating denominator. `legibility VALID` — vacuously (R9 stamp 0; empty render_capture; zero bindings). The smoke proved transport, storage, gating, and probe plumbing — real and valuable — and nothing about the thesis mechanisms.

---

## 6. What it takes to make the build serve the design (priority order)

1. **B4 pre-registration (unlocks the ladder):** at emit time, compile applicable rule/step predictions (`compile_rule_test`) and write them into the ConsequenceRecord; Executive computes `match`; call `recompute_rule_status` + `fission_check` + `divergence_context_class` per beat; arm T1 from real mismatches. Everything needed already exists except the prediction compiler and ~20 lines in `_emit`.
2. **B1 query walk + commitment execution (unlocks A):** evaluate → `compute_rank` walk → means analysis over TESTED rules (stamp `relevance_edges`) → `compile_navigate`/`write_commitment` (add `step_premise` + `predicted_delta` at compile) → execute with consume-on-success, lease decrement, premise auto-block, `SUBSTITUTION_CAUGHT`, real source stamps; Actuator LLM hop behind `validate_actuator` for ACTION6 realization. All validators/functions exist; the loop integration is the work.
3. **Make J real (unlocks the factorial):** render actual grid content (or annotated crops) in Z5 with true colors; bind referents to goals live (means analysis + Surveyor goals + LEARN-* target stamping); make `_active_chain` walk to the live leaf; implement R2 substitution over prose fields.
4. **Real shadow compile:** in A-off cells run step 2's compiler, stamp its step id, never render — then GDS-bind/abandon/GA/ICR/DTL become computable from existing Log columns (add them to probe_arg_metrics; fix RGR/WER definitions; stamp real render_tokens and dspy token counts).
5. **ZCR loop:** call `salt_canaries` at K_CANARY cadence, write `zcr_echo`, compute per-zone rates + floors in health/legibility, add the missing-canary reject class, wire the R6 zone-differential trigger.
6. **Lifecycle hygiene:** re-anchor on AUTO_BIND (new locator version per §2.2's versioning), exclusive assignment, level-boundary demote+reset pass on T5, budget decrement → NEVER_VALIDATED, TTL expiry sweep, unify context classes (one base class; divergence minting per (action, class) — also fixes LEARN-ACTIONS unsatisfiability), resolve `evidence_ptr` against the store in the revision gate, write REVISION rows and persist Surveyor relations, honest A4/A8/A10 seams (implement or delete from config).

Items 1–3 are the thesis-critical core; they are roughly the size of what M5+M6 actually shipped (~600–800 lines + tests), and they convert almost every currently-dormant tested function into live machinery.

---

## Bottom line

- **Implements the design?** The write-integrity substrate, schema, gates, identity scoring, renderer contract skeleton, seeds, adapter, and observability plumbing: yes, faithfully, with real SQL-level enforcement. The doing loop, the agenda, pre-registered prediction matching, the live join, ZCR, the status machine beyond ACCEPTED/REOPENED, and the §8 measurement layer: no — built-but-unwired at best, absent at worst.
- **Tests the correct parameters and limitations?** 10 of 17 pinned constants are consumed and asserted correctly; 5 are read nowhere; gate 6 and the lease/TTL/ZCR family are untested because unimplemented. The suites are rigorous about the substrate and structurally blind to the wiring gaps.
- **Serves the purpose?** Not yet. The purpose is a pre-registered factorial over two live mechanisms; today neither mechanism affects a single emitted action. The foundation is genuinely strong and most of the remaining work has its functions, schema, and offline tests already in place — but P0–P4/X1/X2 are not runnable on this build, and no result produced by it should be attributed to J or A.

---

# Post-review wire-up (2026-07-17, commits d80c36a…a5aace9)

Every blocker and major gap in this review was subsequently implemented, in six commits, each with tests asserting the design-mandated behavior the original suite was blind to. 19 suites (~230 assertions) green; Sensi goldens byte-identical.

| Review finding | Commit | Now true in live play (test-asserted) |
|---|---|---|
| S2 no pre-registered predictions | **C1** d80c36a | closed rule ctx/effect vocabulary (4 reject classes); predictions committed pre-emission; a rule reaches TESTED **in play**; a referent climbs to **CHARACTERIZED off a pre-committed prediction** (the buildplan M5 live criterion); Observer quiets mechanically (1 call across 8 changed beats); **T1 fires from a real contradiction**; context regimes make LEARN-ACTIONS satisfiable and it **fires in play** |
| S1 the agenda never acts | **C2** 5a02098 | B1 walk → means analysis → compile with **premise closure + predictions** → execute with consume-on-success, lease, premise auto-block, SUBSTITUTION_CAUGHT (ring-hole case: caught, receipt suppressed, no consume); Actuator behind R8 with retry→verbatim-centroid FALLBACK; goals walk PROPOSED→EXPLORED→VALIDATED→ACCEPTED; experiments persisted + probe-preferred; **perceive_bind fixed** (candidate prefilter by anchor-overlap-or-signature + per-beat exclusivity — the single-candidate margin artifact that bound a ring to the background is gone) |
| S3 the join vacuous; organs blind | **C3** f540c97 | Z5 renders the **actual grid** (hex rows) + true machine-derived colors; R6 gains the coordinate-only fallback tier; **R2 substitution** implemented and applied in Z1/Z3/Z6; chain walks to the live leaf; bindings written by compilation (both join sides carry real content) |
| S4 shadow placeholder / S7 metrics ~4-of-17 | **C4** ab833cf | real per-beat shadow compile via the same `_select_means` as FULL (never persisted/rendered/executed); §8 table: ICR GA GDS-bind GDS-abandon DRIFT DTL FBR FCR FSN APR SCL SRR ECR DPR, per-organ WER (§2.1 definition), **RGR = CHARACTERIZED share among goal-bound**; real dspy token accounting + per-call render_tokens (R9 no longer vacuous); TESTED made sticky-until-K-mismatches (θ governs promotion only) |
| S5 ZCR unwired | **C5** 2e7042c | salt at cadence per organ-consumed zones; zcr_echo persisted; MISSING_CANARY metered; uniform failure → run INVALID; zone-differential → "consumption rot"; render_capture live. The loop's first test run caught its own over-salting bug, and the live smoke went **9/9 echoes with real Sonnet output** |
| S6 gate trusts the LLM / S8 anchors stale / S9 lifecycle absent / S10 fake seams | **C6** 79239c2 | `resolve_evidence` resolves pointers **against the store** (claims carry no weight); accepted aborts write REVISION + ABORT the step; re-anchor-on-bind as new versions; T5 boundary pass (TESTED→HYPOTHESIS with prior_support, instances DORMANT, steps abort); budget exhaustion → NEVER_VALIDATED (anti-oscillation now guards a real set); TTL re-probe sweep; relations persist; A4/A10/STRESS seams real; ARG_SPLIT relabeled RESERVED |
| Live verification | smoke-2 (ft09, 30 actions, real server) | 31 round-trips; 65 referents; **30 ENGAGED via null-effect receipts** ("nothing changed" is evidence — grounding_rate_all 0.46 vs 0.0 pre-fix); Surveyor 3 real calls / 20k tokens / 14 ops admitted incl. 9 experiments + 5 gate-rejected (2 with the new reject classes); ZCR 9/9; T3 comp-fail epochs on rate; R9 real (2382 ≤ 6000); scorecard captured; legibility VALID on **non-vacuous** checks. One fix surfaced and applied: the Surveyor's view now carries the frame's real available_actions (a5aace9) |

**Remaining known narrowings (documented, not hidden):** GA uses the union-of-bindings closure; DPR is the Actuator-retry approximation; live context classes = the current regime per level; the Observer's log_tail is the current beat's delta rather than an L-turn Log window; ACTION6-target frontier pairs prune only for ACTION6; Procedures (§5.4) and the P3 TextSpan instantiation remain future work. The J×A factorial, baselines, and the full §8 campaign are now *runnable* — that is the next phase, not more wiring.
