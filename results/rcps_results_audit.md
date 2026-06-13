# RCPS Results Audit

Generated: 2026-06-14T00:41:07.736544

## Main Results

| Method | Hits | Hit@10 | 95% CI | Parse Rate |
|---|---:|---:|---|---:|
| direct10 | 20 | 26.0% | [16.9, 36.4] | 0.1% |
| bcs50 | 16 | 20.8% | [11.7, 29.9] | 0.0% |
| pgcr | 14 | 18.2% | [10.4, 27.3] | 0.0% |

## Paired Comparison vs Direct-10

| Method | Wins | Losses | Ties |
|---|---:|---:|---:|
| bcs50 | 11 | 15 | 5 |
| pgcr | 11 | 17 | 3 |

## Union Analysis

- Union hits: 40
- Common hits (all methods): 2
- Direct-10 only: 14
- BCS-50 only: 9
- PGCR only: 9

## Oracle Warning

⚠️ Union of all methods has 40 hits, more than any single method. Do not report as a fair method.

## Token Costs

| Method | Total Tokens |
|---|---:|
| direct10 | 1,907,440 |
| bcs50 | 4,103,615 |
| pgcr | 10,335,016 |

## Parse Failures

### direct10

- Total judgments: 770
- Parse OK: 1 (0.1%)
- Parse fail: 769
- Empty reason: 705
- Confidence zero: 706

### bcs50

- Total judgments: 770
- Parse OK: 0 (0.0%)
- Parse fail: 770
- Empty reason: 698
- Confidence zero: 699

### pgcr

- Total judgments: 770
- Parse OK: 0 (0.0%)
- Parse fail: 770
- Empty reason: 706
- Confidence zero: 709

