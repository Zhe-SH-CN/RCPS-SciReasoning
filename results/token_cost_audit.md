# Token Cost Audit

Generated: 2026-06-14T00:39:45.207409

## Summary

| Method | Total Tokens | Tokens/Target | vs Direct-10 |
|---|---:|---:|---:|
| Direct-10 | 1,907,440 | 24,772 | 1.00x |
| BCS-50 | 4,103,615 | 53,294 | 2.15x |
| PGCR | 10,335,016 | 134,221 | 5.42x |

## Breakdown

### Direct-10

- Generation: 1,096,918
- Enriched rejudge: 810,522
- Total: 1,907,440

### BCS-50

- Generation: 1,644,589
- Scoring: 1,605,338
- Evaluation: 853,688
- Total: 4,103,615

### PGCR

- Generation: 0
- Scoring: 9,480,185
- Evaluation: 854,831
- Total: 10,335,016

## Key Finding

BCS-50 uses 2.15x more tokens than Direct-10, not 5% as previously claimed. PGCR uses 5.42x more tokens than Direct-10.
