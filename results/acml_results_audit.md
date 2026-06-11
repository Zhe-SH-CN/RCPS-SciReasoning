# ACML Results Audit

Generated: 2026-06-11 22:57

**This report is computed from JSON result files, not from markdown summaries.**

## Method Comparison

| Method | Targets | Hits | Hit@10 | 95% CI | Full-set? |
|--------|--------:|-----:|-------:|--------|-----------|
| Baseline | 77 | 29 | 37.7% | [27.3%, 48.1%] | Yes |
| Pgcr | 77 | 22 | 28.6% | [18.2%, 39.0%] | Yes |
| Vanilla Expansion | 48 | 16 | 33.3% | [20.8%, 47.9%] | No (hard-case only) |
| Oracle Combined | 77 | 45 | 58.4% | — | **NOT FAIR** |

## PGCR vs Baseline Overlap

- PGCR hits also in baseline: 11
- PGCR new hits (baseline misses): 11
- Baseline hits lost by PGCR: 18

## Vanilla Expansion Analysis

- Evaluated on 48 targets (baseline misses)
- Hard-case-only: True
- New hits: 16
- Oracle combined hits: 45 / 77 = 58.4%

**WARNING: Oracle combined uses knowledge of baseline failures. Not a fair standalone method.**

## Baseline Details

- Model: mimo-v2.5-pro
- Completed: 77 / 77
- Candidates: min=0, max=10, mean=9.5
- Tokens: input=510,254, output=586,664
- Match confidence: mean=0.84, min=0.6, max=0.95 (n=35)

## Pgcr Details

- Model: mimo-v2.5-pro
- Completed: 77 / 77
- Candidates: min=12, max=96, mean=55.8
- Tokens (from file): 814,247
- Match confidence: mean=0.84, min=0.7, max=0.95 (n=25)

## Vanilla Expansion Details

- Model: mimo-v2.5-pro
- Completed: 48 / 48
- Candidates: min=20, max=50, mean=41.7
- Tokens (from file): 507,478
- Match confidence: mean=0.84, min=0.6, max=0.95 (n=17)

  ⚠ evaluated on baseline-miss subset only (not full-set)
  ⚠ method field says "pgcr_full" but analyzed as "vanilla_expansion"

## Eval Data Quality

- Enriched file exists: True
- Total records: 77
- Non-empty contributions: 77
- Empty contributions: 0
- Avg predecessors: 6.9
- Path leaks: 0

## All Warnings

- [vanilla_expansion] evaluated on baseline-miss subset only (not full-set)
- [vanilla_expansion] method field says "pgcr_full" but analyzed as "vanilla_expansion"
