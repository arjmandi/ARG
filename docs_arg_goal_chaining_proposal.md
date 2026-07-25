# Proposal: Goal-Chain Sufficiency — the recursive decomposition engine

*Response to the owner's directive (2026-07-17): "we need a mechanism that chains the goals… if enough goals to implement the multi-step navigate-then-interact mechanic exist in ARG we align ARG understanding to these goals; if not, we create more sub-goals with the help of the LLM, to complete our chain, which will reduce to single-action at execution level. The load-bearing part is the ability to recognize if we have enough goals to implement multi-step or not." Reviewed against docs_arg_design.md; this is a proposal for approval, not an implementation.*

---

## 1. Review: what the design already says, and what is actually missing

The directive is not an addition to the design — it is the design's §3 taken at its word, completed. The existing text already contains every fragment:

| Design text | What it gives us |
|---|---|
| §3: "Goals are **expandable axioms**… the goal ladder relates structural learnings to ordered ends" | the decomposition INTENT |
| Owner's brief (quoted in §3.2): "learn the actions, learn the rules, (maybe learn the env), then win the game… these are logical reasoning, they can be manipulated easily by an LLM" | the canonical top chain |
| §4.3 step 4: "**Unmet preconditions → each becomes a candidate sub-goal** surfaced to the Surveyor through the §3.3 gate" | the expansion TRIGGER |
| §4.2: the Surveyor writes "goal expansions" through the six gates | the expansion CHANNEL |
| §5.3: rank = "deterministic function of **dependency edges**, status-machine state, remaining budget" | the ordering over a chain |
| §4.3 steps 2–3 + §5.4 + M6: means analysis → NAVIGATE\*+INTERACT compilation | the REDUCTION to single actions |

**What is missing — three pieces, one of them the load-bearing one:**

1. **No dependency edges exist.** `parent_goal` is lineage, not a plan edge. §5.3's rank key #1 ("dependency edges among siblings first") has nothing to read. A proposed sub-goal is just a sibling; nothing records *what hole in which parent it fills*, so nothing can ever conclude "the chain is complete."
2. **No sufficiency recognizer.** The walk's per-goal question is binary (means analysis succeeds / probe). There is no computed answer to the owner's question: *"do the goals currently in ARG suffice to implement the multi-step chain?"* — and therefore no principled moment to say "align and execute" vs "expand."
3. **Intermediate goals are inexpressible**, so even a willing Surveyor cannot fill a hole: the closed test grammar spans {score, levels_completed, state, lives} + bare LEARN markers. "Reach/arm/test-the-door" has no admissible test. Batch 3 showed this with receipts: four score-linked HYPOTHESIS rules that nothing could ever *deliberately* test, because the goal that would test them cannot be written.

The campaign data confirms the diagnosis end-to-end: grounding, rule formation, experiments, gating, economy all work (six VALID FULL runs), and the run stalls exactly at the decomposition boundary — the §9.2 idle-during-the-hardest-phase trade, which this proposal narrows structurally instead of accepting.

---

## 2. The proposal

### 2.1 Chain semantics: dependency edges with verified fill

New store table (append-only like everything):

```
goal_edge { run_id, parent_goal, child_goal, hole_json, verified: 0|1, created_turn }
```

An edge means: *child fills a named hole of parent*. Edges are created only at admission, and only when the Executive **verifies the fill mechanically** (§2.3 below) — an LLM cannot assert that a sub-goal helps; the schema check proves it or the edge (and with it the chain claim) does not exist. This is what finally feeds §5.3's rank key #1: children order before the parents they serve.

### 2.2 The sufficiency recognizer — `chain_status(G)` (THE load-bearing piece)

A deterministic, records-only, bottom-up computation. No LLM anywhere in it.

```
needs(g)      = unmet effect-keys of test(g)            # {score_event, level_event, …}
              ∪ unmet record-predicates of test(g)      # EXISTS/COUNT clauses not yet true

EXECUTABLE(g) = _select_means(g) ≠ None                 # a TESTED rule/procedure serves g NOW
              (compiles to NAVIGATE* + INTERACT — single actions at execution level)

holes(g):
    if status(g) = ACCEPTED:      ∅
    if EXECUTABLE(g):             ∅
    for each need n in needs(g):
        if ∃ verified edge (g ← c), c live, holes(c) = ∅:   n is covered
        else:                                                n is a HOLE, carrying evidence:
             • HYPOTHESIS rules whose closed effect ⊇ n      (the derivable fills)
             • referents with partial receipts toward n
             • the action model / controllable status         (can we even reach things?)

chain_status(G) = COMPILABLE  if EXECUTABLE(G)
                = REDUCIBLE   if holes(G) = ∅ (via covered needs)
                = DEFICIT(H)  otherwise, H = the typed hole list
```

This answers the owner's question exactly and mechanically: **"enough goals" ⇔ `holes(G0-path) = ∅`.** The recognizer runs in the walk (B1) and at every epoch; its output is stamped (auditable) so "the system believed its chain was complete at turn T" is replayable data.

### 2.3 The sub-goal vocabulary: knowledge milestones (grammar extension, scoped)

Intermediate goals stay consequence-grounded by being **milestones of knowledge**, not of appearance. Extend the closed grammar with `where`-clauses over EXISTING record fields only:

```
{op: EXISTS|COUNT, entity: consequence,  where: {action, target, match, score_event, level_event}}
{op: RULE_STATUS,  rule: RU####,  is: TESTED}          # sugar over status records
{op: RUNG,         ref:  R####,   at_least: ENGAGED|CHARACTERIZED}
```

No colors, no positions, no prose — every predicate resolves against Executive-stamped rows. This makes the bridge goals *writable*:

- **"Test RU0005"** := `EXISTS consequence WHERE predictor=RU0005 AND match=1` — achieving it means the hypothesis score-rule got a pre-registered matched receipt; the parent's `_select_means` then succeeds **by construction**.
- **"Engage R7"** := `RUNG(R7) ≥ ENGAGED` — the reach-and-touch milestone; compiling it is precisely NAVIGATE(R7) + INTERACT — the multi-step navigate-then-interact mechanic *emerges as the compilation of a knowledge milestone*, using machinery that already exists (action model, compile_navigate, arrival handoff, R8).

**Verified fill (edge admission):** an edge (g ← c) is verified iff, mechanically: c's test being ACCEPTED makes at least one of g's needs satisfiable — two checkable forms: (i) *knowledge fill*: c's test is RULE_STATUS/EXISTS-matched-receipt over a rule whose closed effect ⊇ the need; (ii) *signal fill*: c's effect-keys ⊆ g's needs. Anything else: edge refused, sub-goal admitted (if it passes the six gates) but chain-irrelevant — it cannot fake completeness.

### 2.4 Expansion: derivable holes fill themselves; the LLM fills the novel ones

Per the owner: *"if not, we create more sub-goals with the help of the LLM."* Two tiers:

1. **Deterministic auto-fill (0 LLM).** A hole that names its own fill — "no TESTED rule with effect ⊇ {level_event}, but HYPOTHESIS rules RU5–RU8 carry it" — is derivable: the Executive drafts the milestone sub-goals ("test RU5", …) itself and admits them through the same six gates, provenance `DEFICIT` *(design amendment A2 below)*. This is the hypothesis-rule bootstrap that batch 3 was missing, and it needs no reasoning.
2. **Deficit-driven Surveyor expansion (the LLM's proper job).** When the hole is NOT derivable — no candidate rule exists at all — the T3 epoch's BudgetedView gains a **DEFICIT block**: the typed holes with their evidence, plus the instruction "propose sub-goals that fill exactly these holes; cite the hole id." Proposals carry `fills_hole`; the Executive runs the verified-fill check before creating the edge. This is §4.3-step-4 finally operational, and it aims the Surveyor's "logical reasoning an LLM manipulates easily" (the brief's phrase) at a machine-stated question instead of an open sky — which is also what should finally cut the duplicate-proposal noise to zero.

### 2.5 Alignment and execution ("align ARG understanding to these goals")

When `chain_status = REDUCIBLE/COMPILABLE`:
- **Walk:** execute the chain **frontier** — the deepest hole-free EXECUTABLE descendant along dependency order (replaces batch-3's flat first-compilable scan). Consume-on-success propagates upward: a child's ACCEPT re-evaluates the parent's holes the same beat (B6 already re-evaluates every goal).
- **Render:** Z1's chain line and Z6's card show the decomposition path root→…→active milestone with hole status (`chain: COMPLETE` / `holes: 2`); chain-bound referents keep their never-evicted retention (§2.4.2 unchanged — the chain is now the real chain).
- **Rank:** dependency edges take their designed place as key #1; the REOPENED-LEARN leaf-lock disappears as a side effect (a reopened coverage goal without edges into the active deficit no longer outranks the milestone path).

### 2.6 What does NOT change

The six gates, immutable tests, budgets → NEVER_VALIDATED, anti-oscillation, append-only truth, LLM-proposes/Executive-disposes, pre-registration→match, R1–R9, ZCR, the factorial seams. No appearance-based test becomes expressible. Chain size is bounded by the existing arithmetic: gate 6 (N_max), per-goal budgets, and the epoch caps bound expansion; goal_edge rows are append-only audit data.

---

## 3. Risks, named (with their existing instruments)

- **Goodhart on milestones (§9.3):** a milestone chain can complete while the parent stays unachievable (wrong rule tested). Instruments already in place: parents' tests are unchanged and Executive-evaluated; FCR; budget exhaustion → NEVER_VALIDATED on the milestone; the DEFICIT recomputes and the chain honestly re-opens holes.
- **Chain explosion:** bounded by N_max/budgets/epoch caps; the recognizer's holes are per-need, not per-imagination; APR prices pollution.
- **Grammar creep (§9.2 vigilance):** the extension is three predicate forms over existing stamped fields, pre-registered here; the §7 vocabulary lint applies to it; nothing else enters.
- **Residue:** a mechanic whose intermediate state produces NO record signature under any probe remains invisible (§9.4 stands, narrowed: "seen but untypeable" now excludes everything receipt-shaped).

## 4. Expected observables + falsified-if (pre-registered for the next batch)

- First **DEFICIT stamps** naming "no TESTED rule with level_event" with RU-candidates (ls20, ~turn 30–60).
- First **auto-filled milestone goals** ("test RU####") admitted with verified edges; first **experiment-commitments** compiled toward them: NAVIGATE\*+INTERACT with the hypothesis rule's prediction pre-registered → **the first non-probe stamps on ls20** (COMMITMENT_STEP / ACTUATOR_LLM), first ICR ≠ None, first GDS denominators > 0 — the factorial's A-dimension finally measurable on this game.
- Holes close monotonically absent regime shifts; duplicate-proposal rejections → ~0 (the Surveyor now answers a stated question).
- **Falsified-if:** with the recognizer live, FULL still produces zero commitments over ≥3 seeds × 400 actions while DEFICIT stamps exist with derivable fills — then the recognizer or the reduction is wrong, and the mechanism (not the game) is charged.

## 5. Design amendments requiring the owner's blessing (2)

- **A1 — grammar extension** (§2.3): `where`-clauses + RULE_STATUS/RUNG predicates over existing stamped fields, as the sub-goal test vocabulary. (Enters the §7 glossary/lint like every closed vocabulary.)
- **A2 — `DEFICIT` provenance** (§2.4 tier 1): the Executive may auto-admit *derivable* milestone sub-goals through the six gates without a Surveyor round-trip. Alternative if rejected: the Executive only DRAFTS them into the epoch view and the Surveyor confirms — one extra LLM call per derivable hole, LLM stays sole proposer.

## 6. Implementation plan (after approval)

- **G1** store (goal_edge) + predicates (where/RULE_STATUS/RUNG) + `chain_status` + hole taxonomy — offline tests: sufficiency verdicts on constructed trees; verified-fill accept/reject.
- **G2** walk-frontier execution + rank-by-edges + auto-fill tier + DEFICIT stamps — loop tests: hypothesis-rule bootstrap end-to-end in a mock (milestone → experiment-commitment → parent compilable → parent achieved).
- **G3** Surveyor DEFICIT block + `fills_hole` ingest + contract text — live batch 4 on ls20 (FULL ×3, 400 actions) against the §4 falsified-if.
- Estimated size: ≈ C2's footprint (~600–800 lines + tests). Metrics additions: holes_open/filled, chain_depth, milestone conversion rate.
