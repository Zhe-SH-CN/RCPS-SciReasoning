# RCPS-SciReasoning

This repository contains public-facing code and scaffolding for a
cache-controlled Sci-Reasoning Hit@10 study of Risk-Controlled Candidate
Portfolio Search (RCPS).

The project studies a fixed-budget scientific ideation setting: a system may
generate or search over candidate ideas, but the benchmark evaluates only the
final submitted portfolio. RCPS keeps a prefix of Direct-generation ideas as
anchors and fills the remaining slots with target-hidden expansion candidates.

## Current Submission Scope

The current paper is an ACML 2026 Conference Track submission draft titled:

> Risk-Controlled Candidate Portfolio Search for Target-Hidden Scientific Idea Generation

The paper's main empirical claim is a paired cache-controlled comparison on
Sci-Reasoning Hit@10. Direct, BCS, and RCPS use the same released predecessor
cache, final budget, parser, and binary judge. The work does not claim exact
live-Exa reproduction, SOTA performance, human-confirmed scientific novelty, or
statistical significance.

## Citation

If you use this repository in academic work, please cite it as:

```bibtex
@misc{rcps_scireasoning_2026,
  title        = {{RCPS-SciReasoning}: Risk-Controlled Candidate Portfolio Search for Sci-Reasoning Hit@10},
  author       = {{RCPS-SciReasoning Contributors}},
  year         = {2026},
  howpublished = {\url{https://github.com/Zhe-SH-CN/RCPS-SciReasoning}},
  note         = {Research code for a cache-controlled Sci-Reasoning Hit@10 study}
}
```

If a formal paper citation becomes available, prefer the paper citation and use
the repository citation for code or artifact references.

## Intended Use

This repository is provided for educational and academic research purposes only.
It is not intended for production scientific-discovery deployment, automated
paper generation, or unsupervised decision-making about scientific merit.

## Repository Layout

- `ACML_camera_ready/`: official ACML/JMLR template assets kept for public
  provenance.
- `scripts/`: current experiment, audit, and analysis scripts.
- `scripts/archive/`: preserved historical scripts from earlier MiMo, PGCR,
  clean-context, and Sci-Reasoning reset phases.
- `requirements.txt`: clean `uv pip freeze` snapshot from the project environment.
- `AGENTS.md`: public agent-operation notes for this workspace.
- `CLAUDE.md`: local ignored handoff notes; not part of the public repository.

Several local directories are intentionally excluded from Git because they may
contain paper drafts, raw benchmark data, target contributions, model outputs,
logs, private planning notes, or provider credentials:

- `paper/`
- `Plan/*.md`
- `results/`
- `data/scireasoning/`
- `supplement/`
- `literature/`
- `logs/`
- `archive/`
- `wiki/`
- `.env`
- `*.zip`

Private local archives also exist under ignored directories such as
`archive/`, `Plan/archive/`, `paper/archive/`, and `wiki/`. They preserve
history for rebuttal and handoff, but are not public release artifacts.

## Public Artifact Boundary

The repository is not meant to expose the full submission package or raw
experiment traces. The local submission package is prepared separately from
sanitized aggregate files and should be reviewed before upload.

Do not commit:

- raw model responses,
- API keys or provider logs,
- cached Exa paper text,
- target-level contribution text,
- private planning files,
- paper source or generated PDFs unless a deliberate release decision is made.

## Environment

The local Python environment can be recreated with:

```bash
UV_CACHE_DIR=.uv-cache uv venv .venv
UV_CACHE_DIR=.uv-cache uv pip install -r requirements.txt
```

After setup, run scripts with `.venv/bin/python`.

## Reproduction Notes

The experiments depend on provider endpoints and public Sci-Reasoning repository
artifacts. A bit-for-bit rerun requires the same provider APIs, model aliases,
and cache files. For review-facing reproduction, use sanitized aggregate tables,
audits, and scripts from the local supplementary package rather than raw logs.

Current paper-facing scripts are the root-level `scripts/38` through
`scripts/45` chain. Archived scripts are retained for traceability only and
should not be used for current claims without a fresh audit.

## Submission Checklist

Before any public release or submission update:

1. Build the ACML PDF locally and check that there are no undefined citations or
   LaTeX errors.
2. Verify that every paper claim is traceable to structured result artifacts.
3. Confirm that the supplementary package contains no secrets, local paths, raw
   model outputs, or private planning notes.
4. Keep historical drafts and negative-result explorations out of the submitted
   paper unless explicitly reintroduced and audited.
