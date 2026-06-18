# RCPS-SciReasoning

This repository contains code and public-facing scaffolding for a cache-controlled
Sci-Reasoning Hit@10 study of Risk-Controlled Candidate Portfolio Search (RCPS).

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

## Repository Layout

- `ACML_camera_ready/`: official ACML/JMLR template assets kept for public
  provenance.
- `scripts/`: experiment, audit, and analysis scripts used during development.
- `requirements.txt`: minimal Python dependency record for local scripts.
- `AGENTS.md`, `CLAUDE.md`: agent-operation notes for this workspace.

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
- `.env`
- `*.zip`

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

## Reproduction Notes

The experiments depend on provider endpoints and public Sci-Reasoning repository
artifacts. A bit-for-bit rerun requires the same provider APIs, model aliases,
and cache files. For review-facing reproduction, use sanitized aggregate tables,
audits, and scripts from the local supplementary package rather than raw logs.

## Submission Checklist

Before any public release or submission update:

1. Build the ACML PDF locally and check that there are no undefined citations or
   LaTeX errors.
2. Verify that every paper claim is traceable to structured result artifacts.
3. Confirm that the supplementary package contains no secrets, local paths, raw
   model outputs, or private planning notes.
4. Keep historical drafts and negative-result explorations out of the submitted
   paper unless explicitly reintroduced and audited.

