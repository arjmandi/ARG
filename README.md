# ARG — Aligned Referent Grounding

**The LLM proposes, the Executive disposes: consequence-earned grounding for long-horizon agents.**

ARG is an agent architecture in which a language model's output never becomes belief directly. Every claim enters a deterministic **Executive** as a typed proposal in a closed vocabulary, and is admitted only by *earning* it — a perceived object or rule climbs grounding tiers solely when a pre-registered prediction about its consequences is matched against observation by code. Everything is append-only and replayable: every belief, plan, and achievement is a queryable row with the receipts that produced it.

ARG is the successor to [Sensi](https://github.com/arjmandi/sensi) ([arXiv 2603.17683](https://arxiv.org/abs/2603.17683)), rebuilt around the failure Sensi diagnosed — a self-consistent hallucination cascade (binding loss, in the present taxonomy) — with the commitment component drawn from the goal-drift literature, so that both drift components are externalized in code and measured separately. It is evaluated on [ARC-AGI-3](https://three.arcprize.org) interactive games, entered with zero prior knowledge, and is substrate-general by design — nothing above the environment adapter knows what a game is.

**Author:** Mohsen Arjmandi · Independent researcher · July 2026

---

## Status

- **52 gated live runs, ~17M tokens. Zero level completions in every run, including every baseline.** The efficacy claim (P0) is open and pre-registered as a structural defeater — a ~0-wins endpoint would defeat the contribution, not footnote it.
- What the campaign **has** validated are mechanism results, each earned under the system's own validity gates:
  - **Commitment-drift dissociation** confirmed at protocol seed count: removing the agenda mechanism flips goal-abandonment (GDS-abandon) 0.00 → 1.00 while binding error stays flat, measured against per-beat shadow-compiled reference plans.
  - **Binding drift structurally absorbed:** removing the LLM-facing render join changes nothing per-beat, because aiming, attribution, and grounding promotion are Executive-owned code; the join dimension's residue appears upstream as hypothesis-formation collapse in the double-kill cell (0/4 seeds).
  - **Generative curriculum from zero knowledge:** with no seeded goals, the system generated the canonical learn-shaped curriculum from its own typed knowledge deficits.
  - **Small-model floor crossed:** Haiku-class ran the complete loop VALID at write-error-rate 0.0 (a worked-examples contract lever took Surveyor WER 0.55–0.71 → 0.333 → 0.0), with engaged milestones and aimed experiments.
  - **Generality:** the machinery engaged on 3/3 games never touched by a design decision.
- Eight live-only defects were caught by the system's own gates during the campaign and fixed same-day, each pinned by a test.

Full results narrative with per-run tables: [`docs_arg_campaign_ls20.md`](docs_arg_campaign_ls20.md).

## Documents

**Start here — the reviewer path:**

| Document | What it is |
|---|---|
| [`docs_arg_paper_dissociation.md`](docs_arg_paper_dissociation.md) | **The paper** — *Dissociating commitment drift from binding drift in long-horizon LLM agents.* The headline mechanism result, the instrument that measures it, and the honest null on task efficacy |
| [`docs_arg_design.md`](docs_arg_design.md) | **The normative spec** — thesis, structure, goals, organs, doing loop, generality contract, ablation plan (§8), failure modes, 25 adopted amendments, and the 27-attack adversarial review ledger |
| [`docs_arg_campaign_ls20.md`](docs_arg_campaign_ls20.md) | **The results record** — batches 1–4 and waves E–F: every run, every verdict, every live-caught defect |
| [`docs_arg_worksample.md`](docs_arg_worksample.md) | 4-page overview for technical reviewers |

**Methods & record:**

| Document | What it is |
|---|---|
| [`docs_arg_expected_outcomes.md`](docs_arg_expected_outcomes.md) | The measurement framework: mechanism → observable → instrument, pre-registered claims P0–P4 with falsified-ifs, run protocol |
| [`docs_arg_goal_chaining_proposal.md`](docs_arg_goal_chaining_proposal.md) | The goal-chain sufficiency engine proposal (recognizer, verified fill, milestones) |
| [`docs_arg_cold_start_evaluation.md`](docs_arg_cold_start_evaluation.md) | The zero-knowledge walkthrough: feasibility of the cold-start cycle, tool seam, small-model plan |
| [`docs_arg_brief.md`](docs_arg_brief.md) / [`docs_arg_buildplan.md`](docs_arg_buildplan.md) | The original owner brief and the build plan derived from the design |
| [`docs_arg_design_coverage.md`](docs_arg_design_coverage.md) / [`docs_arg_code_review.md`](docs_arg_code_review.md) / [`docs_arg_verification.md`](docs_arg_verification.md) | Spec-to-code coverage audit, independent code review, verification record |

## Layout

```
agents/arg/          the system: executive.py (deterministic core), organs.py (LLM
                     role contracts), store.py (append-only SQLite + triggers),
                     predicates.py (closed test grammar), renderer.py (zoned views),
                     agent_arg.py (the beat loop), adapter.py (the ONLY
                     game-specific code), pather.py, seeds.py, baselines.py
agents/              minimal ARC-AGI-3 harness (agent, structs, recorder, swarm)
tests/               25 hermetic suites (~400 assertions) + byte-level golden renders;
                     no test can reach a real LLM
probe_arg_*.py       read-only instruments: §8 metrics, run-validity gate (WER floors,
                     render ceiling, canary echo), health, store/log inspectors
docs_arg_*.md        design, results, methodology (see table above)
```

## Running

```bash
uv sync
cp .env.example .env   # fill ARC_API_KEY + your LLM provider key

# offline test battery (hermetic — no API calls, no keys needed)
for t in tests/test_arg_*.py; do uv run python "$t"; done

# a live run (400 actions, generative cold start, Sonnet-class backbone)
ARG_SEEDS=0 SENSI_MAX_ACTIONS=400 uv run python main.py --agent=arg --game=ls20

# gate + read the run (replayable from the append-only stores)
uv run python probe_arg_legibility.py --db arg_state.db --probe arg_probe.db
uv run python probe_arg_metrics.py    --db arg_state.db --probe arg_probe.db
```

Factorial and ablation cells are environment flags (`ARG_JOIN=0`, `ARG_AGENDA=0`, `ARG_SEEDS=0`, `ARG_MODEL=...`, `ARG_OP_EXAMPLES=1`, …) — see `agents/arg/config.py` and the §8 protocol in the outcomes doc.

## License

**MIT** — see [`LICENSE`](LICENSE). Released permissively so the work can be read, run, and built on, with attribution preserved. The release passes the design's own §7 gate (exemplar scrub + vocabulary glossary); the lint is runnable:

```bash
uv run python probe_arg_release.py     # exemplar scrub + vocabulary lint over model-facing surfaces
```
