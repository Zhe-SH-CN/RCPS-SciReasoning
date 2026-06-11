# ACML Readiness Audit

Generated: 2026-06-11

## Verdict

Current state is not ready for ACML submission.

The project is still potentially salvageable for ACML 2026 Conference Track, but only after a protocol correction and a paper reframing. The current strongest number, 58.4% Hit@10, is an oracle-style combined result because vanilla expansion was run only on the 48 targets that the baseline had already missed. This cannot be used as the main ACML result.

## ACML Constraints

Authoritative source: https://www.acml-conf.org/2026/calls/papers/

- Conference Track deadline: 2026-06-26, 23:59 AoE.
- Conference Track format: ACML/JMLR style, not IEEE.
- Length: 16 pages including references and appendix.
- Review: double-blind.
- At least one author must be nominated as reviewer or area chair; otherwise desk reject unless the PCs approve an exception before 2026-06-23.
- Local template: `ACML_camera_ready/acml26_submission_template.tex`.

Given the current date, the practical target is ACML 2026 Conference Track. The journal track deadline is 2026-06-20 and is too tight for this project unless the user explicitly switches track.

## Files Reviewed

Primary generated outputs:

- `mimo_summary_for_ICTAI_task.md`
- `results/baseline_mimo.json`
- `results/pgcr_full.json`
- `results/vanilla_expansion_eval.json`
- `results/baseline_summary.md`
- `results/vanilla_expansion_summary.md`
- `logs/experiment_summary.json`
- `logs/experiment_log.jsonl`
- `paper/main.tex`
- `paper/references.bib`
- `paper/submission_checklist.md`

Scripts:

- `scripts/mimo_client.py`
- `scripts/00_test_mimo_connection.py`
- `scripts/01_prepare_scireasoning_data.py`
- `scripts/02_render_prompts.py`
- `scripts/03_run_baseline_mimo.py`
- `scripts/05_summarize_results.py`
- `scripts/06_generate_pgcr_candidates.py`
- `scripts/07_score_pgcr_candidates.py`
- `scripts/08_select_pgcr_top10.py`
- `scripts/09_evaluate_pgcr.py`
- `scripts/10_vanilla_expansion.py`
- `scripts/11_score_and_select_vanilla.py`
- `scripts/experiment_logger.py`

Planning and paper files:

- `Plan/`
- `CLAUDE.md`
- `ACML_camera_ready/`

## Verified Current Results

From JSON result files:

| Method | Target set | Candidates | Hits | Total | Hit@10 |
|---|---:|---:|---:|---:|---:|
| MiMo v2.5-pro baseline | full | 10 | 29 | 77 | 37.7% |
| PGCR full | full | about 80 | 22 | 77 | 28.6% |
| Vanilla expansion | baseline misses only | 50 | 16 | 48 | 33.3% |
| Oracle combined | baseline hits + hard-case expansion hits | mixed | 45 | 77 | 58.4% |

Important overlap facts:

- PGCR hits 22 targets, but only 11 are baseline misses.
- PGCR loses 18 baseline-hit targets.
- Vanilla expansion was evaluated only on the 48 baseline misses.
- The 58.4% combined result equals `baseline_hits union vanilla_hard_hits`; it uses knowledge of baseline failure and is not a fair standalone method.

## Data Quality Issues

1. `data/scireasoning/eval_neurips_2025_oral.jsonl` has 77 targets, but all 77 have empty `contribution`.
2. The judge therefore falls back to comparing generated ideas against the target title, not a full target contribution.
3. Contribution text appears recoverable from local Sci-Reasoning evaluation result files:
   - `Sci-Reasoning/research_idea_evaluation/results/evaluation_results_claude_sonnet_final.json`
   - `Sci-Reasoning/research_idea_evaluation/results/evaluation_results_claude_opus_final.json`
   - `Sci-Reasoning/research_idea_evaluation/results/evaluation_results_gemini_25pro_final.json`
   - `Sci-Reasoning/research_idea_evaluation/results/evaluation_results_gpt52_v3_exa_final.json`
4. The source paths embedded in the eval JSONL point to `/home/zsz/ICTAI/...`; these should be normalized or removed from paper-facing artifacts.

## Script Issues

Must fix before ACML reruns:

- `scripts/03_run_baseline_mimo.py` resume mode loads existing targets but does not initialize `total_hits` and token counters from previous results.
- `scripts/09_evaluate_pgcr.py` has the same resume-counter risk.
- `results/vanilla_expansion_eval.json` has `"method": "pgcr_full"` although it is vanilla expansion.
- `scripts/05_summarize_results.py` reports `Avg ideas/target` from `generated_ideas`, so it is wrong for PGCR/selected-candidate outputs.
- `baseline_summary.md` token counts do not match `baseline_mimo.json`.
- Logger summary is useful for token accounting but has stage-level summaries that should not be treated as final method metrics.

Protocol rules that look correct:

- Generation and scoring prompts do not expose target title or contribution.
- The judge sees target title and contribution only after ideas are generated.
- MiMo API calls default to `--sleep-seconds 0.5`.
- Scripts are mostly resumable and checkpoint after target-level outputs.

## Paper Issues

`paper/main.tex` is not ACML-ready:

- Uses IEEEtran, not ACML/JMLR template.
- Uses anonymous IEEE author block, not ACML empty-author style.
- Presents the oracle combined result as the main improvement.
- Contains placeholder/fake bibliography entries inside the TeX body.
- Cost table is inconsistent with logs and result JSON.
- Claims "5 candidates" in one analysis sentence while the method says 50 candidates.
- Does not discuss the empty-contribution fallback and judge limitations.

This draft should be treated as content notes, not as a submission draft.

## Idea Assessment for ACML

The original PGCR idea is not supported. PGCR is a negative ablation.

The candidate-expansion idea is plausible but currently too weak for ACML unless upgraded into a fair, budgeted-search study:

- Full-set fair evaluation is missing.
- Cross-model replication is missing.
- Judge robustness is missing.
- Budget curves are missing.
- Statistical confidence intervals and paired comparisons are missing.
- The method needs an oracle-free selection/allocation rule.

Recommended ACML framing:

**Budgeted Candidate Search for Scientific Ideation.**

Claim to test:

> Under a fixed Hit@10 protocol on Sci-Reasoning, target-hidden candidate expansion plus quality/diversity selection improves scientific idea generation over direct generation, while pattern-conditioned expansion can reduce recall.

This is ACML-plausible only if the corrected experiments show a full-set improvement and a clean mechanism.

## Minimum Bar for Submission

Submit only if all of the following hold:

- Full 77-target MiMo v2.5-pro candidate expansion beats the v2.5-pro direct baseline by at least 5 percentage points.
- The final method selects exactly 10 ideas per target without seeing target title or target contribution.
- Results are rejudged with enriched target contributions.
- The improvement is not solely an artifact of a same-model judge.
- At least one replication is available: MiMo v2.5, a different judge, or a local open-source model.
- ACML/JMLR paper compiles from the ACML template.

If these fail, pivot to a shorter empirical negative-result framing only if the analysis is unusually strong.

