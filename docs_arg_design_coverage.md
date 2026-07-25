# ARG Design Coverage — is the entire docs_arg_design.md implemented?

*Re-verification at HEAD, 2026-07-17 (after wire-up C1–C6 and gap-closure D1–D4). Method: the design's requirement inventory (§1–§9) checked element-by-element against the code, with wiring greps confirming every claimed mechanism is CALLED where the design says (not merely defined); 22/22 ARG test suites (~300 assertions) green at HEAD; Sensi goldens byte-identical; two live smokes on the real ARC server as behavioral evidence. Historical passes: the first audit (§4 note) found the thesis mechanisms built-but-unwired; C1–C6 wired them; D1–D4 closed all 16 residual build gaps.*

---

## Verdict

**The entire agent-code surface of the design is now implemented and tested.** Every mechanism in §2–§6 (structure, grounding, goals, organs, the doing loop, the question-list answers) and the §8 measurement layer is implemented, wired into the live loop, and covered by a test that would catch its regression — with **fifteen named narrowings** (§3) where the implementation is deliberately simpler than the design's letter; each is visible in code comments and none touches the forgery-resistance or attribution invariants.

What "the entire design" still does NOT include — and by the design's own nature cannot, as agent code:

1. **Campaign artifacts (§8/§1):** the factorial and ablation RUNS (≥3 games × ≥3 seeds), the decoy stress arm, the sensitivity/Z-tier/position/ZCR-calibration sweeps, parity rows + conditional compute-matched arms as executed comparisons, P0–P4/X1/X2 evaluation and the downgrade clause. Everything they need — cells, seams, comparators, metrics, validity gates — now exists; these are experiment executions, not code.
2. **Other tracks (§7):** the P3 long-context instantiation (TextSpan locator schema exists; the deterministic re-read engine does not), the Kaggle small-backbone arm, and the release-gate tooling (exemplar scrub + vocabulary lint).
3. **A8** (`ARG_SPLIT`, three backbones): deliberately RESERVED, labeled as such in config.

Status legend: **LIVE** = implemented, loop-wired, test-asserted (items marked ⊙ also exercised against the real ARC server); **NARROWED** = implemented with a §3-listed simplification; **CAMPAIGN/TRACK/RESERVED** as above.

---

## 1. Coverage by design section (current)

### §1 Thesis & falsifiable program
| Element | Status |
|---|---|
| GDS-bind/GDS-abandon as computed metrics; real shadow reference in every cell | **LIVE** |
| P0–P4, X1/X2, downgrade clause; efficiency-conditioned-on-success reporting | **CAMPAIGN** (all consumed metrics exist) |

### §2 The ARG structure
| Element | Status |
|---|---|
| §2.1 LLM-proposes/Executive-disposes; typed proposals; validators at every ingest ⊙ | **LIVE** |
| §2.1 retry budget + completeness invariant + WER/DPR per organ | **LIVE/NARROWED** — one corrective re-prompt (within "≤2"); drops metered `retry_count=1` = honest DPR; the second-round one-op-per-call decomposition is not implemented (§3.2) |
| §2.1 WER floor → run disqualification | **LIVE** (per-organ floor, min-ops guard, wired into run_validity) |
| §2.2 schema (all records; premise closure; pre-committed predictions) ⊙ | **LIVE** |
| §2.2 `controllable` earned annotation | **LIVE** (movement-correlated observations; HYPOTHESIS→TESTED at k; consumed by mover selection) |
| §2.2 `scope` across deaths (lives/life_event) | **LIVE/NARROWED** — lives captured at the choke point (FrameData lacks the field); PERSISTENT/WITHIN_LIFE/UNKNOWN computed; WITHIN_LIFE excluded from means analysis until re-armed (§3.15) |
| §2.3 grounding tiers, machine-verified ⊙ | **LIVE** (ENGAGED incl. null effects on the real server; CHARACTERIZED off a pre-committed prediction in loop tests) |
| §2.3 rules climb/demote + TTL re-probe | **LIVE** |
| §2.3 relations climb/demote | **LIVE/NARROWED** — same_as has full mechanics (co-presence refutes → DEMOTED; alternation promotes → TESTED + MERGE_CANONICAL); other verbs have endpoint-dormancy demotion + TTL only (§3.6) |
| §2.4.1 working set vs archive; index line; overflow logged | **LIVE** |
| §2.4.2/.3 chain retention, eviction rank, gate-6 arithmetic | **LIVE** (gate-6 tested) |
| §2.4.4 margin rule; §2.4.6 carryover + T5 boundary demotion ⊙ | **LIVE** |
| §2.4.5 evidence compaction | **LIVE** (consequence signatures: count + change/no-op/event split + exemplar pointers, rendered in Z6) |
| §2.4.7 budget table; warmup; B calibration sweep | **LIVE** for enforcement (B everywhere + terminal clamp; ZCR floors post-warmup); the position-sweep that calibrates B is **CAMPAIGN** |
| §2.5 zones Z1–Z6 (real grid, joins, R2 substitution) + R1–R9 ⊙ | **LIVE** (R5 via ingest validators — §3.8; Z4 scoped + regime-pruned; C_max paginates the ChangeSet; log tail ≤L keyed turns) |
| §2.5 ZCR: salt/echo/floors/diagnosis ordering/R6 live trigger ⊙ | **LIVE** (9/9 with real Sonnet; uniform→INVALID; differential→"consumption rot" + LIVE compact fallback; calibration vs task metrics is **CAMPAIGN**) |
| §2.6 identity: BindingRecords, margin, prefilter+exclusive assignment | **LIVE/NARROWED** (greedy-exclusive approximates Hungarian — §3.1; AMBIGUOUS band auto-binds — §3.11) |
| §2.6 FISSION-CHECK + FISSION EXECUTE | **LIVE** (statistic + full execute: children per signature cluster, lineage, parent DORMANT, rules demoted, bindings widened, steps blocked, T1; receipts stay with the retired parent — §3.5; `ARG_FISSION` kill switch) |

### §3 Goals
| Element | Status |
|---|---|
| Schema; seeds (disjunctive G0, LEARN-*, no game nouns) ⊙ | **LIVE** |
| G0 test-the-test audit | **LIVE** (G0-AUDIT row naming which signals moved) |
| Six admission gates + anti-oscillation over real NEVER_VALIDATED rows | **LIVE** (all six tested) |
| Status machine incl. EXPLORED/VALIDATED/terminal rule/REOPENED ⊙ | **LIVE** (budget spend counts committed actions — §3.7) |
| LEARN-* quantification over live context classes | **LIVE/NARROWED** (live = current regime per level — §3.4) |
| **§3.5 chain recognizer** — chain_status COMPILABLE/REDUCIBLE/DEFICIT(typed holes+evidence); cold start = total DEFICIT (pinned) ⊙ | **LIVE** (chain1; batch 4) |
| §3.5 goal_edge + verified fill (knowledge/signal proofs; fills_hole claims proven or unverified) ⊙ | **LIVE** (chain1/chain3) |
| §3.5 milestone grammar A1 (EXISTS/COUNT-where, RULE_STATUS, RUNG; COUNT value/cmp) ⊙ | **LIVE** (chain1; §7 lint) |
| §3.5 auto-fill A2 (DEFICIT provenance through the six gates; budget = max(8, 6·K_SUPPORT) by SHAPE) ⊙ | **LIVE** (chain2) |
| §3.5 milestone experiment-commitments (HYPOTHESIS rule as premise+prediction; exercisability gate) ⊙ | **LIVE** (chain2) |
| §3.5 deficit stamps (append-only, deduped) + epoch DEFICIT block + walk ancestors-deepest-first ⊙ | **LIVE** (chain2/chain3) |
| §3.3 gate 2 A3 (false-at-admission / GATE2_TRUE_AT_ADMISSION) | **LIVE** (engine/chain3 pins — 2026-07-17) |
| §5.3 rank key #1 (verified-edge-into-live-parent first) ⊙ | **LIVE** (chain1) |
| §7 tool seam (adapter.tools(); no action-name string-matching above adapter, grep-pinned) ⊙ | **LIVE** (chain2) |
| §8 chain quartet (deficit_stamps, milestone_conversion, edges_verified/unverified; pre-chain DBs read None) | **LIVE** (chain3) |

### §4 Organs & Log
| Element | Status |
|---|---|
| Observer: closed algebra, fires-iff-unexplained, quiets, C_max pagination, ≤L tail ⊙ | **LIVE** (BIND candidate routing narrowed — §3.11) |
| Surveyor: gated goals/rules/relations/experiments; resolved Revision-Evidence gate; counterexample buckets; real action frontier; epoch caps ⊙ | **LIVE** (RANK_TIEBREAK gated but not persisted — §3.9) |
| Actuator: deterministic default; R8-confined realization; retry→verbatim-centroid FALLBACK; stamps | **LIVE** |
| Log: TurnRecord (prediction/match/step/shadow/drift/lives/render_tokens), WRITE_REJECT, SUBSTITUTION_CAUGHT, REVISION ⊙ | **LIVE** |
| Directed bridge (Actuator never reads Log) | **LIVE** by construction |

### §5 The doing loop
| Element | Status |
|---|---|
| B1–B8; modal beat 0 calls; T1–T5 + lease + rate limit + per-level caps ⊙ | **LIVE** |
| Commitments: persistence, consume-on-success, premise auto-block, lease, Surveyor-only revision (store-resolved evidence + REVISION rows) | **LIVE** |
| §5.4 Procedures: distill → reuse-before-means-analysis → replay-TESTED → scope demotions → TTL | **LIVE** (slot rebinding deterministic — §3.12) |

### §6 Q1–Q16
All answered by live mechanisms; Q4's renderer invariant holds by construction of means-analysis+Z6 (no dedicated invariant test — accepted); Q10/Q15 are TRACK (TextSpan engine; human-edit tooling).

### §7 Generality
Adapter-only env code, no game nouns, machine-derived kind, honest tri-state image receipt — **LIVE**. P3 instantiation, negative control, release gate — **TRACK/CAMPAIGN**.

### §8 Ablations & baselines
| Element | Status |
|---|---|
| Metric table (all ~17 incl. GDS family, ICR, DTL, FBR, FCR, APR, FSN, ECR, WER/DPR, SCL, SRR, ZCR, slope, bins) | **LIVE** (GA closure — §3.3; DPR = one-retry drops — §3.2) |
| Factorial seams J/A + real shadow instrumentation + byte-identity | **LIVE** |
| Ablation seams A3–A7, A9–A11 (+ FISSION kill) | **LIVE** (each consumed + tested) |
| Baselines: bare backbone, raw-history (pinned protocol agents), B-CACHE configuration | **LIVE** (argbare/argraw: one call/action, fixed template; ARG_BASELINE=bcache: substituted-view decisions, rungs frozen, no goals) |
| HRT (reject rates + mismatch-by-stamp + actuator-vs-step delta); length-stratified bins; goldens | **LIVE** |
| A8 role split | **RESERVED** |
| Runs, sweeps, parity/compute-matched executions, decoy arm | **CAMPAIGN** |

### §9 Failure-mode instrumentation
FSN + execute path (9.1) **LIVE**; WER/DPR/SRR (9.2) **LIVE**; REOPENED + FCR in-run (9.3) **LIVE** (offline replay-audit of ACCEPTED verdicts — CAMPAIGN); `discriminates` on experiments (9.4) **LIVE as data** (not consumed in rule adjudication — §3.13); SCL + A0/A9 bracket + sweep-able constants (9.5) **LIVE** as seams.

---

## 2. Score

Of the design's ~90 checkable elements: **~78 LIVE (15 of them narrowed as below), 0 absent-build, the remainder Campaign/Track/Reserved.** Every pinned constant is consumed and test-asserted except `ARG_SPLIT` (reserved). All 28 store tables are written by live code paths. All 13 §2.1/§3.3/R8 reject classes fire in tests.

## 3. The fifteen residual narrowings (deliberate, documented in code)

1. Identity assignment is greedy-exclusive over anchor-overlap-or-signature candidates, not Hungarian-optimal.
2. Write-path retry = ONE corrective re-prompt (within the "≤2" budget); the second-round one-op-per-call decomposition is unimplemented; DPR = one-retry drops.
3. GA's binding closure = union of goal bindings, not the per-beat active goal's closure.
4. "Live context classes" = the current regime (latest class per level); superseded regimes are unrevisitable (keeps LEARN-ACTIONS satisfiable).
5. Fission re-attribution is query-side: receipts stay keyed to the retired parent, joinable via lineage + BindingRecords; children re-earn support fresh.
6. Relation receipt semantics exist for same_as only; other verbs get endpoint-dormancy demotion + TTL re-probe.
7. Goal budget spend counts committed actions only (probes don't decrement).
8. R5 (outputs cite ids or die) is enforced by the ingest validators' dangling-ref rejections, not a universal output linter.
9. Admitted RANK_TIEBREAKs pass the resolved gate but are not persisted as ordering state (rank stays purely Executive-computed).
10. B's positional-bias calibration sweep and the ZCR↔task correlation are pre-registered campaign work; the constants they would tune are env-sweepable today.
11. The AMBIGUOUS margin band auto-binds instead of routing to the Observer-BIND hop (the validator path exists; the loop passes an empty candidate set).
12. Procedure slots rebind deterministically to the leaf's bound referent (Surveyor-proposed alternative bindings not implemented).
13. Experiments' `discriminates` list is recorded and reported, not consumed in rule adjudication.
14. bare/raw comparators share the global MAX_TOKENS as the pinned per-call budget (no separate constant).
15. WITHIN_LIFE plan discipline = exclusion from means analysis until a post-death match re-arms the rule (approximates "compile within one life").

## 4. History

First audit (this file's original verdict): substrate faithful, thesis mechanisms built-but-unwired; the previous in-session "10/10" verification had checked structural forgery-resistance only. **C1–C6** (d80c36a…a5aace9) wired pre-registration, the acting agenda, the real join, real shadow compile, the ZCR loop, and lifecycle hygiene — live-verified on the real server (30 ENGAGED referents via null-effect receipts; ZCR 9/9 with real Sonnet; gates rejecting real proposals). **D1–D4** (bf80258…c60677e) closed all 16 build gaps (test_arg_gaps1–4, 67 assertions) — including two incidental catches: the loop/probes suites had been silently reaching a real backbone (now hermetic), and the ZCR machinery's first test caught its own over-salting. ZCR warmup wired in this pass. Full regression at HEAD: 22/22 suites; Sensi goldens byte-identical.
