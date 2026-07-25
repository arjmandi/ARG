# ARG Brief — verbatim from the project owner (2026-07-16)

This is the binding input for the ARG design workflow. ARG is a NEW system, entirely
different from Sensi, inspired by Sensi's findings. Observe-and-improve is finished;
this is a re-design step. After the design is reviewed we may change the benchmark
from ARC-AGI to another benchmark that prioritizes this limitation in LLMs, then test
on ARC-AGI as well.

---

## Intro (owner's corrections and values, verbatim)

no, we are wrong on multiple ground.

let's first adjust expectations and values.
1. this statement doesn't hold. if you read "That's also a paper-grade result in itself: 'discover at frontier once, execute at commodity forever' is the tier-ladder story with numbers."
if you read "sensi_review_response.docx" you can see we've already wrote a paper on how sensi was able to fully learn its general curriculum but with zero win and it was rejected from two venues. while it had a good foundation.

2. on analyzing the gap: don't go into excuses, the gap is not monolithic but these improvements were harness bugs or some logical errors that blocked us from winning the L1 of ls20. this win is very tiny. so the peeling is also tiny. it doesn't matter that the gap is or isn't monolithic, we still don't get this gap properly. this is our path.
this is the reason we can't have concrete assumptions on games and some of the findings like "going on the hatch is not enough" can be nearly useless in other games. and capabilities that bring them (a frontier model) might not be sufficient in next levels or next games.

of course the value of an academic paper is high but our goal is to achieve and build an effective representation of the knowledge that addresses referent grounding effectively and test it on ARC AGI game complexity and demonstrate strong signal of progress in this field with ablation.
probably we will later apply the design to other benchmarks as well.

don't get lost in winning one level of one game. if we even solve L4 and sensi is not able to move to other games or scores nearly zero there, we have achieved nothing and we'll publish nothing.

this is not accepted: to run a frontier model once on all games then get another round to play them:
1. ARC AGI is designed for the agents to learn on the game, with the energy they have, maybe fail a couple times but not totally lose, then move to the next level. this is accepted; while training on all games and levels a lot is not what ARC AGI has been designed for and makes it hard for RL-maxing it like Atari.
2. ARC AGI has a private set; it's better to read how that works on the Kaggle competition page.

another point: in the ARC AGI Kaggle competition they have mentioned they will cut off internet access: https://www.kaggle.com/competitions/arc-prize-2026-arc-agi-3/overview
I'm not sure if I got it right but this means if we use LLMs we must use smaller models — which makes this proposal more important.
but having Sonnet will help us to have some benchmarks and a feasibility study, then see if smaller models are actually able to score the same. if they don't, we'll publish a credible paper with the Sonnet model and include small-model performances as well.

## Critical findings to build on (from Sensi, owner-selected)

- the curriculum steers what gets learned, not what gets done
- everything achieved so far ran on prose facts plus geometric evidence, not programs
- "Referent grounding: a genuine mid-tier capability gap: cross-referencing between distant prompt regions, and salience bias against small/dull percepts. Prompt rhetoric cannot fix it; mechanical joins can, cheaply. Generalized: anything that must not be missed has to be surfaced structurally, never requested rhetorically."
- Two modeling lessons that cut deeper than any mechanism: the environment has invisible state — the plate never latches visually; its armed state exists only behaviorally — so mechanistic facts must be tested by consequences, not appearances (the Cartographer models what looks different; only probing models what is different).
- "Frontier models sometimes hold that structure in attention (that's exactly what xhigh did for L1)." What we want is to preserve and present this structure for medium models in our structure. That's our contribution.
- "per-turn cognition re-decides from scratch every turn and the agenda lives nowhere" — the referent grounding.
- These issues are not unique to ARC AGI. They come from the gap mentioned above, and ARC AGI maximizes game hardship using this gap.

## What the design must be (owner's needs)

1. a design that is not focused on curriculum, but on DOING (we can use curriculum ...)
2. a structure that addresses Referent grounding
3. a separate search mechanism on the Referent grounding that expands it. this can be another LLM — called "conscious"? — that reasons through this referent grounding and turns it into a live model + agenda.
4. then player two reads this structure, model, agenda and can decide much better, especially if actions have been discovered — what to do.

Core question: how can we build a structure that is both keeping the structure AND LLMs can manipulate and consume well?

---

## Literature (owner-provided, four pillars)

### 1. Symbol grounding ↔ LLM understanding (the bidirectional core)
- Floridi et al. (late-2025): categorical framework arguing LLMs do not solve but CIRCUMVENT the symbol grounding problem — "epistemic parasitism" on human-grounded corpora. ARG must directly engage: it claims to convert LLM understanding into symbolic mechanics rather than assume grounding. https://arxiv.org/abs/2512.09117
- Zero-shot benchmark of 13 LLMs on Frame Problem / Symbol Grounding tasks (contextual reasoning, semantic coherence, information filtering) — relevant to the claim that understanding "exists strongly even in mid-level models". (arXiv 2506.07896)
- Neurosymbolic extraction lineage: Logic-LM (LLM → symbolic language → external reasoner; hallucination requires verification steps), Symbol-LLM, Concept-RuleNet (LLM as symbol extractor / rule generator, grounding via visual concepts).
- Dec-2025 survey on LLM symbolic reasoning (semantic-loss consistency, self-distillation aligning neural reps with symbolic inference, LLM-built world models for planning): https://arxiv.org/pdf/2509.07122 ; https://arxiv.org/pdf/2511.11751 ; https://www.techrxiv.org/doi/pdf/10.36227/techrxiv.176538331.19733376/v1
- Robotics grounding survey (formal symbols ↔ end-to-end embeddings tradeoff; SayCan, Code as Policies, VIMA): https://arxiv.org/html/2405.13245

### 2. Cross-referencing distant prompt regions
- BOOKCOREF: book-scale coreference, >200k-token documents. https://arxiv.org/pdf/2507.12075
- LegalCore: ~25k-token legal docs, coreference links >1000 tokens; all LLMs underperform a supervised baseline. https://arxiv.org/pdf/2510.17013
- DiscoTrack: entity tracking as reasoning tasks forcing whole-document attention; structured pairwise coreference is unnatural for LLMs.
- LQCA (ICLR 2025): integrating coreference resolution with information extraction improves LLM long-text comprehension. https://openreview.net/pdf?id=cPozlf9OaF
- LINK-KG: two-stage prompt-based coreference module with a type-specific prompt cache linking noun phrases to canonical names (multi-role entities, shifting aliases) — a proto-"referent grounding structure"; KEY comparison point. https://arxiv.org/pdf/2510.26486

### 3. Salience / positional bias
- "Found in the Middle": lost-in-the-middle is intrinsic U-shaped positional attention bias; calibration mitigates. https://arxiv.org/html/2406.16008v1
- Attention-basin follow-ups; shallow layers determine attended positions; initial-token saliency drives the U-shape. https://arxiv.org/pdf/2606.27793 ; https://arxiv.org/pdf/2410.14641
- LONGPIBENCH: bias related to SPACING between multiple relevant pieces (not just absolute position). 
- Context Rot Evaluation: up to 88-point drops mid-context; middle-position errors match surrounding filler — "filler-answer interference" ≈ the closest formulation of salience bias against dull percepts. https://arxiv.org/pdf/2605.23170

### 4. Multi-horizon goals, exploration/validation/rejection, queryable goal state
- BDI revived with LLMs: beliefs→world state/memory, commitment strategies, intention revision. 2025 review: essentially NO work on ML-driven option generation (generating viable intentions consistent with beliefs) partly due to hallucinated intentions — a claimable gap. T2B2T: bidirectional RDF↔BDI with provenance chains. https://arxiv.org/pdf/2512.09458 ; https://arxiv.org/pdf/2510.20641
- LLM long-horizon planning: subgoal dependencies, sparse feedback, error propagation; "objective drift" — agents deviate from the intended goal as interaction unfolds, token-inefficient ever-growing histories weaken global task-state tracking; HIPIF: subgoal decomposition + completed-progress summarization. https://arxiv.org/html/2606.10507
  - NOTE the convergence: goal drift in agents is literally the salience/cross-referencing problem applied to goals. That convergence is ARG's strongest novelty argument.
- Goal-state introspection: Thought Management System (hierarchical goals + self-critique), CUGA-style persistent task ledger with reflective re-planning. None expose a queryable, symbolically-grounded goal store; closest analogues are validation loops internal to execution. https://www.sciencedirect.com/science/article/abs/pii/S1877750325002170

### Benchmarks to evaluate ARG against
- Long-range/salience: BABILong (facts distributed in large corpora with deceptive mixing), RULER, HELMET, LongBench v2 (503 MCQ, 8K–2M words, human experts 53.7%), LONGPIBENCH (multi-piece spacing), BOOKCOREF/LegalCore (referent grounding at scale), CRE position-controlled protocol (show gains exactly where baselines collapse). https://arxiv.org/pdf/2406.10149
- Goal layer: PlanBench (~26,250 prompts; verification task = identify first inexecutable action + missing precondition — maps 1:1 onto explore/validate/reject/accept), Planet survey (benchmark family), TravelPlanner-style constrained planning.
- Grounding capability: Frame/Symbol-Grounding zero-shot benchmark (arXiv 2506.07896).

### Owner's framing suggestion
The literature treats these as four separate problems — grounding (philosophy/neurosymbolic), long-range reference (coreference/long-context), salience (attention mechanics), goal persistence (agents). ARG's pitch: they are ONE problem — goal drift IS referent-grounding failure under salience bias — so a structure that maintains aligned referents should fix all three surfaces at once. Nobody makes that unification explicit; the closest are the LQCA/LINK-KG line (referents) and HIPIF/Multi² line (goals), which never cite each other.

---

## The ARG proposal (verbatim)

a goal-oriented referent grounding or aligned referent grounding (let's call it ARG):
a structure that addresses the cross-referencing between distant prompt regions and salience bias against small/dull percepts which LLMs can manipulate and consume well, tied to an LLM called "conscious", pre-seeded multi-horizon goals.

The goal of this architecture is to turn LLM understanding capabilities (which we demonstrated exist strongly even in mid-level models) into symbolic representation mechanics and vice versa. Then align this understanding into multi-horizon goals.

Multi-horizon goals are expandable axioms which address the ambiguity of the relation between a higher goal and grounded truth.
Example: pre-seed the agent with one goal "win the game"; the agent must be able to understand, based on the current references, what is a logical set of sub-goals that can help it win — for ARC AGI: "learn the actions", "learn the rules", (maybe "learn the env"), then "win the game".
Since these are usually logical reasoning, they can be manipulated easily by an LLM and even adjusted by a human in early versions.
The more important aspect of ARG is to be able to relate structural learnings to these ordered goals and understand when they are achieved.
This fills the gap that a curriculum couldn't.

Alongside ARG we need:
- An Observer: an LLM that percepts the world, its changes, previous Actions, and the changes an action has done to the world. Observer gives its output to ARG.
- Actuator: another LLM that queries ARG and performs an Action. Actuator knows how to read ARG goals, finds the nearest unachieved goal, and asks ARG "in order to achieve goal_x what must I do?". Actuator has tools to achieve that goal and, once acted, updates both ARG and Log.
- Log: log of all perceptions and actions per turn_id, different from ARG. Log is a directed bridge from Actuator to Observer (not the other way).

What the design must address:
1. What is the symbolic relation that turns Observer's output into a structure that addresses the referent grounding issues in LLM contexts?
2. How does ARG align this internal structure with its goals in a way that can respond to Actuator's queries?
3. (list intentionally unfinished — the design must complete the question list itself)
