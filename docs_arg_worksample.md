# The LLM Proposes, the Executive Disposes: A Work Sample from the ARG Research Program

**Author:** Mohsen Arjmandi
**Affiliation:** Independent researcher
**Date:** July 2026

*ARG (Aligned Referent Grounding) is an agent architecture in which a language model's output never becomes belief directly: every claim enters a deterministic Executive as a typed proposal, and is admitted only by earning it — a perceived object or rule climbs grounding tiers solely when a pre-registered prediction about its consequences is matched against observation by code. This document is a work sample for technical review: the design reasoning, the implementation discipline, the experimental method, and the results exactly as they stand — including the efficacy number that is still zero. Every figure below is computed from append-only run logs and is replayable.*

---

## 1. The problem

Long-horizon LLM agents fail in ways the literature now documents separately. Goal drift — agents deviating from their own objectives as interaction unfolds — is an established, measured phenomenon ([arXiv 2505.02709](https://arxiv.org/abs/2505.02709), [arXiv 2603.03258](https://arxiv.org/abs/2603.03258)). Model-asserted beliefs enter agent state unverified and compound; Floridi and colleagues argue that LLMs circumvent rather than solve symbol grounding ([arXiv 2512.09117](https://arxiv.org/abs/2512.09117)). And agent behavior across thousands of steps is unauditable, because the state behind each action was never externalized. The cost is concrete on ARC-AGI-3 ([arXiv 2603.24621](https://arxiv.org/abs/2603.24621)), a benchmark of novel interactive games entered with zero prior knowledge: frontier systems scored below 1% at launch, and early entrants report exploration and belief maintenance, not puzzle-solving, as the bottleneck (e.g., [arXiv 2605.25931](https://arxiv.org/abs/2605.25931)).

Two existence proofs from our predecessor system's controlled experiments fixed the design target; both are single-variable results. First, binding failure: a prose fact ("plate at (20,31)") and the matching render content (a 3-cell component at (21,31)) never joined across ~2,300 actions and 13 runs of a frozen mid-tier model — until one mechanical coordinate join was added, which flipped first-level completions from 0 across 200-action runs to 3/3, on an otherwise identical stack. Second, commitment failure: a mid-tier run wrote the winning move verbatim at turns 150 and 184, wrote its own unstick prescription at turn 60, and executed none of them across 171 consecutive turns. The intention was present, recent, and salient; what was missing was an external commitment store executed by code. Prompt rhetoric ("pay attention to X") restored neither capability. The design conclusion: externalize both mechanisms, separately, and measure them separately.

## 2. The design stance

ARG rests on three commitments.

**The LLM proposes, the Executive disposes.** No LLM output ever mutates the store, and no LLM ever reads a raw dump. Every write is a typed proposal in a closed vocabulary, schema-validated on ingest; every state transition — grounding promotion, goal status, plan revision, eviction — is executed by deterministic code against invariants the model cannot forge; every read is a mechanically rendered view under a fixed serialization contract. The propose/verify pattern has published neighbors (LLM-Modulo planning, "Symbolic Governor," "Blueprint First, Model Second"), but none makes the deterministic side the owner of *belief*.

**Belief is earned, not asserted.** A referent climbs four tiers, every transition machine-verified: MENTIONED (a thing named only in LLM text is not a referent — it cannot be a plan target or a goal binding), ANCHORED (a deterministic extraction from raw observation; enumeration is salience-blind, so a 3-cell plate and a 40-cell wall get identical records), ENGAGED (at least one logged action receipt — a null effect counts as evidence), and CHARACTERIZED (referenced by a TESTED rule). A rule is TESTED when predictions committed to the log *before* acting were matched against the deterministic observation diff by the Executive, with mismatches below threshold — the model cannot author a match it did not pre-commit to. Demotion never deletes; the audit chain survives. The grounding claim is scoped honestly: causal-informational grounding relative to a formal micro-world, an implementation of Floridi's own sanctioned route of curation, verification, and tooling. Nothing stronger is claimed.

**Ignorance is typed, and the curriculum is generated from it.** A deterministic recognizer computes, per goal and per beat, whether enough verified sub-structure exists to act: `chain_status ∈ {COMPILABLE, REDUCIBLE, DEFICIT(holes)}`. Compilable goals reduce to single actions. Holes that name their own fill are auto-filled by the Executive with zero LLM calls; non-derivable holes are stamped as typed knowledge DEFICITs — machine-stated questions the LLM slot-fills through admission gates. An empty store is total DEFICIT, and that *is* the explore state: the curriculum is generated from zero knowledge rather than seeded. A working hypothesis follows: small models may suffice here, because their job reduces to filling slots in machine-stated questions rather than open-ended invention.

## 3. Mechanics

```
                 typed proposals (closed vocabularies, admission gates)
  LLM organs   ──────────────────────────────────────────────────────►
   Observer                                                   Executive
   Surveyor    ◄──────────────────────────────────────────────  (deterministic: diff,
   Actuator      rendered views (fixed zones Z1–Z6, ceiling B)   match, gate, compile,
                                                                 recognize, render)
                                                                      │
                                                        append-only stores + Log
                                                        (referents, rules, goals,
                                                         receipts — replayable)
                                                                      │
                                                        environment adapter
                                                        (the only game-specific code)
```

Three LLM role contracts surround one store. The **Observer** interprets machine-computed change sets over pre-anchored components; its output is a closed algebra of typed deltas (bind verdicts on Executive-proposed candidates, event notes, rule and relation hypotheses). It cannot invent an anchor. The **Surveyor** reads a budget-capped view and files gated proposals: goals whose achievement tests live in a closed predicate grammar, hypotheses with test plans, and experiments carrying pre-registered predictions plus a field naming which rival rules the probe discriminates between. The **Actuator** executes; on the modal beat a live plan step runs at code speed with zero LLM calls. The **Executive** — differ, matcher, validator, compiler, renderer, test evaluator — owns every transition. All stores are append-only SQLite; status is computed, never overwritten; every consequence receipt keys to the exact per-frame anchor it was observed under, so identity assignments are replayable data, never destructive merges.

Two structural details carry unusual load. First, the renderer is a fixed positional contract: goal–referent joins are pre-computed and co-located at fixed zones, so no consumer ever joins facts across distant prompt regions; outputs must cite referent ids or are rejected; emitted parameters are containment-checked against the cited anchor before emission; no call exceeds the hard render ceiling. Second, the goal chain carries proof obligations: a proposal may *claim* it fills a hole, but the edge counts only when the Executive proves the child's achievement test advances the parent — admitted goals cannot fake chain completeness. Milestones are tests over Executive-stamped records only ("deliberately test rule RU5" := k matched pre-registered receipts exist), so achievement is a fired predicate on logged events, never a model's declaration.

## 4. The methodology is the differentiator

**The system gates its own runs.** A run is INVALID for attribution if any per-organ write-error-rate floor is breached (WER ≤ 0.25, computed from typed rejection rows), if any rendered view exceeds the token ceiling, or if canary echo rates fall below floor. Canaries are quarantined synthetic rows salted into every zone of the rendered view; per-zone echo rates separate transport defects from consumption rot before any belief-level diagnosis is permitted. This is not decorative: four of the first batch's eight architecture runs were invalidated by the system's own floors, and each invalidation localized a real contract defect.

**Everything claim-bearing is pre-registered.** Predictions P0–P4 and two cross-transfer predictions each carry a written falsified-if clause, including the headline: P0 states that a ~0-wins result is a structural defeater of the entire contribution, not a caveat. A pre-committed downgrade clause reframes the thesis automatically if the transfer predictions are null. A compute-parity rule pins comparator protocols and prints ρ_calls and ρ_tokens beside every headline number; any advantage carried at ρ > 1 must survive a compute-matched comparator. Shadow-agenda instrumentation compiles plans in agenda-off cells without rendering or executing them — a byte-identity test proves the instrument cannot leak into behavior — so drift metrics are defined in every factorial cell.

**The loop is fast and pinned.** Roughly 25 offline test suites plus byte-level golden renders run green before any live run; campaigns proceed in same-day observe→improve waves; every live-caught defect is pinned by a test the same day; and because metrics are computed from the Log, instrument defects are repaired by recomputation, not re-running. A release gate applies the same discipline to language: any mental-state term in an external claim must be bound to a mechanical, log-computed definition in a closed glossary — one unglossed term fails release exactly as one task-isomorphic exemplar does. The design document itself was produced adversarially: three independently drafted designs merged, then iterated against a 27-attack review ledger to zero must-change verdicts.

## 5. Results to date

The honest headline first: across the live campaign to date — 52 runs, ~17M tokens, two protocol days — there are **zero level completions and zero score in every run, including every baseline cell**. The efficacy prediction (P0) is open. What the campaign has validated are mechanism results, each earned under the gates above.

| # | Finding | Status | Evidence (VALID runs only; all replayable) |
|---|---|---|---|
| 1 | Task efficacy (P0) | **Open — 0 completions** | 52 runs, ~17M tokens; 0 levels / 0 score in all cells, baselines included |
| 2 | Commitment-drift channel (P2, agenda half) | Confirmed at protocol seed count | killing the agenda flips GDS-abandon 0.00 → 1.00 (up to 394 reference beats/run); GDS-bind flat at 0.00 both sides; 3 seeds/cell, all cells VALID |
| 3 | Binding-drift channel (P2, join half) | Structurally absorbed | join-off ≡ full system on every per-beat metric in the paired engaged comparison (bind 0.00 = 0.00, goal adherence 0.964 = 0.964); residue is upstream — the double-kill cell formed zero effect hypotheses (0/4 seeds) |
| 4 | Substrate generality | Engaged 3/3 unseen games | generated curricula, effect hypotheses, milestones, deficit stamps on three never-seen games; zero game-specific code |
| 5 | Small-model floor | Crossed | Haiku 4.5 ran the complete loop VALID at write-error rate 0.0, engaged (2 hypotheses → 2 milestones → 48 aimed experiment beats); contract lever: WER 0.55–0.71 → 0.333 → 0.0 |
| 6 | Zero-seed curriculum | Demonstrated | with no seeded goals, runs generated the canonical learn-shaped chain, verbatim: "Discover an action that produces a level-completion event," "…a score-increasing event" |
| 7 | Cold-start honesty | Pinned and observed | an empty store reports total DEFICIT with empty-evidence holes on every generative run |
| 8 | Instrument integrity | 8 live-only defects | each caught by the system's own gates, fixed same-day, pinned by a test |
| 9 | Compute economy | ρ < 1 | full system vs bare baseline: ρ_calls 0.15, ρ_tokens 0.38 — no result can be attributed to extra inference spend |

Three of these deserve a sentence. The dissociation (row 2) is the central measurement working as designed: one switch moves exactly one drift component against real denominators. The absorption result (row 3) is the kind of finding only instrumentation surfaces — the LLM-facing join we expected to be load-bearing per-beat proved redundant *because* aiming, containment, and receipt attribution are code-owned; its contribution appears one layer earlier, as hypothesis feedstock. Row 8 is the culture: a containment mis-attribution (96 receipts credited to an enclosing board rather than the aimed component) was found by decomposing a suspicious factorial readout, fixed, and pinned by a nested fixture the same day.

## 6. Open problems, stated as the next experiments

The system now behaves as a disciplined experimentalist that has not yet found the mechanic that scores: it recognizes its deficits, invites targeted hypotheses, proves fills, runs bounded experiments with pre-registered predictions, demotes wrong theories with receipts, and re-opens its chain honestly — testing roughly three wrong object-scoped theories per 400-action run. The open problem is hypothesis quality and ordering, not machinery: which referent to test first. A receipt-density ranking lever is pre-registered but not yet run. Beyond P0, the named risks are the design's own §9 ledger: closed vocabularies may not span some environments ("seen but untypeable" is a narrower door, not a solved problem); record-quantified milestones can Goodhart; consistent-but-wrong theories pass receipts when probes lack discriminating power; and small-model Surveyor quality is the unhedged variable. Run variance on identical configurations (37/45/184 actions) means no single-run readout — good or bad — is treated as meaning anything; the protocol is the only lens.

## 7. What this work demonstrates

- **Thesis construction:** a falsifiable decomposition (drift = binding + abandonment) with pre-registered kill conditions, a downgrade clause, and existence proofs per component — not an architecture pitch.
- **Architecture for auditability:** a deterministic control plane owning all state; typed closed-vocabulary contracts at every LLM boundary; append-only stores where status is computed; full replayability of every number.
- **Instrumentation-first engineering:** the system invalidates its own runs; canary-based consumption measurement; per-organ error floors; parity accounting that forecloses the compute confound before a reviewer asks.
- **Experimental operations:** 52 gated runs in a two-day campaign window; same-day fix→pin→re-run cadence; recompute-not-re-run repairs; ~25 hermetic offline suites and golden renders ahead of every live wave.
- **LLM-contract craft:** measured contract levers (worked examples moved a small backbone's write-error rate from 0.55–0.71 to 0.0); adapter-integrity canaries motivated by real silent-failure incidents; render layouts designed against measured positional bias.
- **Reporting discipline:** mechanism results separated from efficacy results; efficiency claims conditioned on task success (a 0-completion cell prints "0 completions" and no efficiency number, ever); an enforced operational glossary in place of mental-state language.

The strongest thing this sample can show a technical reviewer is the shape of the zero: it is measured, gated, decomposed, and pre-registered as the next experiment — which is what it looks like when an instrument is finished and the discovery is in progress.
