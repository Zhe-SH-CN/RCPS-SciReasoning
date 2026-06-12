# Current ACML Idea Snapshot

Date: 2026-06-12

## Working Title

Structured-Evolutionary Budgeted Candidate Search for Scientific Idea Generation

## Target Venue

ACML 2026 Conference Track.

## Core Problem

Sci-Reasoning evaluates whether a system can generate future scientific ideas from predecessor papers. The current local experiments show that direct MiMo v2.5-pro generation reaches 29/77 Hit@10 on the NeurIPS 2025 Oral subset, while the earlier PGCR pattern-conditioned approach reaches 22/77. The apparent 45/77 oracle-combined result is not a fair method because it combines baseline hits with hard-case expansion after observing baseline misses.

The submission should therefore not claim PGCR is positive. The research question is whether a fair, target-hidden search-budget intervention can improve Hit@10 while keeping the final output budget fixed at 10 ideas.

## Proposed Method: BCS and SE-BCS

BCS means Budgeted Candidate Search.

For each target paper:

1. Generate a larger candidate pool from predecessor papers only.
2. Score candidates with target-hidden criteria such as grounding, specificity, novelty, plausibility, and diversity.
3. Select exactly 10 final ideas.
4. Judge the final 10 only after selection, using target title and enriched target contribution.

The method increases search budget, not final answer budget.

After external research, plain candidate expansion is no longer enough as a novelty claim. Graph2Idea, FlowPIE, Nova, LDC, SCI-IDEA, RQ-Bench, SciAidanBench, and future-aligned proposal prediction cover nearby graph-context, iterative-search, controllable-generation, and evaluation-bias territory.

The updated lightweight variant is **SE-BCS: Structured-Evolutionary Budgeted Candidate Search**:

1. Extract compact target-hidden predecessor structures:
   - problem,
   - method,
   - evidence,
   - limitation,
   - cross-paper relation triples.
2. Generate seed candidates from the structured context.
3. Generate crossover candidates by combining promising seed ideas.
4. Generate mutation candidates by changing one assumption, representation, data setting, or evaluation target.
5. Select exactly 10 ideas with target-hidden quality, diversity, and anti-mirage diagnostics.
6. Judge only after final selection.

SE-BCS must remain lightweight. It must not become a full graph database, MCTS system, RL-controlled generator, or long-horizon autonomous agent.

## Main Fairness Constraints

- Generation cannot see target title or target contribution.
- Scoring cannot see target title or target contribution.
- Selection and budget allocation cannot see target title or target contribution.
- Final output is exactly 10 ideas per target.
- Judge prompts may see target title and enriched contribution only after final ideas are selected.
- All reported numbers must come from JSON/JSONL outputs, not markdown summaries.

## Current Experimental Design

Phase 1 repairs data and evaluation:

- Fill missing target contributions for all 77 target records.
- Fix or wrap resume accounting in baseline and evaluation scripts.
- Create a robust ACML audit script and result summary.

Phase 2 tests the main method with MiMo v2.5-pro:

- Direct-10 enriched rejudge on all 77 targets.
- Full-set BCS-50 on all 77 targets.
- Full-set SE-BCS-50 on all 77 targets if plain BCS-50 and Phase 1 audits are clean; otherwise record why it was skipped.
- BCS-100 if useful for the budget curve.
- Selection ablations: random, score-only, diversity-aware, and baseline-preserving mixture.

Phase 3 tests robustness:

- MiMo v2.5 Direct-10 and BCS-50, preferably on all 77 targets.
- Secondary judge or judge-prompt robustness.
- Optional local open-source model subset only if setup is low-friction.

Phase 4 converts outputs into evidence:

- Main results table.
- Selection ablation table.
- Robustness table.
- Cost and budget curve.
- Bootstrap confidence intervals or paired comparison.
- Case studies and protocol integrity audit.

Phase 5 writes the ACML paper from the official ACML LaTeX template.

## Intended Claims

Strong claim, only if supported:

> Target-hidden structured/evolutionary candidate search improves scientific idea generation over direct generation on Sci-Reasoning under a fixed final-output budget.

Moderate claim:

> Candidate budget, selection policy, and judge design strongly affect measured scientific ideation performance.

Fallback claim:

> Pattern-conditioned and expanded candidate search reveal failure modes in current Sci-Reasoning evaluation.

## What Must Not Be Claimed

- Do not claim PGCR improves performance unless corrected experiments prove it.
- Do not present the 58.4% oracle combined result as the main method.
- Do not claim state of the art unless verified against external work.
- Do not claim that larger candidate pools alone are novel.
- Do not claim Graph2Idea/FlowPIE/Nova-level system novelty. This project is lighter and narrower.
- Do not claim cross-model robustness unless both MiMo v2.5-pro and MiMo v2.5 results exist.

## Novelty Hypothesis After External Search

The novelty is not "LLM generates more ideas." The defensible angle is:

> a controlled, target-hidden, fixed-output-budget Sci-Reasoning Hit@10 study that isolates candidate budget, structured predecessor compression, lightweight crossover/mutation, and anti-mirage selection diagnostics under a strict leakage protocol.

This is a narrower claim than Graph2Idea or FlowPIE. That is intentional: it keeps the project finishable before the ACML deadline.

## Automation and Reflection Requirements

Long-running Claude Code work must continuously check whether the direction is still valid.

Required workflow:

1. Use Superpowers if installed:
   - execute-plan for phase execution,
   - systematic debugging for failed scripts or inconsistent results,
   - code review before phase completion.
2. Use planning-with-files if installed:
   - read-before-decide,
   - persistent file-based planning,
   - context reduction by writing conclusions to files.
3. Use `Plan/07_DYNAMIC_REPLANNING_AND_SUBMISSION_GATES.md` as the reflection mechanism.
4. At every phase or major experiment boundary, update `Plan/RUN_STATE.md` with:
   - trigger,
   - evidence,
   - decision,
   - insufficiency or risk,
   - rollback condition,
   - next action.
5. After each completed phase or major part, run a secret/path sanity scan, commit the completed work, and push to `git@github.com:Zhe-SH-CN/PGCR.git`.

Major parts include:

- Phase 1 protocol/data repair,
- Direct-10 enriched rejudge,
- BCS-50 full run,
- SE-BCS-50 full run or skip decision,
- Phase 3 robustness,
- Phase 4 tables/analysis,
- Phase 5 paper draft/compile.

## Current Risk

The idea is not ACML-ready yet. It becomes viable only if full-set BCS or SE-BCS beats the enriched direct baseline, or if the experiments produce a strong, well-analyzed negative/budget result.
