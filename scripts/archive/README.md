# Scripts Archive

This directory preserves historical experiment scripts that are no longer part
of the current ACML 2026 RCPS submission chain.

Use the root-level scripts for the current paper route:

- `38_scireasoning_official_cache_exa.py`
- `39_scireasoning_official_cache_methods.py`
- `40_audit_script38_outputs.py`
- `41_static_audit_script38_methods.py`
- `43_build_rcps_no_api_analysis.py`
- `45_rcps_anchor_selector_sensitivity.py`

`42_run_script38_gemini_plan40.py` and
`44_run_mimo_script38_direct_bcs_rcps.py` are retained at the root as run
or reference wrappers. Do not rerun them without checking current paths,
provider aliases, and output-overwrite behavior.

Archive groups:

- `early_mimo_pgcr/`: early MiMo, PGCR, BCS, and negative-result audit scripts.
- `cross_model_clean_context/`: GLM/MiniMax/MiMo clean-context and self-judge diagnostics.
- `scireasoning_reset/`: superseded Sci-Reasoning reset, cache, and live-Exa transition scripts.
- `helpers/`: helper modules used by early scripts.
- `final_run_wrappers/`: local monitor helpers from final runs.
- `generated/`: generated Python caches kept out of the active script root.

Archived scripts may be useful for reconstructing the project history, but they
are not valid evidence for the submitted RCPS numbers unless a later audit says
otherwise.
