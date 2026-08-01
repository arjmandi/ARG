# Paper — build & submission kit

Source for the ARG dissociation paper, targeting **Verify-Agents @ NeurIPS 2026**
("Who Verifies the Agents? Toward Reliable Agent Development") and **arXiv**.

- `paper.tex` — one source, two builds (workshop-anonymous / arXiv-named).
- `references.bib` — 10 entries: 9 references (all arXiv-verified 2026-07-31) plus one
  anonymized stand-in (`sensi_anon`) used only in the blind build.
- `.gitignore` — LaTeX artifacts, the built PDF, and `neurips_2026.sty` are ignored.

## Prerequisite: the NeurIPS 2026 style file

The workshop mandates the **NeurIPS 2026 template**. A working `neurips_2026.sty`
(declares `\ProvidesPackage{neurips_2026}[2026-01-29 …]`) has been placed in this
directory **from a community mirror** (the official `media.neurips.cc/.../NeurIPS2026/Styles`
URL 404'd at build time). It is **not committed** (provenance + it is NeurIPS's file).
**Before final submission, replace it with the official author-kit `.sty`** and
rebuild — the layout must be the official one.

The mirror `.sty` pulls in `environ.sty`. Easiest path: build with **tectonic**,
which auto-fetches missing packages. With `pdflatex`, first `tlmgr install environ`.

## Two builds from one source

Switches at the top of `paper.tex`:

| Target | Template line | Body switch |
|---|---|---|
| **Workshop (double-blind)** | `\usepackage{neurips_2026}` | `\anontrue` |
| **arXiv (named preprint)** | `\usepackage[preprint]{neurips_2026}` | `\anonfalse` |
| Camera-ready (if accepted) | `\usepackage[final]{neurips_2026}` | `\anonfalse` |

Anonymization is handled three ways, all verified by building both variants:
1. the template prints **"Anonymous Author(s)"** in submission mode;
2. citations are **numeric** (`\PassOptionsToPackage{numbers}{natbib}`), so no author
   name appears in-text;
3. the **self-citation to the predecessor system auto-swaps** to an anonymized entry
   (`sensi_anon`) under `\anontrue`, and the repo URL / "our" phrasing are wrapped in
   `\ifanon` — so the blind PDF contains no "Sensi", "Arjmandi", or repo link.

## Build

```bash
tectonic paper.tex          # recommended (auto-fetches environ, natbib, …)
# or, with a full TeX Live that has `environ`:
pdflatex paper && bibtex paper && pdflatex paper && pdflatex paper
```

## Submitting

**arXiv (named — per plan, now):** set the arXiv switches, upload the **source**
(`paper.tex`, `references.bib`, and the official `neurips_2026.sty`). Category `cs.AI`
(cross-list `cs.LG`). The reproducibility line points at repo tag `v1.0-paper`.

**Verify-Agents (double-blind, non-archival):** keep the workshop switches, build the
anonymized PDF, submit on OpenReview
(`https://openreview.net/group?id=NeurIPS.cc/2026/Workshop/Verify-Agents`).
Deadline **2026-08-29 23:59 AoE**; notify 2026-09-29; workshop Dec 11/12, Sydney.
Length **4–9pp** excl. refs/appendices (this build ≈ **7pp**).

## Anonymization check — VERIFIED (2026-08-01)

The anonymous build was compiled and its text grepped; **zero** hits for
`arjmandi / evolution / independent researcher / github / sensi / v1.0-paper / gmail`.
Re-run after any edit:

```bash
tectonic paper.tex && pdftotext paper.pdf - \
  | grep -inE "arjmandi|evolution|independent researcher|github|sensi|v1\\.0-paper|gmail" \
  && echo "LEAK" || echo "clean"
```

## Status of the earlier outstanding items

1. **NeurIPS `.sty`** — fetched locally (community mirror, validated); **swap for the
   official author-kit `.sty` before final submission.** *(done, with caveat)*
2. **`[3]` LongPiBench authors** — filled from arXiv:2410.14641 (13 authors). *(done)*
3. **`[5]` Sensi figures** — **dropped** (author decision); the paper attributes no run
   figures to Sensi. If the run logs are published to the `sensi` repo, they can return
   as cited re-analysis.
4. **Design-doc sweep** — `docs_arg_design.md` still presents `0/200→3/3`, `t150/t184`,
   `~2,300 actions/13 runs` as ARG's own "G2 vs G3" runs (~6 places). **Still open** —
   confirm those runs are logged/reproducible, or soften, before a reviewer follows
   README → design.
