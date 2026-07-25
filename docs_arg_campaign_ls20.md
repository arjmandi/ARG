# ARG Campaign — ls20, batch 1 (2026-07-17)

*First execution of the §8 protocol: FULL ×5 seeds, factorial cells J0/A0/J0A0 ×1, bare comparator ×1 — ls20-9607627b, real ARC server, Sonnet-5-medium, 200-action horizon. Every run gated by `probe_arg_legibility` before reading a number. Raw stores: scratchpad/full{1..5}, j0s1, a0s1, j0a0s1, bare1.*

## The table (batch 1)

| cell | run | verdict | compl | TESTED rules | grounding_all | WER | obs WER | LLM calls | ktok |
|---|---|---|---|---|---|---|---|---|---|
| FULL | seed1 | **INVALID** (obs WER 0.777, pre-fix) | 0 | 21 | 0.871 | 0.602 | 0.777 | 34 | 195 |
| FULL | seed2 | VALID | 0 | 20 | 0.729 | 0.075 | 0.0 | 40 | 250 |
| FULL | seed3 | VALID | 0 | 9 | 0.871 | 0.125 | 0.0 | 22 | 128 |
| FULL | seed4 | **INVALID** (surv WER 0.273) | 0 | 7 | 0.790 | 0.256 | 0.0 | 16 | 90 |
| FULL | seed5 | VALID | 0 | 8 | 0.790 | 0.099 | 0.0 | 28 | 155 |
| J0 | seed1 | **INVALID** (surv WER 0.270) | 0 | 12 | 0.810 | 0.155 | 0.0 | 24 | 129 |
| A0 | seed1 | **INVALID** (surv WER 0.417) | 0 | 8 | 0.790 | 0.083 | 0.0 | 9 | 44 |
| J0A0 | seed1 | VALID | 0 | 14 | 0.879 | 0.113 | 0.0 | 23 | 138 |
| BARE | seed1 | (comparator) | 0 | — | — | — | — | 200 | 468 |

**Parity row (compute-parity rule, clause 2):** FULL(VALID mean) vs BARE — **ρ_calls = 0.15, ρ_tokens = 0.38**. Both ρ ≤ 1, so per the pre-registered rule the parity row itself is the rebuttal: no compute-matched arm is required; any future FULL advantage cannot be attributed to extra inference spend.

## What batch 1 establishes

1. **The validity gate works on real runs.** Seed1's Observer-contract mismatch (advertised BIND ops → 68 auto-rejects, WER 0.777) was caught, diagnosed from the reject table, fixed (550a878), and eliminated (obs WER 0.0 on every later run). Three runs then breached the SURVEYOR floor (0.27–0.42) — see §Next.
2. **The learning substrate performs live at mid-tier.** Across cells: 7–21 rules TESTED per run off pre-registered receipts (with demotions — FBR up to 9), grounding_rate_all 0.73–0.88, experiments the dominant probe driver (65 proposed / 62 executed on seed2), controllable earned, ZCR 1.0 everywhere, R9 max 2.7k/6k, LEARN-ACTIONS fired and REOPENED on a regime mint (the self-repairing false closure, live).
3. **Economy:** FULL averages ~28 calls / ~178k tokens per 200 actions vs BARE's 200 calls / 468k — the modal-beat-zero-calls claim holds on a real game.
4. **No completions in any cell (including BARE).** P0 remains open; no cell differentiates on the conditioning variable yet. Consistent with ls20's history (multi-step mechanic; raw approaches never won). The J/A dissociation is therefore not yet measurable here: no run compiled a commitment (the walk's leaf stayed on LEARN goals whose tests carry no effect keys; no learned rule yet carries a score/level effect — those signals only fire at level completion on ls20). Shadow steps correctly did not stamp either (the shadow compiles exactly as FULL would — and FULL would not).

## Diagnosis → next levers (research, in priority order)

1. **Surveyor goal quality (write-path):** the remaining INVALIDs are surv-WER breaches from incompilable/duplicate PROPOSE_GOALs — the §9.2 trade priced honestly. Contract fix applied post-batch (the closed AST grammar is now TAUGHT in the SurveyorProposals docstring with an example, as the rule format already was): expect gate-2 rejections to drop on the next seeds. The 0.25 floor at small op counts is also a sensitivity-sweep observation (pre-registered tunable).
2. **Rank precedence trap:** a REOPENED LEARN-ACTIONS outranks everything, returning the walk to a leaf with no compilable effect keys. Candidate design question (not a unilateral change): should record-quantified LEARN goals rank behind effect-keyed goals once each regime's coverage is in progress?
3. **Bridging to score-linked rules:** completions need a rule whose effect carries score/level — i.e., the Surveyor must chain intermediate discoveries (charge/hatch mechanics) into admissible sub-goals. This is exactly the §9.2/§9.4 hard case the design names.
4. Longer horizons / more seeds; then J0/A0 re-runs to fill the factorial with VALID cells.

## Cost of batch 1
9 runs, ~1.65M tokens total (≈196k avg per ARG run; 468k for BARE), ~8–10 min per lane, all scorecards on the ARC server.

---

## Batches 2–3 (same day): contract fixes verified, the bootstrap gap isolated

**Batch 2** (J0 s2, A0 s2, FULL-400 s6) after teaching the AST grammar in the Surveyor contract: GATE2 incompilable-goal rejections **eliminated**; the first Surveyor goals were **ADMITTED** (4/1/2 per run) and the first **score/level-linked rules** appeared. J0 s2 and A0 s2 both VALID (factorial cells refilled). full6 went INVALID on duplicate re-proposals (12) — root-caused to a §4.2 narrowing: the BudgetedView never showed the Surveyor the existing goal tree. Fixed (cc4e6fb): the view now lists live goals + folded terminal counts, and the §4.3 walk visits ALL unachieved goals by rank instead of locking on a REOPENED LEARN leaf.

**Batch 3** (FULL s7, s8, s9-400) with both fixes: **3/3 VALID** (surv WER 0.042/0.231/0.049; duplicates 3/23/2). Six VALID FULL runs total. Consistent profile: TESTED rules 4–20, grounding 0.79–0.89, Observer strongly quieting (s9: 10 calls across 400 actions — 62k tokens), goals admitted every run.

| cell (VALID only) | n | completions | TESTED rules | grounding_all | calls | ktok |
|---|---|---|---|---|---|---|
| FULL (s2,3,5,7,8) | 5 | 0 | 8–20 (μ≈11.8) | 0.73–0.89 | 22–40 | 128–250 |
| FULL-400 (s9) | 1 | 0 | 4 | 0.80 | 10 | 62 |
| J0 (s2) | 1 | 0 | 15 | 0.79 | 23 | 119 |
| A0 (s2) | 1 | 0 | 5 | 0.79 | 6 | 29 |
| J0A0 (s1) | 1 | 0 | 14 | 0.88 | 23 | 138 |
| BARE (s1) | 1 | 0 | — | — | 200 | 468 |

**The isolated bootstrap gap (the §9.2/§9.4 case, now with receipts):** score-linked rules form (s9 holds four) but stay HYPOTHESIS — their predictions can only match on a scoring beat, and ls20's score requires a multi-step mechanic (navigate the mover, then interact) that no single-action rule can capture. Meanwhile intermediate spatial subgoals ("mover reaches R#") are INEXPRESSIBLE in the closed test grammar (channels: score/levels/state/lives; the record-quantified ops exist but `where`-clauses are not evaluated). So means analysis correctly refuses to compile, probing continues, and completions stay at 0 in every cell including BARE. This is the design's own admitted trade surfacing exactly where predicted — "the central machinery idles during the hardest phase."

**Decision now owned by the design, not the harness** (three candidate routes, all pre-registerable):
1. **Record-quantified intermediate tests:** evaluate `where` clauses on EXISTS/COUNT (e.g., "≥1 consequence with target=R# and action=ACTION_move") — stays within grounded records; smallest change; makes navigate-adjacent subgoals admissible.
2. **NAVIGATE-first exploitation:** let the walk compile toward a HYPOTHESIS score-rule as an EXPERIMENT commitment (bounded lease) rather than requiring TESTED first — the design's Experiments already carry pre-registered predictions; this extends them to multi-step plans.
3. **Signal-vocabulary extension per adapter:** the adapter could declare a verified derived channel (e.g., mover-position stability) — heavier, touches the generality contract.

Batch totals: 15 runs, ~2.5M tokens. All stores under scratchpad; every number gated.

---

## Batch 4 (2026-07-17): the goal-chain engine live — generative curriculum, milestones, and three walk-economics fixes

**What shipped between batches 3 and 4 (G1–G3):** routes 1+2 above, unified and completed per docs_arg_goal_chaining_proposal.md — the `chain_status` sufficiency recognizer (COMPILABLE/REDUCIBLE/DEFICIT with typed holes + derivable evidence), verified-fill `goal_edge`s (knowledge/signal fill proofs; an LLM cannot assert chain progress), the knowledge-milestone grammar (A1), deterministic auto-fill of derivable holes (A2, provenance DEFICIT), milestone experiment-commitments toward HYPOTHESIS rules, DEFICIT stamps + the epoch view's DEFICIT block + `fills_hole` ingest, the tool seam (zero ACTION6 literals above the adapter), and the generative-curriculum configuration (`ARG_SEEDS=0`). 25 offline suites + goldens green before any live run.

**Design:** FULL-gen (`ARG_SEEDS=0`) ×3 seeds ×400 actions on ls20, Sonnet-5-medium, plus one small-backbone lane (Haiku 4.5) — against three pre-registered falsified-ifs (outcomes doc §PC).

### The waves (observe→improve, same-day cadence as batches 2–3)

| wave | runs | build | verdicts | what the instruments caught |
|---|---|---|---|---|
| 4a | gen1–3 + hk1 | G3 as first shipped | 3× INVALID (surv WER .28/.48/.38); hk1 broken | (1) hk1: Haiku rejects adaptive thinking — every organ call 400'd; a config failure, NOT a small-model readout. (2) Surveyor WER breaches: bindings citing non-roster ids (12×GATE1) + restated intents for re-opened holes (5×GATE4). (3) gen3: auto-filled milestones inherited 400-action budgets → 379/400 beats of experiment-commitments toward wrong hypotheses → grounding starved (0.24 vs batch-3 ~0.8); the §3 budget-exhaustion clause never fired |
| 4b | gen4–6 + hkb | + Haiku thinking fix, + contract (roster-closure, per-hole dedup) | gen6 VALID (WER .038); gen4 INVALID (.58), gen5 INVALID (.40) | (4) gen4: a Surveyor-proposed RULE_STATUS milestone dodged the budget clamp (provenance-scoped, not shape-scoped) and compiled 336 blind commitments — its target-scoped rule was reached via an untargeted action with no route, so its receipt could never land. (5) 20×GATE3: dropped discriminators. gen6: contract fix confirmed (WER 0.378→0.038) but zero effect-linked rules formed → the bootstrap had no feedstock → honest all-probe idle |
| 4c | gen7–9 + hkc | + shape-scoped milestone budgets, + exercisability gate, + REQUIRED discriminator | (running) | the attribution wave |

### What batch 4 already establishes (receipts across waves)

1. **The generated curriculum is real (falsified-if ii: NOT falsified).** With zero seeds, Sonnet lanes generated learn-shaped goals on 2/3 4a seeds — gen3 verbatim: *"Discover an action that produces a level-completion event"*, *"…a score-increasing event"* — the canonical chain from the owner's brief, produced by the deficit brief alone.
2. **The recognizer + auto-fill + milestone execution work live (falsified-if i: NOT falsified).** gen3: 3 DEFICIT stamps → 2 auto-filled milestones (verified edges) → **379 COMMITMENT_STEP beats — the first non-probe stamps ever recorded on ls20** (batches 1–3: zero commitments in every cell). ICR/GDS denominators exist for the first time on this game.
3. **Cold-start honesty (falsified-if iii: NOT falsified).** Every generative run's first stamp is the total DEFICIT with empty-evidence holes (pinned offline; observed live in all 7 Sonnet runs).
4. **The proof seam holds.** Across runs: 2 verified edges per engaged run vs 3–15 unverified (Surveyor-claimed fills that could not be proven — admitted, chain-irrelevant, exactly as designed).
5. **The gates police their own regime.** Every WER breach was a REAL contract gap (roster closure, dedup-under-reopened-holes, discriminator omission) surfaced by the floor and fixed same-day — the batch-1→2 pattern repeating at the next layer.
6. **Milestone economics needed two turns of the crank:** budgets must scale with the promotion bar *by test shape* (not provenance), and a milestone is compilable only if its rule is *exercisable now* (target-scoped + untargeted action ⇒ requires a route). Both pinned in chain1/chain2.
7. **P0 remains open, honestly.** 0 completions, 0 score everywhere — identical to BARE. The mechanic (what actually scores on ls20) is still unfound; what changed is that the system now *deliberately experiments* toward its hypotheses instead of idling, and states its ignorance in typed, auditable holes.

**Haiku lane:** hk1 = config artifact (fixed: standard extended thinking with effort-mapped budget). hkb/hkc = the real small-backbone readout (pending).

### Final batch-4 table (all 12 runs)

| run | wave | verdict | surv WER | goals | milestones | edges✓ | commits | probes | ktok | effect-rules |
|---|---|---|---|---|---|---|---|---|---|---|
| gen1 | 4a | INVALID | 0.28 | 9 | 1 | 1 | 378 | 19 | 2395 | 1 |
| gen2 | 4a | INVALID | 0.483 | 5 | 1 | 1 | 378 | 19 | 2423 | 1 |
| gen3 | 4a | INVALID | 0.378 | 14 | 2 | 2 | 379 | 11 | 198 | 5 |
| hk1 | 4a | (config) | — | 1 | 0 | 0 | 0 | 397 | 0 | 0 |
| gen4 | 4b | INVALID | 0.578 | 18 | 0 | 2 | 336 | 61 | 166 | 0 |
| gen5 | 4b | INVALID | 0.40 | 25 | 0 | 2 | 0 | 397 | 166 | 0 |
| gen6 | 4b | VALID | 0.038 | 5 | 0 | 0 | 0 | 397 | 137 | 0 |
| hkb | 4b | INVALID | 0.55 | 11 | 4 | 4 | 42 | 355 | 678 | 4 |
| **gen7** | **4c** | **VALID** | **0.0** | 3 | 0 | 0 | 0 | 399 | 504 | 0 |
| **gen8** | **4c** | **VALID** | **0.0** | 3 | 0 | 0 | 0 | 397 | 139 | 0 |
| **gen9** | **4c** | **VALID** | **0.0** | 29 | 0 | 2 | 51 | 347 | 399 | 0 |
| hkc | 4c | INVALID | 0.711 | 12 | 2 | 4 | 24 | 373 | 392 | 2 |

0 completions / 0 score everywhere (P0 open; identical to BARE). Batch-4 totals: 12 runs, ~7.6M tokens. gen1/gen2's 2.4M each = the unbounded-targeted-milestone pathology (an R8 Actuator call per commitment beat) — the shape-budget clamp fixed cost as well as economics.

### The two-backbone readout (P4 × chain, first data)

- **Sonnet-5-medium:** near-perfect emission (4c: WER 0.0 across 3/3 VALID) but conservative hypothesizing — with the disciplined contract, **no seed proposed a score/level-linked rule** (0 effect-rules), so the bootstrap idled honestly (stamps + probes). Where it did engage (gen9's RULE_STATUS milestones over exercisable cells-rules), the walk showed the intended balance: 51 bounded commitment beats / 347 probes.
- **Haiku-4.5 (fixed config):** rich hypothesizing — effect-linked rules on 2/2 lanes → auto-fill milestones → bounded experiment-commitments (42/24 beats) + the first live NEVER_VALIDATED→re-open cycles (hkc: 2) — but weak emission discipline (WER 0.55/0.71 → INVALID). Exactly the emission-vs-decomposition separation P4 was designed to print; the gate-rejection classes are the fine-tuning labels the cold-start doc predicted.

### Next levers (pre-register for 4d; do not run unprompted)

1. **Feedstock steering:** on an empty-evidence hole, the DEFICIT block should invite `PROPOSE_RULE` carrying the missing effect key (the engine auto-drafts its milestone) — the productive answer the disciplined Surveyor currently withholds.
2. **Zero-information goals:** gate 2 admits tests already TRUE at admission (gen3's "confirm RU0011 demoted" trio accepted instantly). Consider rejecting tests that evaluate true at admission — achievement without work.
3. **Haiku emission:** one-shot examples per op type in the contract, or a smaller closed op subset for small backbones; WER per class is the training signal.


### Wave 4d (confirmation, feedstock + A3 build): the full mechanism on VALID runs

Build adds (commit 6466617): design fold-in (§3.5 + amendments 20–25), **feedstock steering** (DEFICIT block invites PROPOSE_RULE on empty-evidence holes), **A3 zero-information gate** (tests already TRUE at admission rejected). gen10 died to a laptop-sleep connection error (voided, relaunched as gen10b); hkd survived the sleep and continues.

| run | verdict | surv WER | effect-rules | milestones | edges v/u | commits/probes | NV re-opens |
|---|---|---|---|---|---|---|---|
| gen11 | **VALID** | 0.0 | 2 | 2 | 3/1 | 24/373 | 2 |
| gen12 | **VALID** | 0.0 | 3 | 3 | 3/3 | 36/361 | 3 |
| gen10b | **VALID** | 0.0 | 4 | 4 | **8/0** | 96/301 | 8 |

**The 4d Sonnet cell closes 3/3 VALID with the chain ENGAGED on every seed** — the conjunction batches 4a–4c never produced (4a engaged but INVALID; 4b/4c VALID but idle). Feedstock steering is confirmed as the missing ingredient: disciplined Surveyors now hypothesize effect-linked rules when the machine states the hole, and the full loop runs under all gates — recognize deficit → invite feedstock → prove fills (gen10b: 8/8 proven) → bounded deliberate experiments → NEVER_VALIDATED → honest re-open. A3 needed zero enforcement rejections (the contract redirect held). Score still 0 everywhere: every hypothesis about WHAT scores on ls20 has so far been wrong and is demoted with receipts — the remaining gap is hypothesis QUALITY, not machinery.

---

## Step 3 (2026-07-17): first attributable P2 factorial + two instrument repairs

**Two §8-instrument defects found by the first factorial cells and fixed** (metrics are Log-computed → recompute, not re-run): (1) the shadow-agenda reference still mirrored the pre-chain walk — agenda-off cells had `drift_ref_beats=0`; the shadow now walks the chain-aware selection and computes the auto-fill tier VIRTUALLY (pure read; byte-identity intact; a0g1b re-ran: 394 reference beats). (2) GDS attribution charged untargeted beats to bind; the adopted operational taxonomy (design §8): **bind** = aimed emission on the plan's action landing wrong/dangling; **abandon** = the step not followed; **aligned** = faithful execution (untargeted steps have no join seam). Pinned by a 5-beat fixture.

### Factorial, 1 seed/cell, generative build (all VALID)

| cell | drift_ref_beats | GDS-bind | GDS-abandon | RGR | GA | ICR |
|---|---|---|---|---|---|---|
| FULL (gen10b/11/12) | 96/24/36 | 0.0 | 0.0 | 0.0 | 0.0 | 0.556/0/0 |
| J0 (j0g1) | 72 | 0.0 | 0.0 | 0.0 | 0.0 | 0.769 |
| A0 (a0g1b) | 394 | 0.0 | **1.0** | 0.0 | — | — |
| J0A0 (j0a0g1b) | 0 (no feedstock this seed) | — | — | 0.0 | — | — |

**What prints:** the **A-half of the P2 dissociation, cleanly** — killing the agenda flips GDS-abandon 0.0→1.0 with GDS-bind flat at 0.0 on both sides, against real shadow denominators. **What does not yet print:** the J-half — on generative ls20 seeds no rule survives to CHARACTERIZED (RGR 0.0 even in FULL) and this seed's milestones were untargeted-action rules (no aim seam for bind). *Honest scoping:* the J-half needs targeted-step-rich seeds (ACTION6-rule milestones) and/or a game where some hypothesis is right enough to promote — exactly what the multi-game slate probes. J0A0 needs a re-seed with feedstock. 1 seed/cell is the exploratory pass; the pre-registered protocol (≥3 seeds) stands for the claim-bearing table.

### Multi-game P0 slate (unseen games, 1 seed ×400, FULL-gen) + the 4d Haiku lane

| run | game | verdict | WER (surv/act) | effect-rules | milestones | stamps | commit beats (step-id) | levels/score |
|---|---|---|---|---|---|---|---|---|
| tn36a | tn36 (unseen) | **VALID** | 0.0 / — | 3 | 3 | 4 | 106 (targeted-rich) | 0/0 |
| su15a | su15 (unseen) | **VALID** | 0.0 / — | 12 | 9 | 17 | 112 | 0/0 |
| cd82a | cd82 (unseen) | INVALID | 0.645 / **0.541** | 6 | 6 | 7 | 34 | 0/0 |
| hkd | ls20 (Haiku 4.5) | INVALID | 0.576 / — | 8 | 8 | 9 | 64 | 0/0 |

- **Generality (§7): the chain machinery engaged on 3/3 unseen games with zero game-specific code or tuning** — generated curricula, effect-linked hypotheses, milestones, deficit stamps everywhere; 2/3 VALID. tn36a is targeted-step-rich (106 aimed commitment beats) — the seed profile the P2 J-half needs.
- **cd82a is the campaign's first Actuator floor breach**: R8 containment realization degrades on cd82's geometry — an organ-specific stressor no ls20 run produced; the WER-per-organ discipline localizes it (emission, not machinery).
- **Haiku (hkd, third fixed-config lane): Surveyor WER 0.55/0.71/0.58 across hkb/hkc/hkd** — consistent, not anecdotal: decomposition rich (8 milestones, 64 commit beats), emission structurally short against this op vocabulary. The pre-registered lever (per-op examples / reduced op subset for small backbones) is the P4 path; run spanned a host sleep (continuity caveat, moot under INVALID).
- **P0 at 1 seed: 0 completions on all games** — open, as on ls20. The §8-protocol claim table (≥3 games × ≥3 seeds) remains the bar; this slate establishes the machinery's substrate-generality, not efficacy.

**Step-3 + wave-4d cost:** 13 runs (4d ×4 + factorial ×5 incl. reruns + games ×3 + gen10 voided), ~2.6M tokens. Campaign total to date: ~10.4M tokens, 30 runs.

---

## Wave E (2026-07-17): the claim-bearing factorial, the containment artifact, and the Haiku emission lever

**E1 — ls20 factorial at protocol seed count (all cells VALID):**

| cell | seeds | feedstock | GDS-bind | GDS-abandon | ICR |
|---|---|---|---|---|---|
| FULL (gen10b/11/12) | 3 | 3/3 | 0.00 | 0.00 | .56/0/0 |
| J0 (j0g1/2/3) | 3 | 3/3 | 0.00 | 0.00 | .77/.74/0 |
| A0 (a0g1b/2/3) | 3 | 2/3 | 0.00 | **1.00** (n=2 defined) | — |
| J0A0 (j0a0g1b/2/3/4) | 4 | **0/4** | — | — | — |

**P2 A-half: CONFIRMED at protocol scale.** Killing the agenda flips GDS-abandon 0.00→1.00 with GDS-bind flat at 0.00 wherever defined (up to 394 shadow-reference beats/run). **Emergent second readout — the feedstock gradient:** effect-hypothesis formation runs 3/3 (FULL) = 3/3 (J0) > 2/3 (A0) > 0/4 (J0A0). The joint kill floors the system UPSTREAM of drift: with neither the join nor agenda context in the epoch view, effect-linked hypotheses never form (≈1% under a two-thirds per-seed rate if independent) — J0A0 ≈ near-bare floor manifesting as feedstock collapse, one layer earlier than the design predicted it.

**The tn36 containment artifact (integrity-class fix).** The J-half probe (j0tn1, bind 0.878) matched its FULL comparator (tn36a, 0.906) — and decomposition traced every wrong landing to ONE pair: clicks R8-validated INSIDE the aimed component (R0089) were containment-stamped to the enclosing board (R0004) by first-by-id scan order. Not just fake drift in every cell: **96 receipts were attributed to the wrong referent during the runs**, starving the aimed rule. `stamp_target` now attributes the MOST SPECIFIC (smallest) containing referent — geometry still decides — pinned by a nested fixture. ls20 unaffected (disjoint components; bind 0.0 throughout).

**J-half: OPEN.** Post-fix tn36 re-rolls (tn36b/c, j0tn2/3, ±examples) all drew feedstock-less seeds — tn36 engagement ≈ 1/5/run, and the paired requirement (engagement in BOTH cells) makes re-rolling uneconomical. Also noted: the one engaged tn36 run predates the containment fix — the mis-attributed receipt density may itself have fed hypothesizing (receipts-beget-rules), suggesting a real lever: hole evidence carrying per-referent receipt density. Pre-registered, not run. tn36 remains the right J-half game: it promotes rules (first CHARACTERIZED referents of the campaign, RGR 0.5) and compiles aimed milestones.

**E2 — the Haiku emission lever: CONFIRMED, and the first VALID Haiku run.** `ARG_OP_EXAMPLES` (worked per-op examples, config-gated; Sonnet contract byte-stable): Surveyor WER 0.55/0.71/0.58 (hkb/c/d, no examples) → **0.333** (hke, examples; residue = one class, missing evidence_ptrs) → **VALID, zero rejected ops** (hkf, examples + explicit evidence_ptrs requirement). Small-backbone emission is a solved contract problem, not a model wall; the engaged-VALID-Haiku decomposition readout awaits a feedstock-lucky seed.

Wave E: 14 runs ≈ 3.3M tokens. Campaign total: ~13.7M tokens, 44 runs. P0 open everywhere (0 completions).

---

## Wave F (2026-07-18): target-scoped steering + receipt-density anchors — every lane engages

**F0 build:** hole evidence gains `receipted_refs` (top-5 referents by receipt count — the receipts-beget-rules observation, mechanized); the DEFICIT block prefers rules SCOPED to a specific referent ("the effect needs the RIGHT object, not the right button" — every untargeted single-action effect rule in the campaign had demoted).

| run | cell/backbone | verdict | surv WER | targeted effect-rules | milestones | commit beats | levels/score |
|---|---|---|---|---|---|---|---|
| f1 | ls20 FULL | **VALID** | 0.0 | yes (9 ms) | 9 | 192 (ICR .814) | 0/0 |
| f2 | ls20 FULL | **VALID** | 0.0 | 3/3 | 3 | 96 | 0/0 |
| f3 | ls20 FULL | **VALID** | 0.0 | 3/3 | 3 | 72 | 0/0 |
| tn36f | tn36 FULL | **VALID** | 0.0 | yes | 24 | 130 | 0/0 |
| j0tnf | tn36 J0 | **VALID** | 0.0 | yes | 17 | 78 | 0/0 |
| hkg | ls20 Haiku+ex | INVALID (.364, 4×dup) | — | 2 | 2 | 48 | 0/0 |
| hkh | ls20 Haiku+ex | **VALID** | **0.0** | 2 | 2 | 48 | 0/0 |

**What wave F establishes:**
1. **Steering works everywhere:** target-scoped effect hypotheses on 7/7 engaged runs (prior ls20 waves: zero targeted). Engagement itself jumped — every Sonnet lane engaged, both games.
2. **The P2 J-half verdict (paired, engaged, honest attribution):** FULL ≡ J0 on tn36 across every per-beat and grounding metric (bind 0.0=0.0, abandon 0.0=0.0, RGR 1.0=1.0, GA .964=.964). **The render join's drift-prevention load is ABSORBED INTO STRUCTURE** — R8 containment, substitution-catch, and receipt-driven rungs are Executive-owned, so the failure channel the join guarded in Sensi-era systems cannot open here. The J-dimension's measurable residue is upstream (J0A0 feedstock collapse 0/4; 4a-era GATE1 rejections). This reframes P2's J-arm: structural absorption, not printed drift — with X2-class effects to seek in proposal-quality metrics.
3. **The P4 conjunction achieved: hkh = Haiku 4.5, VALID (WER 0.0), ENGAGED** (2 targeted hypotheses → 2 milestones → 48 aimed experiment beats, zero rejects). With examples + steering, the small backbone runs the complete loop cleanly. Decomposition richness per backbone now has its first clean pair: Sonnet f1 9 milestones/192 beats vs Haiku hkh 2/48 — the tier gap is real but the floor is crossed. hkg's residue (4× duplicate re-proposals) names the third examples-block iteration if wanted.
4. **P0 still open, sharper:** the engine tests ~3 wrong object-scoped theories per 400-action seed, efficiently and honestly. The bottleneck is now candidate ORDERING (which referent to test first) — receipted_refs data exists per hole; ranking auto-fill candidates by it is the queued lever.

Wave F: 8 runs ≈ 2.2M tokens. Campaign totals: **~17M tokens, 52 runs**; every number gated, replayable from the Log.
