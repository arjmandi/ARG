# Dissociating commitment drift from binding drift in long-horizon LLM agents

**Mohsen Arjmandi** · Independent researcher · July 2026
*Preprint — working draft. Every figure is computed from append-only run logs by the read-only instruments in this repository and is replayable; see §9.*

---

## Abstract

Long-horizon LLM agents deviate from their own goals as interaction unfolds. This "goal drift" is usually treated as one phenomenon and attacked with one class of fix (prompt rhetoric, better memory, longer context). We argue it is at least two phenomena, and we causally isolate one of them. In a deterministic agent architecture where a language model may only file typed proposals and a code "Executive" owns all belief, goal persistence and referent binding are two independent, environment-gated switches. Running the 2×2 ablation over them with per-beat reference plans compiled by a render-invisible shadow instrument, we find a clean **single-variable dissociation**: ablating the commitment mechanism flips goal-abandonment from 0.00 to 1.00 (up to 394 reference beats/run, 3 seeds/cell, all runs passing the system's own validity gate) while binding error stays flat at 0.00 on both sides. The binding channel, by contrast, does **not** re-appear as per-beat drift when its LLM-facing repair is ablated — because aiming, containment, and receipt attribution are code-owned, the binding failure class is *structurally absorbed*, and its only measurable residue is one layer upstream, as a collapse in hypothesis formation (0/4 seeds when both mechanisms are removed). We report these as mechanism results under full disclosure that task efficacy is null: across 52 gated runs and ~17M tokens on ARC-AGI-3 interactive games, there are zero level completions in every cell, including every baseline — a result pre-registered as a structural defeater of the efficacy claim, not a caveat. The contribution is the decomposition and the instrument that measures it: commitment drift is a live, isolable failure channel repaired by state persistence, dissociable from binding drift, and measurable in every ablation cell.

---

## 1. Introduction

An agent that plans over hundreds or thousands of steps tends to wander off its own objective. The phenomenon — **goal drift** — is now measured and benchmarked as a first-class failure of LLM agents [1, 2]. The default responses treat it as a single defect of a single component (the model's attention or memory) and reach for a single lever: tell the model to "stay focused," give it a scratchpad, extend the context window. Those levers under-perform, and the reason, we argue, is that "drift" names at least two mechanically distinct failures that happen to co-occur:

- **Binding drift** — the intention and the objects it refers to are *both present* in context, but the join between "the goal" and "the object the goal is about" lives only in transformer attention, which loses bindings under distance and low salience (the positional / spaced-evidence regime studied by long-context reference benchmarks such as LongPiBench [3] and the lost-in-the-middle effect [4]). The fix is *positional*: re-surface the join, pre-computed, at a privileged position.
- **Commitment drift** — the intention is simply *absent* from later contexts, and error compounds through local mistakes and sparse feedback, *even when every context is short and the goal maximally salient* (the compounding-error / objective-drift regime measured by the goal-drift benchmark line [1, 2]). The fix is *not* positional: it is an external commitment store that a deterministic executor consults, independent of what the model happens to attend to.

These have different signatures and different repairs, and the binding component is not merely hypothesized. The predecessor system to this work, **Sensi** [5], diagnosed a *self-consistent hallucination cascade*: errors in its perception layer (frame differencing) propagate through the hypothesis pipeline into internally coherent but factually wrong world models. What [5] names a perception-layer hallucination cascade is, in the present taxonomy, **binding loss** — a referent grounded in the model's own prior text rather than in observation. Its counterpart, **commitment loss**, is the goal-abandonment failure the agent literature measures [1, 2]: an intention lost from later contexts even when it is short, recent, and maximally salient — a failure of state persistence, not of attention. ARG externalizes a repair for each as an independent switch — a goal↔referent join (**J**) and an external commitment store (**A**) — so the two can be turned off, and measured, separately; whether they are in fact separable is what §5 tests.

This paper asks the follow-on question directly: **if we externalize both repairs into code, as two independent switches, do the two drift components dissociate?** We report:

1. **A clean commitment-drift dissociation (§5.1).** Ablating the commitment store flips goal-abandonment 0.00 → 1.00 while binding error stays flat at 0.00 — a single-variable causal isolation, measured against real per-beat reference plans, at protocol seed count, every run gated VALID.
2. **Binding drift is structurally absorbed (§5.2).** Ablating the LLM-facing binding repair changes *nothing* per-beat, because binding is code-owned; the failure class the repair guarded cannot open, and its residue appears upstream (§5.3) as hypothesis-formation collapse.
3. **The efficacy null (§5.4).** No cell completes a level. We pre-registered this as a defeater and report it first, not last.
4. **Two secondary results:** a small model runs the full loop cleanly (§5.5), and the machinery engages on unseen games with zero game-specific code (§5.6).

We are explicit about what this is and is not. It is **not** a completed double dissociation — the binding half does not print as per-beat drift, so we cannot show "kill the join ⇒ binding error rises." It *is* stronger evidence for the **decomposition** (drift is not one thing) than for a **unification** (one structure repairing both), and we report it as such (§6). The methodological claim — that both drift components can be *defined and measured in every ablation cell*, including the cells where a mechanism is absent — is, to our knowledge, new, and is what lets the dissociation be stated at all.

## 2. Two failure modes, made measurable

We instantiate the two components as two metrics, both defined per beat and in every factorial cell.

- **GDS-bind** (binding-drift score): on a beat that executes an *aimed* action, the fraction where the emitted target referent differs from the reference plan's target — the aim landed on the wrong object or on background. This is the join seam: it exists only where an action carries an aim parameter.
- **GDS-abandon** (commitment-drift score): the fraction of reference beats where the beat did not follow the reference step at all — a different action, or a different deliberate target, or the step simply not taken. This is the persistence seam: it exists wherever a plan step exists, aimed or not.

Both are ratios over **reference beats** — beats for which a plan step is defined. The crucial move is that the reference plan is available *even in cells where the planning mechanism is ablated*, via a shadow instrument (§4). The pre-registered prediction was a **double dissociation**: killing the binding repair moves the grounding metrics and GDS-bind together while GDS-abandon stays flat; killing the commitment repair moves GDS-abandon (and the in-commitment ratio ICR) while the grounding metrics stay flat. §5 reports which half held and how the other half reframed.

## 3. The apparatus (only as much as the measurement needs)

The architecture exists here as an *instrument*, not as the contribution; we describe only what is load-bearing for trusting the numbers. Full spec: `docs_arg_design.md`.

**The LLM proposes, the Executive disposes.** No model output mutates state and no model reads a raw dump. Three LLM "organs" (an Observer that interprets machine-computed change-sets, a Surveyor that files goals/hypotheses/experiments, an Actuator that emits actions) may only submit typed proposals in closed vocabularies through admission gates. A deterministic **Executive** — differ, matcher, validator, compiler, renderer, test-evaluator — owns every state transition. All stores are append-only; status is *computed*, never overwritten; every consequence receipt keys to the exact per-frame anchor it was observed under, so identity is replayable data rather than a destructive merge.

**The two switches.** The binding repair **J** is the goal↔referent *join*: a persistent structure that canonicalizes referents from consequence-tested evidence and re-surfaces every active goal pre-joined with its referents at fixed prompt positions each turn, so no consumer ever joins facts across distant prompt regions. `ARG_JOIN=0` deletes exactly this join (the renderer falls back to un-joined prose) and nothing else. The commitment repair **A** is the external Commitment store executed by code: a compiled plan whose steps the Actuator consults independent of model attention. `ARG_AGENDA=0` deletes exactly this. The 2×2 factorial is `{J on/off} × {A on/off}` = FULL / J0 / A0 / J0A0, each a single environment flag; all other scaffolding (store, three organs, triggers, budgets) is identical across cells, so a cell-to-cell delta cannot be attributed to generic scaffolding or to call count.

**Nothing above the environment adapter knows what a game is.** A single small, declarative adapter maps raw observation → canonical state, exposes the action vocabulary as opaque symbols, and declares the verified signal channels; everything above it is substrate-general. This is what makes the "unseen game" claim (§5.6) meaningful and is enforced at release by an exemplar scrub (§9).

## 4. Instrumentation and why the numbers are trustworthy

**The shadow-agenda reference.** GDS is a deviation from a plan — but in agenda-off cells there is no plan to deviate from. The instrument closes this by *shadow-compiling* the plan the full system would have committed, in every cell, without rendering or executing it: a pure read over the same store, walking the chain-aware selection and computing the auto-fill tier virtually. A byte-identity test proves the shadow path cannot leak into behavior (the rendered bytes are identical with the shadow on or off). This yields `drift_ref_beats` > 0 — and therefore *defined* GDS-bind and GDS-abandon — in cells that have no live agenda at all. Without this, the A-off half of the dissociation would rest on an undefined metric; with it, both halves are measured against the same reference.

**Operational GDS taxonomy** (as implemented in `probe_arg_metrics.py`): for each reference beat with a plan step `(target, action)`, the beat is scored **bind** if it took the plan's action with an aim but landed on a referent ≠ the plan's target; **aligned** if it faithfully executed a live step; **abandon** if it neither followed the plan's action nor hit the plan's deliberate target. Untargeted actions have no aim parameter and so present no binding seam — they can abandon but cannot bind-miss, which is why GDS-bind is structurally near-zero wherever plans are untargeted (this matters in §5.2).

**Run validity.** A run is INVALID for attribution — excluded entirely — if any per-organ write-error rate exceeds 0.25 (typed rejection rows / total ops), if any rendered view exceeds the hard token ceiling (6000) per beat *or* per call, or if salted-canary echo rates per zone fall below floor. This is not decorative: four of the first eight architecture runs were invalidated by these floors, and each invalidation localized a real contract defect. Every number in §5 is from a VALID run.

**Compute parity.** The full system vs. the bare backbone runs at ρ_calls = 0.15 and ρ_tokens = 0.38 — it spends *less* inference, not more — so no reported effect can be attributed to extra inference spend. Efficiency figures are reported only for completed levels; a 0-completion cell prints "0 completions" and no efficiency number, ever.

## 5. Results

Campaign to date: **52 runs, ~17M tokens, two protocol days, on ARC-AGI-3 [6]**, Sonnet-class backbone unless noted, 200–400-action horizons. Every figure below is from a VALID run and replayable from the Log.

### 5.1 The commitment-drift dissociation (the headline)

At protocol seed count on ls20 (3 seeds per cell, every cell VALID):

| cell | binding repair J | commitment repair A | **GDS-bind** | **GDS-abandon** | reference beats/run |
|---|:---:|:---:|:---:|:---:|---|
| FULL   | on  | on  | 0.00 | 0.00 | up to 96 |
| J0     | off | on  | 0.00 | 0.00 | up to 72 |
| **A0** | on  | **off** | **0.00** | **1.00** | up to 394 |
| J0A0   | off | off | — | — | (undefined; see §5.3) |

**Killing the commitment store flips goal-abandonment 0.00 → 1.00 with binding error flat at 0.00, wherever the metric is defined** (GDS-abandon defined on n=2 of the 3 A0 seeds; the third drew no feedstock and is undefined, not zero). The effect is single-variable: FULL and J0 both hold abandonment at 0.00; only removing A moves it, and it moves to the ceiling. Against up to 394 shadow-compiled reference beats in a single A0 run, this is not a small-sample artifact of the beat count. This is the commitment-drift channel isolated: the system, deprived only of its external commitment store, abandons the very plan it would otherwise have followed on essentially every beat, while its binding behavior is unchanged.

### 5.2 Binding drift is structurally absorbed, not merely small

The binding half did not behave as the pre-registered double dissociation expected — and the reason is itself a result. GDS-bind is 0.00 in *every* cell above, including the cells where the join is killed (J0, J0A0). We confirmed this is absorption rather than an ls20 idiosyncrasy on **tn36**, a second, targeted-action-rich game, in a paired *engaged* comparison (both FULL and J0 forming and pursuing aimed hypotheses):

| metric (tn36, paired engaged) | FULL | J0 (join killed) |
|---|:---:|:---:|
| GDS-bind | 0.00 | 0.00 |
| GDS-abandon | 0.00 | 0.00 |
| grounding rate (RGR) | 1.00 | 1.00 |
| goal adherence (GA) | 0.964 | 0.964 |

**Killing the LLM-facing join changes nothing per-beat.** The binding-failure class the join was built to guard — the perception-layer grounding failure the predecessor system diagnosed (§1) — cannot open here, because aiming, containment checking, and receipt attribution are Executive-owned code, not attention: an aimed emission's landing is decided by geometry (which referent's anchor cells contain the emitted coordinates), and a wrong landing is caught and its receipt suppressed *before* it can corrupt belief. The join's contribution has moved from "prevent per-beat binding loss" to "structure," where it does not print as drift.

One integrity note that makes the 0.00 credible rather than suspicious: an early version of the containment code attributed a click to the *first* referent by id whose anchor contained it, which under nested components stamped the enclosing board instead of the aimed part — **96 receipts mis-attributed in a single run**, silently starving the aimed rule and *printing fake drift*. The instrument's own decomposition surfaced it; the fix (attribute the *most specific* containing referent) was pinned by a nested fixture the same day. The clean 0.00s post-fix are the corrected reading.

### 5.3 The residue is upstream: a feedstock gradient (emergent)

If the join's load is structural, where does removing it show up? Not per-beat, but one layer earlier, in whether effect-linked hypotheses form at all. Across the factorial, hypothesis-formation rate runs:

> FULL 3/3  =  J0 3/3  >  A0 2/3  >  **J0A0 0/4**

Removing both mechanisms **floors the system upstream of drift**: with neither the join nor the agenda context in the epoch view, effect-linked hypotheses essentially never form (0 of 4 seeds; ≈1% under a two-thirds per-seed base rate if the two removals were independent). This is why the J0A0 GDS cells are *undefined* in §5.1 — the system never gets far enough to have a plan to drift from. The binding repair's measurable effect, then, is on the **feedstock** for commitment, not on binding execution — a coupling one step removed from the one the double dissociation predicted.

### 5.4 Task efficacy is null (stated first among results, by design)

**Across all 52 runs and every cell — including every baseline — there are zero level completions and zero score.** The efficacy prediction (P0) was pre-registered with the clause that a ~0-wins endpoint *defeats the contribution rather than footnoting it*, and we hold to that: the efficacy claim is open, and this paper makes none. What the null does and does not mean:

- It does **not** invalidate §5.1–5.3. Those are mechanism measurements against internal reference plans, defined and gated independent of whether any level is won; they are the same numbers whether the game is solved or not.
- It **does** mean the system has not yet found the *mechanic that scores* on these games. The observed behavior is a disciplined experimentalist that recognizes its own knowledge deficits, files targeted hypotheses, runs bounded experiments with pre-registered predictions, demotes wrong theories with receipts, and re-opens its plan — testing roughly three wrong object-scoped theories per 400-action run. The open problem is hypothesis *quality and ordering*, not machinery.
- The baselines are also at zero. Frontier systems scored below 1% on ARC-AGI-3 at launch [6]; a later analysis [7] finds many *public* games in this family solvable by non-intelligent strategies — so we treat 0 completions on them as a genuine gap, not one excused by difficulty, and the efficacy null is stated on exactly those terms.

### 5.5 A small model runs the whole loop cleanly

A Haiku-class model ran the complete loop **VALID at write-error rate 0.0**, engaged throughout (2 effect-linked hypotheses → 2 milestones → 48 aimed experiment beats, zero rejected ops). This was a contract problem, not a model wall: a single lever — worked per-operation examples in the organ contract, config-gated so the larger model's contract stays byte-stable — moved the small backbone's Surveyor write-error rate from 0.55–0.71 → 0.333 → 0.0. The tier gap is real (the large model decomposes more richly: 9 milestones / 192 beats vs. 2 / 48) but the **floor is crossed** — small models can drive the loop when belief-ownership and verification are structural. This bears directly on the economic case for small agent models [8]: it is testable here precisely because the deficit mechanism reduces the model's job to slot-filling machine-stated questions in a closed grammar.

### 5.6 The machinery is substrate-general

The chain machinery **engaged on 3/3 never-before-seen games with zero game-specific code or tuning** — generated curricula, effect-linked hypotheses, milestones, and deficit stamps on all three; 2/3 passed the validity gate. With no seeded goals (`ARG_SEEDS=0`), runs generated the canonical learn-shaped curriculum verbatim from the deficit brief alone: *"Discover an action that produces a level-completion event," "…a score-increasing event."* One unseen game (tn36) is the targeted-action-rich profile the §5.2 J-half comparison needs; the third exposed an organ-specific stressor (an Actuator-realization floor breach on that game's geometry) that the per-organ error discipline localized as emission, not machinery.

## 6. Interpretation

The pre-registered hypothesis was a *unification*: one aligned-referent structure repairing binding-drift and commitment-drift together, falsified if the metrics dissociate. The metrics dissociated — so, read strictly, the unification is not what these runs support. What they support is the **decomposition and one clean causal isolation**:

1. **Commitment drift is a distinct, isolable failure channel** with a non-positional repair. Removing the external commitment store, and nothing else, takes goal-abandonment to the ceiling while binding is untouched. This is the result the title names, and it is robust (protocol seed count, hundreds of reference beats, every run gated).
2. **Binding drift, once externalized into code, stops being a per-beat phenomenon.** It is *absorbed* into structure rather than *repaired* at the seam, and its residue relocates upstream to hypothesis feedstock. This is a more interesting negative than "the join didn't matter": the join matters, but not where a per-beat drift metric can see it.

The headline is therefore asymmetric: **a demonstrated dissociation of commitment drift from binding drift**, with the commitment half causally isolated and the binding half shown to be structurally absorbed. For the field, the transferable claims are (a) that "goal drift" should be decomposed before it is repaired, because its components have different signatures and different fixes; and (b) that a commitment mechanism's contribution is measurable in isolation, at the ceiling, with the right shadow instrumentation — independent of whether the agent ever wins.

## 7. Related work

**Goal drift** is established and benchmarked [1, 2]; we add a component decomposition and a per-cell measurement rather than a new aggregate score. **Long-context reference and positional bias** (spaced multi-piece evidence, middle-position loss) motivate the binding-drift construct and its positional repair [3, 4]; our finding is that once the join is code-owned the positional failure does not manifest as drift. **Compounding-error / commitment loss** in long interactions motivates the commitment-drift construct [1, 2]; we isolate it. **Coreference caches** (LQCA-style mechanical joins; LINK-KG-style persistent canonical-referent caches) are prior art for the join's *plumbing*, and we concede the overlap openly — the delta is that ARG's referents climb grounding tiers only through Executive-verified consequence receipts, a substrate static-text caches lack. **Propose-and-verify** control (LLM-Modulo planning; "Symbolic Governor"; "Blueprint First, Model Second") shares the pattern of a deterministic checker, but there the verifier checks *outputs*; here the deterministic side owns *belief*. **Grounding** is claimed only in Floridi's causal-informational sense relative to a formal micro-world [9] (see §8); we implement his sanctioned route of curation/verification/tooling and claim nothing stronger. **Small agent models** [8]: we give a positive existence-point for the "structure over scale" position.

*(Citation note: every numeric reference was checked against live arXiv on 2026-07-31 — the id resolves, the title matches, and the source supports the in-text claim. [5], the author's predecessor paper, is cited only for the qualitative failure it diagnoses; no run figures are attributed to it. LQCA/LINK-KG coreference caches and the propose-verify systems are named in-text and cited in full in the design's reference ledger.)*

## 8. Limitations and scope

- **Efficacy is null (§5.4).** Every claim here is a mechanism claim; none is an efficacy claim. A reviewer who reads the dissociation as evidence the agent "works" is reading a claim we do not make.
- **Not a completed double dissociation.** The binding half is absorption, not printed drift; we cannot exhibit "kill J ⇒ GDS-bind rises." The result is a single clean isolation (commitment) plus a structural-absorption finding (binding), not two symmetric arms.
- **Breadth vs. depth.** The commitment dissociation is at protocol seed count but on one game (ls20); the binding-absorption confirmation is one paired game (tn36); machinery *generality* is 3 games but the full claim-bearing protocol (≥3 games × ≥3 seeds for the dissociation itself) is not complete. The J0A0 cell is undefined for GDS (§5.3), not zero.
- **Closed vocabularies may not span every environment**; "seen but untypeable" is a narrower door, not a solved problem. Record-quantified milestones can be gamed; consistent-but-wrong theories can pass receipts when probes lack discriminating power; small-model Surveyor quality is the unhedged variable.
- **Grounding scope.** "Grounding" throughout denotes causal-informational grounding relative to a formal micro-world whose world-model is the environment's transition function; perceptual and social grounding are explicitly not claimed. A release-time vocabulary lint (§9) binds every mental-state term to a mechanical definition or fails the release.
- **Run variance.** Identical configurations produced 37/45/184-action runs; no single-run readout, good or bad, is treated as meaningful — the protocol and the gate are the only lens.

## 9. Reproducibility

Everything is replayable from append-only SQLite stores; the instruments are read-only and recompute metrics from the Log (instrument defects are fixed by recomputation, not re-running).

```bash
uv sync
# a generative cold-start run (400 actions, Sonnet-class):
ARG_SEEDS=0 SENSI_MAX_ACTIONS=400 uv run python main.py --agent=arg --game=ls20
# the factorial cells are single flags:
#   J0 → ARG_JOIN=0    A0 → ARG_AGENDA=0    J0A0 → both    small model → ARG_MODEL=...
# gate first, then read the numbers (a run is INVALID for attribution if the gate trips):
uv run python probe_arg_legibility.py --db arg_state.db --probe arg_probe.db   # validity gate
uv run python probe_arg_metrics.py    --db arg_state.db --probe arg_probe.db   # GDS-bind/abandon, RGR, GA, ICR
# the §7 release gate (exemplar scrub + vocabulary lint) that guards external claims:
uv run python probe_arg_release.py
```

The GDS taxonomy, shadow reference, and validity gate cited in §4 are implemented in `probe_arg_metrics.py` / `probe_arg_legibility.py` and pinned by hermetic tests (`tests/test_arg_metrics.py`, `tests/test_arg_agenda.py`, byte-level golden renders). The measurement framework and pre-registered clauses are in `docs_arg_expected_outcomes.md`; the full results record with every run and verdict is in `docs_arg_campaign_ls20.md`.

## 10. Conclusion

"Goal drift" is not one failure. At least two mechanically distinct failures hide inside it — one repaired by re-surfacing bindings at a privileged position, one repaired by an external commitment store executed by code — and with the right per-cell instrumentation they come apart. We causally isolated the commitment channel: remove the store and nothing else, and the agent abandons its own plan on essentially every beat, while its binding stays clean. The binding channel, externalized into code, ceased to print as per-beat drift at all. We report this with task efficacy at zero, because the decomposition is the contribution and it holds regardless — an instrument that can say *which* drift is happening, in every cell, is the prerequisite for fixing either.

---

## References

Every entry was checked against live arXiv on 2026-07-31: the id resolves, the title matches, and — except where flagged — the abstract supports the claim made in-text.

[1] R. Arike, E. Donoway, H. Bartsch, M. Hobbhahn. *Evaluating Goal Drift in Language Model Agents.* arXiv:2505.02709.
[2] A. Menon et al. *Inherited Goal Drift: Contextual Pressure Can Undermine Agentic Goals.* arXiv:2603.03258.
[3] *Distance between Relevant Information Pieces Causes Bias in Long-Context LLMs* (LongPiBench). arXiv:2410.14641.
[4] N. F. Liu et al. *Lost in the Middle: How Language Models Use Long Contexts.* arXiv:2307.03172.
[5] M. Arjmandi. *Sensi: Learn One Thing at a Time — Curriculum-Based Test-Time Learning for LLM Game Agents.* arXiv:2603.17683. Cited (§1) for the *self-consistent hallucination cascade* it diagnoses (§6.4) — a perception-layer grounding failure the present taxonomy names binding loss. No numeric run figures are attributed to it.
[6] ARC Prize Foundation. *ARC-AGI-3: A New Challenge for Frontier Agentic Intelligence.* arXiv:2603.24621.
[7] Liew Keong Han. *Explore Before You Solve: The Speed–Depth Trade-off in Epistemic Agents for ARC-AGI-3.* arXiv:2605.25931.
[8] P. Belcak et al. (NVIDIA). *Small Language Models are the Future of Agentic AI.* arXiv:2506.02153.
[9] L. Floridi, Y. Jia, F. Tohmé. *A Categorical Analysis of Large Language Models and Why LLMs Circumvent the Symbol Grounding Problem.* arXiv:2512.09117.

*"HIPIF," which earlier stood in for the commitment class, did not resolve to any real paper and was removed. Coreference-cache prior art (LQCA, LINK-KG) and propose-verify control (LLM-Modulo, "Symbolic Governor," "Blueprint First, Model Second") are discussed in §7 and cited in full in the design document's reference ledger (`docs_arg_design.md`).*
