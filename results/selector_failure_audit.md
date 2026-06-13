# Selector Failure Audit

Generated: 2026-06-14T00:39:13.361973

## Summary

Both BCS and PGCR scorers show widespread fallback-like scores. The selection is not based on meaningful quality scores.

## BCS Scorer

- Total selected: 770
- Fallback score (3.0): 638 (82.9%)
- Empty reason: 638 (82.9%)
- From batch 0: 585 (76.0%)
- Duplicate titles: 0

## PGCR Scorer

- Total scored: 4300
- Fallback score (3.0): 4214 (98.0%)
- Empty reason: 4214 (98.0%)

## Conclusion

Both BCS and PGCR scorers show widespread fallback-like scores (overall=3, empty reason). Selection is not based on meaningful quality scores.
