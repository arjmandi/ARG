# Paper — build & submission kit

Source for the ARG dissociation paper, targeting **Verify-Agents @ NeurIPS 2026**
("Who Verifies the Agents? Toward Reliable Agent Development") and **arXiv**.

- `paper.tex` — one source, two builds (workshop-anonymous / arXiv-named).
- `references.bib` — 9 references, all arXiv-verified 2026-07-31 (one author field flagged, see below).

## Prerequisite: the NeurIPS 2026 style file

The workshop mandates the **NeurIPS 2026 template**. Download `neurips_2026.sty`
(and `neurips_2026.bst` if provided) from the NeurIPS 2026 author kit / the workshop
site, and drop it in this directory. `paper.tex` already `\usepackage`s it. If
`\citep` is undefined at build time, the `.sty` in this dir is not the real NeurIPS
one (it loads `natbib`).

## Two builds from one source

Both switches live at the top of `paper.tex`:

| Target | Template line | Body switch |
|---|---|---|
| **Workshop (double-blind)** | `\usepackage{neurips_2026}` | `\anontrue` |
| **arXiv (named preprint)** | `\usepackage[preprint]{neurips_2026}` | `\anonfalse` |
| Camera-ready (if accepted) | `\usepackage[final]{neurips_2026}` | `\anonfalse` |

The template auto-anonymizes the **author block** in submission mode; the `\ifanon`
switch only governs body de-anonymizers the template does not touch (the repo URL
and the first-person "our predecessor" phrasing — both already wrapped).

Build (either target):

```bash
pdflatex paper && bibtex paper && pdflatex paper && pdflatex paper
```

## Submitting

**arXiv (named — do this now, per plan):** set the arXiv build switches, then upload
the **source** (`paper.tex`, `references.bib`, `neurips_2026.sty`, `neurips_2026.bst`
if used) — arXiv compiles it. Category `cs.AI` (cross-list `cs.LG`). The paper's
reproducibility line points at repo tag `v1.0-paper`, so push that tag before the
preprint goes live.

**Verify-Agents (double-blind, non-archival):** set the workshop build switches,
build the **anonymized PDF**, and submit on OpenReview:
`https://openreview.net/group?id=NeurIPS.cc/2026/Workshop/Verify-Agents`.
- Deadline **2026-08-29, 23:59 AoE**; notification 2026-09-29; workshop Dec 11/12, Sydney.
- Length **4–9 pages** excluding references and appendices (this draft ≈ 7–8pp).
- Non-archival: acceptance appears on OpenReview, not formal proceedings — arXiv-first is fine.

## Double-blind anonymization checklist (run before uploading the workshop PDF)

- [ ] Built with `\usepackage{neurips_2026}` (no `preprint`/`final`) **and** `\anontrue`.
- [ ] Author block shows "Anonymous Author(s)" (template handles this automatically).
- [ ] No repo URL / `v1.0-paper` in the PDF (the `\ifanon` reproducibility paragraph handles this — it references "an anonymized repository").
- [ ] Sensi is cited in third person as prior work `[5]`, not "our predecessor" (handled by `\ifanon`).
- [ ] No acknowledgments, no identifying metadata in the PDF properties.
- [ ] Grep the built `.pdf` text for "Arjmandi", "arjmandi", "Evolution", "Independent researcher" → zero hits.

## Outstanding before submission (author actions)

1. **`references.bib` [3] LongPiBench** — fill the real author list from arXiv:2410.14641. It's the one field not verified; do not guess.
2. **[5] Sensi figures** — the paper deliberately cites Sensi only for its *hallucination cascade* and attributes **no run figures** to it (the turn numbers / 2,300-actions / 0→3/3 are not in Sensi's public paper or blog). If you have those run logs, publishing them to the `sensi` repo lets the numbers return as cited re-analysis.
3. **Design doc sweep** — `docs_arg_design.md` (linked from the README) still presents `0/200→3/3`, `t150/t184`, `~2,300 actions/13 runs` as ARG's own "G2 vs G3" historical runs in ~6 places. Same airtight-or-absent exposure if a reviewer follows README → design: confirm those runs are logged/reproducible, or soften. (Not yet done — say the word.)
4. **Confirm** the `neurips_2026` template version and whether the workshop wants the NeurIPS paper checklist (workshops usually omit it — verify on OpenReview).
