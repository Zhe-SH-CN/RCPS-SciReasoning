# RCPS-SciReasoning

RCPS-SciReasoning is a public code release for a cache-controlled
Sci-Reasoning Hit@10 study. It implements Risk-Controlled Candidate Portfolio
Search (RCPS).

The setup is fixed-budget scientific ideation. A method may search over
candidate ideas, but the benchmark evaluates only the final submitted
portfolio. RCPS keeps part of the direct generation output as anchors and uses
the remaining budget for target-hidden expansion candidates.

A paper based on this project has been submitted to ACML 2026.

## Repository layout

- `ACML_camera_ready/`: ACML/JMLR template files kept for provenance.
- `scripts/`: experiment, audit, and analysis scripts used by the public code
  release.
- `scripts/archive/`: older scripts kept for historical reference.
- `requirements.txt`: Python package snapshot generated with `uv pip freeze`.
- `AGENTS.md`: public agent-operation notes for this workspace.

Several local directories are intentionally not tracked because they are private
workspace material or generated artifacts:

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

## Environment

Create the local Python environment with:

```bash
UV_CACHE_DIR=.uv-cache uv venv .venv
UV_CACHE_DIR=.uv-cache uv pip install -r requirements.txt
```

Run scripts with `.venv/bin/python`.

## Reproduction notes

The experiments depend on provider endpoints and artifacts from the public
Sci-Reasoning repository. Exact reruns require the same model aliases, provider
settings, and cache files.

The current RCPS code path is the root-level `scripts/38` through `scripts/45`
chain. Scripts under `scripts/archive/` are retained for traceability. Recheck
their inputs and outputs before using them in new experiments.

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

## Intended use

This repository is for educational and academic research use. It is not intended
for production scientific-discovery systems, automated paper generation, or
unsupervised decisions about scientific merit.
