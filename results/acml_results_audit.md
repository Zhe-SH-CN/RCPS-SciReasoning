# ACML Results Audit

Generated: 2026-06-12T00:46:54.496680+00:00

## Method Results

| Method | Targets | Completed | Hits | Hit@10 | 95% CI | Full-set |
|---|---:|---:|---:|---:|---|---|
| baseline | 77 | 77 | 29 | 37.7% | [27.3, 48.1] | yes |
| pgcr | 77 | 77 | 22 | 28.6% | [18.2, 39.0] | yes |
| vanilla_expansion | 48 | 48 | 16 | 33.3% | [20.8, 47.9] | NO (48/77) |

## Hit-Set Overlaps

### baseline_vs_pgcr

- Method A hits: 29
- Method B hits: 22
- Common hits: 11
- Only in A: 18
- Only in B: 11

### baseline_vs_vanilla_expansion

- Method A hits: 29
- Method B hits: 16
- Common hits: 0
- Only in A: 29
- Only in B: 16

### pgcr_vs_vanilla_expansion

- Method A hits: 22
- Method B hits: 16
- Common hits: 2
- Only in A: 20
- Only in B: 14

## Oracle Warnings

⚠️ vanilla_expansion was evaluated ONLY on baseline misses (48 targets). Combined baseline+vanilla results are oracle-style and not a fair method.

⚠️ Oracle combined: 45/77 = 58.4% — this must not be reported as the main method.

## Token Usage

- baseline: 1,096,918 tokens
- pgcr: 814,247 tokens
- vanilla_expansion: 507,478 tokens

## Candidate Counts

- baseline: min=0, max=10, mean=9.5
- pgcr: min=12, max=96, mean=55.8
- vanilla_expansion: min=20, max=50, mean=41.7

## Judge Confidence

- baseline: mean=0.106, hit_mean=0.836, miss_mean=0.069
- pgcr: mean=0.083, hit_mean=0.84, miss_mean=0.058
- vanilla_expansion: mean=0.114, hit_mean=0.841, miss_mean=0.087

## Metadata Warnings

- [pgcr] Missing top-level keys: {'model'}
- [vanilla_expansion] Missing top-level keys: {'model'}

## Enrichment Status

- File: eval_neurips_2025_oral_enriched.jsonl
- Total records: 77
- Non-empty contributions: 77
- Ready for ACML judging: True

## Recomputation Notes

- ✅ baseline: reported hits match recomputed
- ✅ pgcr: reported hits match recomputed
- ✅ vanilla_expansion: reported hits match recomputed

